"""
RAG Document Agent; core logic.

Flow:
  upload_pdf(path, conversation_id) → load → split → embed → persist in ChromaDB
  stream_query(question, conversation_id) → retrieve relevant chunks → stream answer via Claude
"""

from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import PromptTemplate

load_dotenv()

PERSIST_DIR = "./chroma_db"
EMBED_MODEL = "all-MiniLM-L6-v2"  # free, runs locally, no API key needed

QA_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template="""Answer the question using only the context below.
If the context does not contain enough information, say so clearly. Do not use any markdown formatting. Answer in the same language as the question.

Context:
{context}

Question: {question}

Answer:""",
)


class RAGAgent:
    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
        self.llm = ChatAnthropic(model=model, temperature=0)
        self.vectorstore = Chroma(
            persist_directory=PERSIST_DIR,
            embedding_function=self.embeddings,
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )

    # Indexing
    def upload_pdf(self, pdf_path: str, source_name: str | None = None, conversation_id: int | None = None) -> int:
        """Load a PDF, split it into chunks, and store embeddings in ChromaDB.

        Args:
            pdf_path:        Path to the PDF file on disk.
            source_name:     Display name stored in metadata (defaults to filename).
            conversation_id: Conversation this document belongs to.

        Returns the number of chunks indexed.
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {pdf_path}")
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Expected a .pdf file, got: {path.suffix}")

        loader = PyPDFLoader(str(path))
        pages = loader.load()

        display_name = source_name or path.name
        for page in pages:
            page.metadata["source"] = display_name
            if conversation_id is not None:
                page.metadata["conversation_id"] = conversation_id

        chunks = self.splitter.split_documents(pages)
        self.vectorstore.add_documents(chunks)
        return len(chunks)

    def delete_document(self, source_name: str, conversation_id: int | None = None) -> int:
        """Remove all chunks belonging to a document from ChromaDB.

        If conversation_id is provided, only deletes chunks scoped to that conversation.
        Returns the number of chunks deleted.
        """
        where: dict = {"source": source_name}
        if conversation_id is not None:
            where = {"$and": [{"source": source_name}, {"conversation_id": conversation_id}]}

        results = self.vectorstore.get(where=where)
        ids = results["ids"]
        if ids:
            self.vectorstore.delete(ids=ids)
        return len(ids)

    def delete_conversation_documents(self, conversation_id: int) -> int:
        """Remove all chunks belonging to a conversation from ChromaDB.

        Returns the number of chunks deleted.
        """
        results = self.vectorstore.get(where={"conversation_id": conversation_id})
        ids = results["ids"]
        if ids:
            self.vectorstore.delete(ids=ids)
        return len(ids)

    # Querying
    def stream_query(self, question: str, k: int = 20, conversation_id: int | None = None) -> Generator[dict, None, None]:
        """Retrieve relevant chunks and stream the answer token by token.

        Yields dicts with keys:
          {"type": "status",  "message": str}
          {"type": "chunk",   "text": str}
          {"type": "done",    "sources": list[str]}
          {"type": "error",   "message": str}
        """
        yield {"type": "status", "message": "Searching documents…"}

        search_kwargs: dict = {"k": k}
        if conversation_id is not None:
            search_kwargs["filter"] = {"conversation_id": conversation_id}

        retriever = self.vectorstore.as_retriever(search_kwargs=search_kwargs)
        source_docs = retriever.invoke(question)

        if not source_docs:
            yield {"type": "error", "message": "No relevant documents found. Please upload a PDF first."}
            return

        yield {"type": "status", "message": "Generating answer…"}

        context_parts = []
        for doc in source_docs:
            source = doc.metadata.get("source", "unknown")
            page = doc.metadata.get("page", 0) + 1
            context_parts.append(f"[{source}, page {page}]\n{doc.page_content}")
        context = "\n\n---\n\n".join(context_parts)

        chain = QA_PROMPT | self.llm
        for chunk in chain.stream({"context": context, "question": question}):
            yield {"type": "chunk", "text": chunk.content}

        sources: list[str] = []
        seen: set[str] = set()
        for doc in source_docs:
            meta = doc.metadata
            ref = f"{meta.get('source', 'unknown')}, page {meta.get('page', 0) + 1}"
            if ref not in seen:
                sources.append(ref)
                seen.add(ref)

        yield {"type": "done", "sources": sources}

    # Inspection
    def list_documents(self, conversation_id: int | None = None) -> list[str]:
        """Return a sorted list of indexed document filenames.

        If conversation_id is provided, only returns documents for that conversation.
        """
        where = {"conversation_id": conversation_id} if conversation_id is not None else {}
        data = self.vectorstore.get(where=where or None, include=["metadatas"])
        sources = {m.get("source", "unknown") for m in data["metadatas"]}
        return sorted(sources)

"""
RAG Document Agent — core logic.

Flow:
  upload_pdf(path)  → load → split → embed → persist in ChromaDB
  query(question)   → retrieve relevant chunks → generate answer via Claude
"""

from pathlib import Path

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

load_dotenv()

PERSIST_DIR = "./chroma_db"
EMBED_MODEL = "all-MiniLM-L6-v2"  # free, runs locally, no API key needed

QA_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template="""Answer the question using only the context below.
If the context does not contain enough information, say so clearly.

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
    def upload_pdf(self, pdf_path: str) -> int:
        """Load a PDF, split it into chunks, and store embeddings in ChromaDB.

        Returns the number of chunks indexed.
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {pdf_path}")
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Expected a .pdf file, got: {path.suffix}")

        loader = PyPDFLoader(str(path))
        pages = loader.load()

        # Attach the filename so we can show it as a source reference later
        for page in pages:
            page.metadata.setdefault("source", path.name)

        chunks = self.splitter.split_documents(pages)
        self.vectorstore.add_documents(chunks)
        return len(chunks)

    # Querying

    def query(self, question: str, k: int = 4) -> dict:
        """Retrieve relevant chunks and generate an answer with source refs.

        Returns:
            {
                "answer": str,
                "sources": list[str],   # e.g. ["report.pdf, page 3", ...]
            }
        """
        retriever = self.vectorstore.as_retriever(search_kwargs={"k": k})
        source_docs = retriever.invoke(question)

        if not source_docs:
            return {
                "answer": "No relevant documents found. Please upload a PDF first.",
                "sources": [],
            }

        # builds context string with inline source labels
        context_parts = []
        for doc in source_docs:
            source = doc.metadata.get("source", "unknown")
            page = doc.metadata.get("page", 0) + 1  # PyPDF uses 0-based page index
            context_parts.append(f"[{source}, page {page}]\n{doc.page_content}")
        context = "\n\n---\n\n".join(context_parts)

        # Generate answer via Claude
        chain = QA_PROMPT | self.llm | StrOutputParser()
        answer = chain.invoke({"context": context, "question": question})

        # Deduplicate source references preserving order
        sources: list[str] = []
        seen: set[str] = set()
        for doc in source_docs:
            meta = doc.metadata
            ref = f"{meta.get('source', 'unknown')}, page {meta.get('page', 0) + 1}"
            if ref not in seen:
                sources.append(ref)
                seen.add(ref)

        return {"answer": answer, "sources": sources}

    # Inspection
    def list_documents(self) -> list[str]:
        """Return a sorted list of indexed document filenames."""
        data = self.vectorstore.get(include=["metadatas"])
        sources = {m.get("source", "unknown") for m in data["metadatas"]}
        return sorted(sources)

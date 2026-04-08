# RAG Document Assistant

> Upload your PDF documents and have a conversation with them. Powered by **Claude** and **LangChain**, with answers that cite the exact source and page number.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal?logo=fastapi&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-0.3+-green?logo=chainlink&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5+-purple?logo=databricks&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-Sonnet_4.6-orange?logo=anthropic&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

<!-- Replace the line below with your actual screenshot or GIF once recorded -->
![Demo](demo.gif)

---

## Features

- **Conversation history** saved automatically in SQLite, persisted across sessions
- **Documents scoped per chat** so files uploaded in one conversation never affect another
- **Search and Summarize modes**: switch between targeted fact retrieval and full document summarization
- **Semantic search** using local embeddings, no extra API key needed
- **Source references** on every answer, with document name and page number
- **Streaming responses** from Claude, shown token by token in the browser

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | [Claude Sonnet 4.6](https://www.anthropic.com/) (Anthropic) |
| Web framework | [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn |
| RAG framework | [LangChain](https://www.langchain.com/) |
| Vector database | [ChromaDB](https://www.trychroma.com/) (persisted locally) |
| Embeddings | [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) (runs locally) |
| Conversation storage | SQLite via the Python standard library |
| PDF parsing | [PyPDF](https://pypdf.readthedocs.io/) |
| Frontend animations | [GSAP](https://gsap.com/) with ScrollTrigger |

---

## How It Works

```
PDF upload
    ↓
PyPDFLoader extracts text per page
    ↓
RecursiveCharacterTextSplitter splits into overlapping chunks
    ↓
all-MiniLM-L6-v2 embeds each chunk locally
    ↓
ChromaDB stores embeddings tagged with the conversation ID
    ↓
User question → top k chunks retrieved (k=20 in Search, k=100 in Summarize)
    ↓
Claude Sonnet 4.6 generates an answer with source citations, streamed to the browser
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/)

### Installation

```bash
git clone <repo-url>
cd rag-document-agent

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
```

Open `.env` and add your API key:

```
ANTHROPIC_API_KEY=your_api_key_here
```

### Run

**Web interface**

```bash
uvicorn server:app --reload
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

**Terminal (CLI)**

```bash
python main.py
```

---

## Usage

### Web interface

1. Click **New chat** in the sidebar to start a fresh conversation
2. Click the **+** button next to the input field to upload a PDF
3. Switch between **Search** and **Summarize** mode depending on what you need
4. Ask questions in plain language and get answers with page references
5. Previous conversations are listed in the sidebar and can be resumed at any time

### CLI

```
> upload path/to/document.pdf
[Indexed 87 chunks from 'document.pdf'.]

> ask What are the main conclusions?
[Searching documents...]
[Generating answer...]
The main conclusions are ...

Sources:
  * document.pdf, page 12
  * document.pdf, page 34

> summarize Give me an overview of the whole document
[Searching documents...]
[Generating answer...]
...

> list
Indexed documents:
  * document.pdf

> remove document.pdf
Removed 87 chunks for 'document.pdf'.

> quit
Goodbye!
```

| Command | Description |
|---|---|
| `upload <path>` | Index a PDF file |
| `ask <question>` | Search with targeted retrieval (k=20) |
| `summarize <question>` | Query with full document coverage (k=100) |
| `list` | Show all indexed documents |
| `remove <filename>` | Remove a document and its embeddings |
| `quit` | Exit |

---

## Configuration

Key constants in `rag_agent.py`:

| Constant | Default | Description |
|---|---|---|
| `PERSIST_DIR` | `./chroma_db` | Where ChromaDB stores embeddings |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Local embedding model |
| `chunk_size` | `1000` | Characters per chunk |
| `chunk_overlap` | `200` | Overlap between chunks |

Chunks retrieved per query in `server.py`:

| Mode | k | Best for |
|---|---|---|
| Search | 20 | Specific questions and fact lookup |
| Summarize | 100 | Overviews and chapter summaries |

---

## Notes

- The embedding model (~90 MB) is downloaded from HuggingFace on first run and cached locally
- On macOS, grant your terminal access to folders via `System Settings → Privacy & Security → Files and Folders` if you get permission errors when uploading PDFs

---

## License

MIT

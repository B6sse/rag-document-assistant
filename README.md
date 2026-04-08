# 📄 RAG Document Assistant

> Upload your PDF documents and ask questions about them in plain English — powered by **Claude** and **LangChain**, with answers that cite the exact source and page number.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1.2-green?logo=chainlink&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-1.5-purple?logo=databricks&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-Sonnet_4.6-orange?logo=anthropic&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

<!-- Replace the line below with your actual GIF once recorded -->
![Demo](demo.gif)

---

## Features

- **Upload multiple PDFs** — index as many documents as you need
- **Ask in plain English** — no special syntax required
- **Source references** — every answer cites the document name and page number
- **Persistent storage** — documents are remembered between sessions via ChromaDB
- **Local embeddings** — no extra API key needed for embedding

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | [Claude Sonnet 4.6](https://www.anthropic.com/) (Anthropic) |
| RAG framework | [LangChain](https://www.langchain.com/) |
| Vector database | [ChromaDB](https://www.trychroma.com/) (persisted locally) |
| Embeddings | [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) (runs locally) |
| PDF parsing | [PyPDF](https://pypdf.readthedocs.io/) |

---

## How It Works

```
PDF file
    │
    ▼
PyPDFLoader — extract text per page
    │
    ▼
RecursiveCharacterTextSplitter — split into overlapping chunks
    │
    ▼
all-MiniLM-L6-v2 — embed each chunk locally
    │
    ▼
ChromaDB — persist embeddings to disk
    │
    ▼
User question → retrieve top-4 relevant chunks
    │
    ▼
Claude Opus 4.6 — generate answer with source references
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

```bash
python main.py
```

---

## Usage

| Command | Description |
|---|---|
| `upload <path>` | Index a PDF file |
| `ask <question>` | Ask a question across all indexed documents |
| `list` | Show all indexed documents |
| `quit` | Exit |

### Example session

```
> upload reports/annual_report.pdf
Indexed 124 chunks from 'annual_report.pdf'.

> ask What was the total revenue in 2023?
Total revenue in 2023 was $4.2 billion, representing a 12% increase from the prior year.

Sources:
  • annual_report.pdf, page 8
  • annual_report.pdf, page 23

> list
Indexed documents:
  • annual_report.pdf

> quit
Goodbye!
```

---

## Project Structure

```
rag-document-agent/
├── rag_agent.py      # Core RAG logic (RAGAgent class)
├── main.py           # Interactive CLI
├── requirements.txt
├── .env.example
└── chroma_db/        # Vector database (created on first upload, gitignored)
```

---

## Configuration

Key constants in `rag_agent.py`:

| Constant | Default | Description |
|---|---|---|
| `PERSIST_DIR` | `./chroma_db` | Where ChromaDB stores data |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Local embedding model |
| `chunk_size` | `1000` | Characters per chunk |
| `chunk_overlap` | `200` | Overlap between chunks |
| `k` (in `query`) | `4` | Number of chunks retrieved per query |

The Claude model can be swapped when instantiating `RAGAgent`:

```python
agent = RAGAgent(model="claude-sonnet-4-6")
```

---

## Notes

- The embedding model (~90 MB) is downloaded from HuggingFace on first run and cached locally — subsequent runs are instant
- On macOS, grant your terminal access to folders via `System Settings → Privacy & Security → Files and Folders` if you get permission errors when uploading

---

## License

MIT

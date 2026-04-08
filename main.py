"""
Interactive CLI for the RAG Document Assistant.

Commands:
  upload <path/to/file.pdf>   Index a PDF into ChromaDB
  ask <your question>         Query across all indexed documents
  list                        Show indexed documents
  quit / exit                 Exit
"""

from rag_agent import RAGAgent


def print_help() -> None:
    print("Commands:")
    print("  upload <path>   — index a PDF")
    print("  ask <question>  — query indexed documents")
    print("  list            — show indexed documents")
    print("  quit            — exit")


def main() -> None:
    print("RAG Document Assistant (Claude + ChromaDB)")
    print("=" * 45)
    print_help()

    try:
        agent = RAGAgent()
    except Exception as e:
        print(f"\nFailed to initialize agent: {e}")
        print("Make sure ANTHROPIC_API_KEY is set in your .env file.")
        return

    while True:
        try:
            raw = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not raw:
            continue

        parts = raw.split(" ", 1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("quit", "exit"):
            print("Goodbye!")
            break

        elif cmd == "upload":
            if not arg:
                print("Usage: upload <path/to/file.pdf>")
                continue
            try:
                n = agent.upload_pdf(arg)
                print(f"Indexed {n} chunks from '{arg}'.")
            except (FileNotFoundError, ValueError) as e:
                print(f"Error: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")

        elif cmd == "ask":
            if not arg:
                print("Usage: ask <your question>")
                continue
            try:
                result = agent.query(arg)
                print(f"\n{result['answer']}")
                if result["sources"]:
                    print("\nSources:")
                    for src in result["sources"]:
                        print(f"  • {src}")
            except Exception as e:
                print(f"Error: {e}")

        elif cmd == "list":
            docs = agent.list_documents()
            if docs:
                print("Indexed documents:")
                for doc in docs:
                    print(f"  • {doc}")
            else:
                print("No documents indexed yet. Use 'upload <path>' to add one.")

        elif cmd in ("help", "?"):
            print_help()

        else:
            print(f"Unknown command '{cmd}'. Type 'help' for usage.")


if __name__ == "__main__":
    main()

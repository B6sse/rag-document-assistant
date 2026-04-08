"""
Interactive CLI for the RAG Document Assistant.

Commands:
  upload <path/to/file.pdf>   Index a PDF into ChromaDB
  ask <your question>         Query across all indexed documents
  summarize <your question>   Query with full document coverage (k=100)
  list                        Show indexed documents
  remove <filename>           Remove a document
  quit / exit                 Exit
"""

from rag_agent import RAGAgent


def print_help() -> None:
    print("Commands:")
    print("  upload <path>        index a PDF")
    print("  ask <question>       search indexed documents")
    print("  summarize <question> summarize with full document coverage")
    print("  list                 show indexed documents")
    print("  remove <filename>    remove a document")
    print("  quit                 exit")


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

        elif cmd in ("ask", "summarize"):
            if not arg:
                print(f"Usage: {cmd} <your question>")
                continue
            k = 100 if cmd == "summarize" else 20
            try:
                print()
                for event in agent.stream_query(arg, k=k):
                    if event["type"] == "status":
                        print(f"[{event['message']}]", flush=True)
                    elif event["type"] == "chunk":
                        print(event["text"], end="", flush=True)
                    elif event["type"] == "done":
                        print("\n")
                        if event["sources"]:
                            print("Sources:")
                            for src in event["sources"]:
                                print(f"  * {src}")
                    elif event["type"] == "error":
                        print(f"\nError: {event['message']}")
            except Exception as e:
                print(f"Error: {e}")

        elif cmd == "list":
            docs = agent.list_documents()
            if docs:
                print("Indexed documents:")
                for doc in docs:
                    print(f"  * {doc}")
            else:
                print("No documents indexed yet. Use 'upload <path>' to add one.")

        elif cmd == "remove":
            if not arg:
                print("Usage: remove <filename>")
                continue
            deleted = agent.delete_document(arg)
            if deleted:
                print(f"Removed {deleted} chunks for '{arg}'.")
            else:
                print(f"No document found with name '{arg}'.")

        elif cmd in ("help", "?"):
            print_help()

        else:
            print(f"Unknown command '{cmd}'. Type 'help' for usage.")


if __name__ == "__main__":
    main()

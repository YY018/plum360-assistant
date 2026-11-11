"""Run the LangGraph-driven advisory agent against the local manual index."""

from __future__ import annotations

import argparse
import json

from plum360_assistant.agent import build_agent_graph
from plum360_assistant.config import load_settings
from plum360_assistant.llm import create_chat_model
from plum360_assistant.vector_store import create_chroma_store, create_gemini_embeddings


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Plum 360 manual LangGraph agent.")
    parser.add_argument("question", help="Question to answer using the indexed manual.")
    parser.add_argument("--collection", default="plum360_manual", help="Manual collection name.")
    args = parser.parse_args()

    settings = load_settings()
    embeddings = create_gemini_embeddings(settings)
    vector_store = create_chroma_store(settings, embeddings, collection_name=args.collection)
    graph = build_agent_graph(vector_store, create_chat_model(settings))
    result = graph.invoke({"question": args.question, "conversation_history": []})
    print(json.dumps({
        "question": result["question"],
        "relevance_assessment": result.get("relevance_assessment"),
        "generated_answer": result.get("generated_answer"),
        "source_references": result.get("source_references", []),
        "verification_result": result.get("verification_result"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

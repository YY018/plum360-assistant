"""LangGraph workflow for the Plum 360 manual agent."""

from __future__ import annotations

import re
from typing import Any

from langchain_chroma import Chroma
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from plum360_assistant.agent.router import (
    CONVERSATION,
    FALLBACK_GREETING,
    MANUAL,
    ROUTER_PROMPT,
    classify_heuristically,
    conversation_messages,
    format_history,
    message_text,
    parse_route,
)
from plum360_assistant.agent.state import AgentState
from plum360_assistant.agent.tools import (
    retrieve_document_context_factory,
    search_by_alarm_code_factory,
    search_by_section_factory,
    search_manual_factory,
    verify_answer_factory,
)


def _tool_name_for_question(question: str) -> str:
    lowered = question.lower()
    if re.search(r"\b[a-z]?\d{3,4}\b", lowered):
        return "search_by_alarm_code"
    if "section" in lowered:
        return "search_by_section"
    return "search_manual"


def _keyword_overlap(question: str, result_text: str) -> int:
    question_tokens = {
        token for token in re.findall(r"[a-z0-9]+", question.lower()) if len(token) > 2
    }
    result_tokens = {
        token for token in re.findall(r"[a-z0-9]+", result_text.lower()) if len(token) > 2
    }
    return len(question_tokens & result_tokens)


def _default_answer(results: list[dict[str, Any]]) -> str:
    if not results:
        return (
            "The manual does not provide enough supported information to answer this "
            "question. Please consult the official Plum 360 System Operating Manual "
            "and qualified clinical guidance."
        )

    excerpts = []
    for index, result in enumerate(results[:3], start=1):
        text = (result.get("text") or "").strip()
        pages = result.get("page_numbers") or []
        page_text = (
            f"pages {', '.join(str(page) for page in pages)}"
            if pages
            else "manual excerpt"
        )
        excerpts.append(f"{index}. {text}\nSource: {result.get('source', 'manual')} ({page_text}).")

    return (
        "Based on the indexed Plum 360 System Operating Manual, the most relevant "
        "manual passages are:\n\n" + "\n\n".join(excerpts)
    )


def _alarm_evidence(
    results: list[dict[str, Any]], alarm_code: str | None
) -> list[dict[str, Any]]:
    if not alarm_code:
        return results[:5]

    focused: list[dict[str, Any]] = []
    code_pattern = re.compile(r"\b[A-Z]\d{2,4}\b", re.IGNORECASE)
    target_pattern = re.compile(rf"\b{re.escape(alarm_code)}\b", re.IGNORECASE)
    for result in results:
        lines = (result.get("text") or "").splitlines()
        target_index = next(
            (index for index, line in enumerate(lines) if target_pattern.search(line)),
            None,
        )
        if target_index is None:
            continue

        next_code_index = next(
            (
                index
                for index in range(target_index + 1, len(lines))
                if code_pattern.search(lines[index])
            ),
            len(lines),
        )
        end_index = max(target_index + 1, next_code_index - 2)
        focused.append({
            **result,
            "text": "\n".join(lines[max(0, target_index - 2):end_index]).strip(),
        })

    return focused or results[:5]


def _alarm_actions(
    results: list[dict[str, Any]], alarm_code: str | None
) -> list[str]:
    if not alarm_code:
        return []

    action_pattern = re.compile(
        r"\b(?:Acknowledge|Backprime|Check|Clear|Close|Connect|Disconnect|"
        r"Enter|Examine|Follow|Keep|Lower|Open|Plug|Power off|Press|Reprogram|"
        r"Remove|Replace|Resolve|Restart|See|Select|Stop|Use)\b[^.!?]*[.!?]",
        re.IGNORECASE,
    )
    actions: list[str] = []
    for result in _alarm_evidence(results, alarm_code):
        text = result.get("text") or ""
        code_match = re.search(rf"\b{re.escape(alarm_code)}\b", text, re.IGNORECASE)
        if not code_match:
            continue
        after_code = text[code_match.end():]
        for match in action_pattern.finditer(after_code):
            action = " ".join(match.group().split())
            if action.casefold() not in {existing.casefold() for existing in actions}:
                actions.append(action)
    return actions


def _include_complete_alarm_actions(
    answer: str, results: list[dict[str, Any]], alarm_code: str | None
) -> str:
    actions = _alarm_actions(results, alarm_code)
    if not actions:
        return answer

    meaning = answer.partition("Manual-listed action:")[0].strip()
    meaning = re.sub(r"^Meaning:\s*", "", meaning, flags=re.IGNORECASE)
    return f"Meaning: {meaning}\nManual-listed action: {' '.join(actions)}"


def build_agent_graph(vector_store: Chroma, llm: BaseChatModel | None = None) -> Any:
    """Create a LangGraph workflow for manual-grounded question answering."""
    search_manual = search_manual_factory(vector_store)
    search_by_alarm_code = search_by_alarm_code_factory(vector_store)
    search_by_section = search_by_section_factory(vector_store)
    retrieve_document_context = retrieve_document_context_factory(vector_store)
    verify_answer = verify_answer_factory()

    def receive_question(state: AgentState) -> AgentState:
        question = (state.get("question") or "").strip()
        return {
            **state,
            "question": question,
            "retrieval_results": [],
            "relevance_assessment": "",
            "generated_answer": "",
            "source_references": [],
            "verification_result": "",
            "retry_count": 0,
            "answer_supported": False,
            "tool_name": "",
            "conversation_history": list(state.get("conversation_history") or []),
            "chat_history": list(state.get("chat_history") or []),
            "route": "",
        }

    def route_intent(state: AgentState) -> AgentState:
        question = state["question"]
        route = classify_heuristically(question)
        if route is None:
            if llm is None:
                route = MANUAL
            else:
                try:
                    reply = llm.invoke(ROUTER_PROMPT.format(
                        history=format_history(state.get("chat_history") or []),
                        question=question,
                    ))
                    route = parse_route(message_text(reply))
                except Exception:
                    # If routing fails, the grounded manual path is the safe default.
                    route = MANUAL
        return {**state, "route": route}

    def respond_conversationally(state: AgentState) -> AgentState:
        if llm is None:
            answer = FALLBACK_GREETING
        else:
            response = llm.invoke(conversation_messages(
                state["question"], state.get("chat_history") or []
            ))
            answer = message_text(response) or FALLBACK_GREETING
        return {
            **state,
            "generated_answer": answer,
            "source_references": [],
            "answer_supported": True,
            "verification_result": "conversational reply; no manual evidence used",
        }

    def analyze_question(state: AgentState) -> AgentState:
        question = state["question"]
        return {**state, "tool_name": _tool_name_for_question(question)}

    def select_tool(state: AgentState) -> AgentState:
        return state

    def retrieve_manual_information(state: AgentState) -> AgentState:
        question = state["question"]
        tool_name = state["tool_name"]
        if tool_name == "search_by_alarm_code":
            match = re.search(r"\b([A-Za-z]\d{2,4})\b", question, re.IGNORECASE)
            alarm_code = match.group(1).upper() if match else question.strip()
            payload = search_by_alarm_code.invoke({"alarm_code": alarm_code, "top_k": 3})
        elif tool_name == "search_by_section":
            section_name = re.search(r"section\s*[:\-]?\s*([A-Za-z0-9 ]+)", question, re.IGNORECASE)
            section = section_name.group(1).strip() if section_name else ""
            payload = search_by_section.invoke({
                "section": section or "Alarms",
                "query": question,
                "top_k": 3,
            })
        else:
            payload = search_manual.invoke({"query": question, "top_k": 3})

        results = payload.get("results", [])
        if not results and "alarm" in question.lower():
            payload = search_manual.invoke({"query": f"{question} alarm details", "top_k": 3})
            results = payload.get("results", [])
        return {
            **state,
            "retrieval_results": results,
            "retrieved_documents": [result.get("text", "") for result in results],
        }

    def assess_relevance(state: AgentState) -> AgentState:
        results = state.get("retrieval_results") or []
        question = state.get("question") or ""
        overlaps = [_keyword_overlap(question, str(result.get("text") or "")) for result in results]
        if not results or max(overlaps, default=0) == 0:
            assessment = "insufficient"
        else:
            assessment = "sufficient"
        return {**state, "relevance_assessment": assessment}

    def should_refine_search(state: AgentState) -> str:
        if state.get("relevance_assessment") == "insufficient":
            if state.get("retry_count", 0) < 2:
                return "refine"
            return "abstain"
        return "answer"

    def refine_search(state: AgentState) -> AgentState:
        retry_count = state.get("retry_count", 0) + 1
        question = state["question"]
        expanded = question
        if "alarm" not in question.lower():
            expanded = f"{question} Plum 360 manual"
        if retry_count == 1:
            tool_name = "retrieve_document_context"
            payload = retrieve_document_context.invoke({"query": expanded, "top_k": 3})
        else:
            tool_name = "search_manual"
            payload = search_manual.invoke({"query": expanded, "top_k": 5})
        return {
            **state,
            "retry_count": retry_count,
            "tool_name": tool_name,
            "retrieval_results": payload.get("results", []),
            "retrieved_documents": [item.get("text", "") for item in payload.get("results", [])],
        }

    def generate_grounded_answer(state: AgentState) -> AgentState:
        results = state.get("retrieval_results") or []
        if llm is None:
            answer = _default_answer(results)
        else:
            alarm_match = re.search(
                r"\b([A-Za-z]\d{2,4})\b", state.get("question", "")
            )
            answer_evidence = _alarm_evidence(
                results, alarm_match.group(1).upper() if alarm_match else None
            )
            evidence = "\n\n".join(
                f"[{index}] {result.get('text', '').strip()}"
                for index, result in enumerate(answer_evidence, start=1)
            )
            prompt = (
                "You are a concise Plum 360 System Operating Manual reference "
                "assistant. Summarize directly in 2-4 sentences using only the "
                "supplied manual excerpts. For an alarm question, report its "
                "priority and meaning/cause, then give the complete corrective "
                "action for that exact alarm. Copy every corrective-action sentence "
                "for that alarm; do not omit a follow-up action or mix in actions "
                "from neighboring alarm entries. Format alarm answers on two lines "
                "as 'Meaning:' and 'Manual-listed action:'. Do not invent steps, "
                "add clinical advice, or make a clinical or device-use decision. If "
                "the excerpts do not support an answer, say that the manual excerpts "
                "are insufficient. The answer is a summary, not a replacement for "
                "the official manual or facility procedure.\n\n"
                f"Question: {state.get('question', '')}\n\n"
                f"Manual excerpts:\n{evidence}"
            )
            answer = message_text(llm.invoke(prompt))
            if not answer:
                raise RuntimeError("The Gemini model returned an empty answer.")
            if alarm_match:
                answer = _include_complete_alarm_actions(
                    answer, results, alarm_match.group(1).upper()
                )
        references = []
        for result in results[:3]:
            source = result.get("source", "manual")
            pages = result.get("page_numbers") or []
            page_text = (
                f"pages {', '.join(str(page) for page in pages)}"
                if pages
                else "manual excerpt"
            )
            references.append(f"{source} ({page_text})")
        return {
            **state,
            "generated_answer": answer,
            "source_references": references,
        }

    def verify_answer_support(state: AgentState) -> AgentState:
        verification = verify_answer.invoke({
            "answer": state.get("generated_answer", ""),
            "source_references": state.get("source_references", []),
        })
        supported = bool(verification.get("supported"))
        return {
            **state,
            "verification_result": verification.get("reason", "unsupported"),
            "answer_supported": supported,
        }

    def revise_or_abstain(state: AgentState) -> AgentState:
        if state.get("answer_supported"):
            return state
        return {
            **state,
            "generated_answer": (
                "The manual does not provide enough supported information to answer this "
                "question. Please consult the official Plum 360 System Operating Manual "
                "and qualified clinical guidance."
            ),
        }

    def return_answer(state: AgentState) -> AgentState:
        return state

    graph = StateGraph(AgentState)
    graph.add_node("receive_question", receive_question)
    graph.add_node("route_intent", route_intent)
    graph.add_node("respond_conversationally", respond_conversationally)
    graph.add_node("analyze_question", analyze_question)
    graph.add_node("select_tool", select_tool)
    graph.add_node("retrieve_manual_information", retrieve_manual_information)
    graph.add_node("assess_relevance", assess_relevance)
    graph.add_node("refine_search", refine_search)
    graph.add_node("generate_grounded_answer", generate_grounded_answer)
    graph.add_node("verify_answer", verify_answer_support)
    graph.add_node("revise_or_abstain", revise_or_abstain)
    graph.add_node("return_answer", return_answer)

    graph.add_edge(START, "receive_question")
    graph.add_edge("receive_question", "route_intent")
    graph.add_conditional_edges(
        "route_intent",
        lambda state: state.get("route", MANUAL),
        {CONVERSATION: "respond_conversationally", MANUAL: "analyze_question"},
    )
    graph.add_edge("respond_conversationally", "return_answer")
    graph.add_edge("analyze_question", "select_tool")
    graph.add_edge("select_tool", "retrieve_manual_information")
    graph.add_edge("retrieve_manual_information", "assess_relevance")
    graph.add_conditional_edges(
        "assess_relevance",
        should_refine_search,
        {
            "refine": "refine_search",
            "answer": "generate_grounded_answer",
            "abstain": "revise_or_abstain",
        },
    )
    graph.add_edge("refine_search", "retrieve_manual_information")
    graph.add_edge("generate_grounded_answer", "verify_answer")
    graph.add_conditional_edges(
        "verify_answer",
        lambda state: "revise" if not state.get("answer_supported") else "return",
        {"revise": "revise_or_abstain", "return": "return_answer"},
    )
    graph.add_edge("revise_or_abstain", "return_answer")
    graph.add_edge("return_answer", END)
    return graph.compile()

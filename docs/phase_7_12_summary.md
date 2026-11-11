# Phases 7–12 completion summary

## Phase 7 — Conversation memory
- Added a bounded `ConversationMemory` helper that keeps recent chat turns in order.
- The Streamlit app now persists conversation history and reuses it for the active session.

## Phase 8 — FastAPI backend
- Added a minimal FastAPI API backend in `backend/main.py`.
- Endpoints include `/health` and `/chat` for direct question handling.

## Phase 9 — React frontend
- Added a lightweight React + Vite frontend in `frontend/`.
- The UI posts questions to the backend and renders the answer with citations.

## Phase 10 — Evaluation and testing
- Added evaluation questions in `evaluation/questions.json`.
- Added a manual QA evaluator in `scripts/evaluate_manual.py`.
- Added targeted tests covering memory and safety behavior.

## Phase 11 — Safety and reliability
- Added safety validation checks before answering user queries.
- Responses are rejected when the request tries to direct pump programming or dosing.

## Phase 12 — Documentation and GitHub portfolio
- Updated the main project documentation to reflect the completed phases.
- The project is structured for portfolio-friendly demo use and future extension.

# Plum 360 Assistant — Project Progress

**Last updated:** 2026-11-11

## Product scope

- Reference information from the Plum 360 System Operating Manual (IFU0000340).
- No pump connection and no patient data. Not a medical device; the UI states
  this on every screen.

## Manual pipeline

- 268-page manual extracted with page metadata; 103 chunks (900 tokens, 120
  overlap) indexed in Chroma with Gemini `gemini-embedding-001`.
- Retrieval is hybrid: vector similarity fused with BM25 keyword ranking. Each
  list's top match is always kept, which fixed misses on exact manual terms.
- Printed page labels (for example `11-6`) are mapped to PDF pages so the
  product guide and the chat can open the cited page.

## Assistant

- LangGraph agent: safety check, intent routing (rules first, LLM for unclear
  messages), retrieval with retries, grounded answer, source verification,
  abstention when unsupported.
- Answers come from Groq (`openai/gpt-oss-120b`, with Qwen and gpt-oss-20b
  fallbacks) and fall back to Gemini chat models. Reasoning output is hidden
  and kept low for speed; time to first token is about one second.
- FastAPI streams status, tokens, and the final answer with structured sources
  as NDJSON. The API is stateless; clients send their own history.

## Frontend

- Product guide with features, manual diagrams, set-up steps, alarm levels,
  care, and specifications; every fact links to its manual page.
- Chat as a slide-in drawer (full screen on phones) or a full page, with
  streaming, a Stop button, and a page viewer for citations.

## Verification

- 59 unit and integration tests pass.
- End-to-end evaluation: 25/26 questions pass (96%); see
  `evaluation/results/latest.md`.

## Known limits

- Groq's free tier allows about 8,000 tokens per minute; bursts of questions
  wait for the limit to reset (the client retries automatically).
- Gemini's free tier allows about 20 chat requests per model per day.

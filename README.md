# Plum 360 Assistant

A product guide and AI assistant for the **Plum 360 infusion pump**, grounded in
its 268-page System Operating Manual. Every answer cites the manual pages it
came from, and those pages open right in the app.

> Independent reference project. Not affiliated with ICU Medical. Not a medical
> device: do not use it for dosing, programming, or alarm response decisions.

## What it does

- **Product guide.** A one-page overview of the infuser: key facts, features,
  diagrams from the manual, set-up steps, alarm priorities, care, and
  specifications. Each fact shows its manual page (for example *Manual 11-6*),
  and clicking it opens that page.
- **Chat assistant.** Opens as a side drawer from any "Ask" link or the
  *Ask about Plum 360* button, or as a full page at `#/assistant`. Answers
  stream in word by word, show live progress ("Searching the manual",
  "Reading the relevant pages"), and list their sources; each source opens the
  cited page.
- **Knows when to search.** Greetings, thanks, and "explain that more simply"
  are answered conversationally. Device questions always go to the manual and
  are never answered from the model's general knowledge.
- **Safe by default.** Requests to program the pump or dose a patient are
  refused before reaching the model. When the manual doesn't support an
  answer, the assistant says so instead of guessing.

## How it works

```
question ─► safety check ─► intent router ─┬─► conversational reply (LLM)
                                           └─► manual search ─► relevance check ─► answer (LLM) ─► source check
                                                (hybrid: vector + BM25, retries)        │
                                                                                       ▼
                                                                    streamed answer + page citations
```

| Layer | Technology |
|---|---|
| Agent workflow | LangGraph (`plum360_assistant/agent/`) |
| Retrieval | Chroma + local `BAAI/bge-small-en-v1.5` embeddings (fastembed), fused with BM25 keyword and phrase ranking |
| Answers | Groq `openai/gpt-oss-120b` with fallbacks (`qwen/qwen3.8-27b`, `openai/gpt-oss-20b`); Gemini optional |
| API | FastAPI, NDJSON streaming (`backend/main.py`) |
| Frontend | React + Vite (`frontend/`) |
| Manual pages | PyMuPDF renders cited pages and figures from the local PDF |

## Evaluation

`python -m scripts.evaluate_manual` runs 26 questions through the full
pipeline and checks routing, whether the expected manual page was retrieved,
whether the answer contains the expected facts, off-topic handling, and safety
refusals. Latest run:

| Check | Result |
|---|---|
| Routing (manual vs. conversation) | 23/23 |
| Retrieval (expected page cited) | 18/20 |
| Facts (answer contains expected values) | 18/20 |
| Small talk without citations | 3/3 |
| Off-topic declined | 1/1 |
| Unsafe requests refused | 2/2 |
| **Overall** | **24/26 (92%)** |

This run uses Groq for answers and local embeddings for search, with no Gemini
calls. The full report is in [evaluation/results/latest.md](evaluation/results/latest.md).

Retrieval notes: vector search alone found the right page in the top 3 for
9 of 16 probe questions with the local model; fusing BM25 keyword ranking
raised that to 14, and adding two-word phrase terms to 18 of 20 on a wider
set. Both remaining misses are values in the dense specifications table
(manual 11-6); for one the assistant declined instead of guessing, for the
other it gave an imprecise lower bound. (With Gemini embeddings the same
pipeline scored 25/26.)

## Setup

Python 3.11+ and Node 18+. From the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
cd frontend; npm install; cd ..
```

In `.env`, set `GROQ_API_KEY` (free at console.groq.com). That is the only
key needed: manual search runs locally, and its model (about 130 MB) downloads
once into `data/models/`. `GEMINI_API_KEY` is optional; see `.env.example`.

See [.env.example](.env.example) for model choices and other options.
Never commit `.env`.

### Manual data (private)

The manual PDF must be lawfully obtained and kept private. Put it in
`data/raw/manuals/` (or set `MANUAL_PDF_PATH`), then build the index and
figures once:

```powershell
python -m scripts.extract_documents data\raw\manuals\plum_360_som_pn-ifu0000340_21658851.pdf --document-id plum360_manual
python -m scripts.chunk_documents data/processed/plum360_manual.json
python -m scripts.index_chunks data/processed/plum360_manual_chunks.json
python -m scripts.export_manual_figures
```

`data/` and the exported figures are git-ignored because they contain
copyrighted manual content. With local embeddings, manual text and search
queries stay on this machine; only the question and the retrieved excerpts are
sent to Groq to write the answer.

## Run

```powershell
# Terminal 1: API
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: frontend
cd frontend; npm run dev
```

Open http://localhost:5173. Restart the API after editing `.env`; `--reload`
only watches Python files. A Streamlit version of the chat is also available
with `streamlit run app.py`.

Optional: place a product photo you hold the rights to at
`frontend/public/product/hero.jpg` to replace the illustration on the guide.

## Publishing a demo safely

The Groq key stays on the server; the browser only ever talks to the FastAPI
backend. On top of that, `backend/guard.py` limits what the public can spend:
questions per client per hour (`RATE_LIMIT_PER_HOUR`, default 30), questions
per day for everyone (`DAILY_REQUEST_BUDGET`, default 400), question length
(`MAX_QUESTION_CHARS`), and an optional `DEMO_ACCESS_CODE` so only people with
your link (`?code=...`) can ask. Refused (unsafe) questions never reach a model
and don't count. `GET /limits` shows today's usage.

## Deploy for free (Hugging Face Spaces)

One command builds a Docker Space that serves the site and the API from one
URL, with the manual data kept in a private dataset (never in the public
Space). You need a Hugging Face account and a write token from
https://huggingface.co/settings/tokens.

```powershell
$env:HF_TOKEN = "hf_..."
python -m scripts.deploy_hf_space --owner YOUR_HF_USERNAME
```

The Space builds for a few minutes and then runs at
`https://YOUR_HF_USERNAME-plum360-assistant.hf.space`. Secrets (Groq key,
access code) and limits are copied from your local `.env`. Set
`DEMO_ACCESS_CODE` in `.env` before deploying if you want the demo gated;
the link to share is then `https://...hf.space/?code=YOUR_CODE`.
Re-run the command to redeploy; add `--skip-data` when only code changed.

## Tests

```powershell
python -m unittest discover -s tests
```

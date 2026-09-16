# UB There — Agentic AI Assistant

A university student assistant: a LangChain agent answers policy questions using RAG over
university documents (LlamaIndex + ChromaDB), served by FastAPI with a React chat UI.

```
React (Vite)  ──HTTP──>  FastAPI  ──>  LangChain agent
                                            │
                                            └──> LlamaIndex query engine ──> ChromaDB
                                                          │
                                       Ollama (free, local)  or  OpenAI (paid API)
```

Documents go in **`upload uni info here/`**. The provider is chosen by `LLM_PROVIDER` in
`backend/.env` — `ollama` (default, free) or `openai`.

**New here? See [RUNNING.md](RUNNING.md)** for step-by-step setup and troubleshooting.

## Prerequisites

- Python 3.11+
- Node.js 18+
- Ollama (free, local, default) — or an OpenAI API key to use the paid provider instead

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Copy-Item .env.example .env   # defaults to the free local provider

.\.venv\Scripts\python.exe ingest.py    # indexes "upload uni info here/"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Calling `.\.venv\Scripts\python.exe` directly avoids needing to activate the venv. If you prefer
`.\.venv\Scripts\Activate.ps1`, note that PowerShell's default execution policy blocks it — run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once first.

The API runs on http://localhost:8000 — interactive docs at http://localhost:8000/docs.

Quick check:

```powershell
curl.exe http://localhost:8000/api/health
```

## Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open the printed URL (http://localhost:5173).

## Using your documents

Put handbooks (`.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.pptx`) in `upload uni info here/` and re-run
`ingest.py`. Each run rebuilds the collection from scratch, so re-running never duplicates chunks.

## Switching providers

Edit `backend/.env`, set `LLM_PROVIDER=openai` and `OPENAI_API_KEY=...`, re-run `ingest.py`, restart.
Each provider has its own Chroma collection, since embedding dimensions differ — so switching back
later needs no re-indexing.

## Deliberately not built yet

- **PostgreSQL** — no persistence: chat is stateless, with no user profiles, chat history,
  or audit logs. `app/routers/chat.py` is the seam where those writes would be added.
- **OpenCV document/ID auditing** — the upload + image-preprocessing endpoint is a separate
  phase.
- Streaming responses, multi-turn conversation memory, and student authentication.

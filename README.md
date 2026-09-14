# UB There — Agentic AI Assistant

A university student assistant: a LangChain agent answers policy questions using RAG over
university documents (LlamaIndex + ChromaDB), served by FastAPI with a React chat UI.

```
React (Vite)  ──HTTP──>  FastAPI  ──>  LangChain agent
                                            │
                                            └──> LlamaIndex query engine ──> ChromaDB
                                                          │
                                                          └──> OpenAI (gpt-4o)
```

**New here? See [RUNNING.md](RUNNING.md)** for step-by-step setup and troubleshooting.

## Prerequisites

- Python 3.11+
- Node.js 18+
- An OpenAI API key

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Copy-Item .env.example .env   # then edit .env and add your OPENAI_API_KEY

.\.venv\Scripts\python.exe ingest.py    # builds the Chroma index from data/sample_docs
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Calling `.\.venv\Scripts\python.exe` directly avoids needing to activate the venv. If you prefer
`.\.venv\Scripts\Activate.ps1`, note that PowerShell's default execution policy blocks it — run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once first.

The API runs on http://localhost:8000 — interactive docs at http://localhost:8000/docs.

Quick check:

```powershell
curl.exe -X POST localhost:8000/api/chat -H "Content-Type: application/json" `
  -d '{\"message\":\"What is the tuition refund policy if I withdraw in week 3?\"}'
```

## Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open the printed URL (http://localhost:5173).

## Using real documents

`backend/data/sample_docs/` contains three placeholder policy files so the pipeline is
testable out of the box. Replace them with real handbooks (`.txt`, `.md`, `.pdf`, `.docx`)
and re-run `python ingest.py`. Each run rebuilds the collection from scratch, so there are
no duplicate chunks.

## Deliberately not built yet

- **PostgreSQL** — no persistence: chat is stateless, with no user profiles, chat history,
  or audit logs. `app/routers/chat.py` is the seam where those writes would be added.
- **OpenCV document/ID auditing** — the upload + image-preprocessing endpoint is a separate
  phase.
- Streaming responses, multi-turn conversation memory, and student authentication.

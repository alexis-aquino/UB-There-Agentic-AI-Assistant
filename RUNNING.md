# How to Run UB There

Step-by-step instructions for starting the app locally on Windows.

---

## Quick start (this machine)

Python, Node, and all dependencies are **already installed**. Only two things are left:

### 1. Add your OpenAI API key

Get a key from https://platform.openai.com/api-keys, then:

```powershell
cd "C:\Users\Alex\UB THERE - Agentic AI Assistant\backend"
Copy-Item .env.example .env
notepad .env
```

Replace `sk-your-key-here` with your real key, save, and close Notepad.

### 2. Build the search index

```powershell
.\.venv\Scripts\python.exe ingest.py
```

Expected output:

```
Loaded 3 document(s) from ...\data\sample_docs
Indexed 3 chunk(s) into 'university_docs'.
```

This calls OpenAI to create embeddings, so it costs a fraction of a cent and needs the key from step 1.

### 3. Start it

You need **two terminals** running at the same time.

**Terminal 1 — backend:**

```powershell
cd "C:\Users\Alex\UB THERE - Agentic AI Assistant\backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Wait for `Application startup complete.`

**Terminal 2 — frontend:**

```powershell
cd "C:\Users\Alex\UB THERE - Agentic AI Assistant\frontend"
npm run dev
```

Then open **http://localhost:5173** in your browser and ask a question, for example:

> What is the tuition refund policy if I withdraw in week 3?

To stop either server, click its terminal and press `Ctrl+C`.

---

## Checking it works

Before opening the browser, you can confirm the backend is healthy:

```powershell
curl.exe http://localhost:8000/api/health
```

A good response looks like this — note `openai_key_configured` must be `true`:

```json
{"status":"ok","openai_key_configured":true,"collection":"university_docs"}
```

You can also browse the interactive API docs at **http://localhost:8000/docs** and try the
`/api/chat` endpoint there without the frontend.

---

## Setup from scratch (a different machine)

Skip this if you are on the machine the project was built on.

### Install the runtimes

```powershell
winget install --id Python.Python.3.12 -e
winget install --id OpenJS.NodeJS.LTS -e
```

**Close and reopen your terminal** afterward, or the new commands will not be found. Verify:

```powershell
python --version   # expect 3.12.x
node --version     # expect v20 or v24
```

### Set up the backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env     # then edit .env and add your OPENAI_API_KEY
.\.venv\Scripts\python.exe ingest.py
```

The first install downloads a lot (LangChain, LlamaIndex, ChromaDB) and takes several minutes.

### Set up the frontend

```powershell
cd ..\frontend
npm install
Copy-Item .env.example .env
```

Then follow **step 3** above to start both servers.

---

## Using real university documents

The three files in `backend\data\sample_docs\` are placeholders with invented policies. To use real
content:

1. Delete the placeholder files.
2. Drop real documents in that folder — `.txt`, `.md`, `.pdf`, and `.docx` all work.
3. Rebuild the index:

   ```powershell
   cd backend
   .\.venv\Scripts\python.exe ingest.py
   ```

Each run rebuilds the collection from scratch, so re-running never creates duplicate entries.
Restart the backend afterward so it picks up the new index.

---

## Troubleshooting

**`python` or `npm` is not recognized**
The terminal was open before the install. Close it and open a new one.

**`running scripts is disabled on this system`**
You tried `.\.venv\Scripts\Activate.ps1`. Either use the `.\.venv\Scripts\python.exe` form shown
above, which needs no activation, or run this once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**Chat replies with `OPENAI_API_KEY is not set`**
`backend\.env` is missing or still has the placeholder key. Check that the file is named exactly
`.env` (not `.env.txt` — Notepad adds that silently) and that the line reads `OPENAI_API_KEY=sk-...`.
Restart the backend after editing.

**Chat replies that it cannot find the information**
The index is empty or was never built. Run `ingest.py` and confirm it reports indexed chunks.

**`Failed to fetch` in the browser**
The backend is not running, or it started on a different port. Confirm Terminal 1 shows
`Application startup complete.` and that `VITE_API_URL` in `frontend\.env` matches the backend's
address.

**`1 package has install scripts not yet covered by allowScripts`**
npm blocked esbuild, which Vite needs. Run `npm approve-scripts esbuild`, then `npm install` again.

**Port already in use**
An older server is still running. Find and stop it:

```powershell
Get-Process python, node -ErrorAction SilentlyContinue | Stop-Process -Force
```

---

## What this version does and does not do

It answers questions about university policies by searching the documents in
`backend\data\sample_docs\` and summarizing what it finds with GPT-4o.

It does **not** yet have a database (no login, no saved chat history — refreshing the page clears the
conversation, and it does not remember earlier messages within a conversation either), and it does
**not** yet accept document or ID image uploads. Both were deliberately left for a later phase.

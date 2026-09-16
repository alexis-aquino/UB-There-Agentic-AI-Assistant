# How to Run UB There

The app runs on a **free local model (Ollama)** by default — no account, no API key, nothing leaves
your machine. Switching to the paid OpenAI API is a one-line change, covered at the bottom.

---

## Current state on this machine

Everything below is already installed and working:

- Python 3.12, Node.js 24, and all project dependencies
- Ollama, with `llama3.2` (chat) and `nomic-embed-text` (embeddings)
- `backend\.env` created, set to the free provider
- Your `studenthandbook.pdf` indexed — 154 pages, 268 searchable chunks

**To use it right now**, you only need to start the two servers (step 3).

---

## 1. Add your documents

Put files in the **`upload uni info here`** folder at the top of the project.

Supported: `.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.pptx`

You can add as many as you like, or just one. The `README.md` in that folder is skipped
automatically, so it never pollutes the answers.

## 2. Rebuild the index

Any time you add, remove, or change a file in that folder:

```powershell
cd "C:\Users\Alex\UB THERE - Agentic AI Assistant\backend"
.\.venv\Scripts\python.exe ingest.py
```

You should see something like `Indexed 268 chunk(s)`. This reads every document, converts it to
searchable vectors with the local embedding model, and replaces the previous index — so re-running
never creates duplicates. A 150-page PDF takes about a minute.

**The chatbot only knows what has been indexed.** Adding a file does nothing until you run this.

## 3. Start it

Two terminals, both left running.

**Terminal 1 — backend:**

```powershell
cd "C:\Users\Alex\UB THERE - Agentic AI Assistant\backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

**Terminal 2 — frontend:**

```powershell
cd "C:\Users\Alex\UB THERE - Agentic AI Assistant\frontend"
npm run dev
```

Open **http://localhost:5173** and ask a question. Answers take about 8-15 seconds on the local
model; the very first one after a cold start is slower while the model loads into your GPU.
`Ctrl+C` in either terminal stops that server.

### Quick check without the browser

```powershell
curl.exe http://localhost:8000/api/health
```

Healthy output — `provider_ready` must be `true`:

```json
{"status":"ok","provider":"ollama","provider_ready":true,"detail":"ready","collection":"university_docs_ollama"}
```

---

## Switching to OpenAI later

The free local model is noticeably weaker at reading tables and following instructions. When you
want better answers:

1. Get a key at https://platform.openai.com/api-keys (this is paid, roughly a cent per few dozen
   questions on `gpt-4o`).
2. Edit `backend\.env`:

   ```
   LLM_PROVIDER=openai
   OPENAI_API_KEY=sk-your-real-key-here
   ```

3. Re-run `ingest.py`, then restart the backend.

The re-ingest is required because the two providers produce different embedding formats. Each
provider keeps its **own** index (`university_docs_ollama` vs `university_docs_openai`), so
switching back and forth later needs no re-indexing — both stay built.

To go back to free, set `LLM_PROVIDER=ollama` and restart. No other code changes.

---

## What works well, and what doesn't

Tested against your actual handbook:

**Works well** — anything written as ordinary prose, answered with a real page citation:
> *"What happens if a student is absent for too many hours?"*
> → *"According to [studenthandbook.pdf p.53] ... dropped from the subject if hours lost reach 20%."*
> Verified correct against page 53.

**Declines honestly** — data locked in a **table**. PDF extraction flattens tables into loose runs of
numbers, so the grade-weighting breakdowns on pages 46-48 aren't retrievable. Asked for the
midterm/finals split, it now says it cannot find that and suggests the registrar, rather than
inventing a number. If you need those figures, restate them in a plain `.txt` file in the upload
folder next to the PDF.

**Watch out for** — words the handbook uses in two senses. Asking about "class suspensions" matches
the *disciplinary* suspension pages, because that's what "suspension" nearly always means in this
document. Phrasing questions with distinctive wording helps.

Switching to OpenAI improves fluency and table handling somewhat, but tables remain the weak area
for any provider.

---

## Setup from scratch (a different machine)

```powershell
winget install --id Python.Python.3.12 -e
winget install --id OpenJS.NodeJS.LTS -e
winget install --id Ollama.Ollama -e
```

Close and reopen the terminal, then:

```powershell
ollama pull llama3.2
ollama pull nomic-embed-text

cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe ingest.py

cd ..\frontend
npm install
Copy-Item .env.example .env
```

Then follow step 3 above.

---

## Troubleshooting

**`Cannot reach Ollama at http://localhost:11434`**
Ollama isn't running. Start it with `ollama serve`, or launch the Ollama app from the Start menu.
Confirm with `ollama list` — you should see `llama3.2` and `nomic-embed-text`.

**Answers are slow**
First question after starting loads the model into VRAM. If every answer is slow, check the model is
on the GPU with `ollama ps` — `100% GPU` is what you want on your GTX 1660 SUPER.

**"No documents found in ... upload uni info here"**
The folder has only the README in it. Add real documents and re-run `ingest.py`.

**Chatbot answers about the wrong topic, or says it has no information**
The index is stale or the question doesn't match the document's wording. Re-run `ingest.py`, and try
phrasing the question using words that actually appear in the handbook.

**`python` or `npm` is not recognized**
The terminal was open before the install. Close it and open a new one.

**`running scripts is disabled on this system`**
Use the `.\.venv\Scripts\python.exe` form shown above, which needs no venv activation. Or run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

**`Failed to fetch` in the browser**
The backend isn't running, or is on a different port than `VITE_API_URL` in `frontend\.env`.

**Port already in use**

```powershell
Get-Process python, node -ErrorAction SilentlyContinue | Stop-Process -Force
```

---

## Not built yet

No database — no login, no saved chat history, and no memory of earlier messages within a
conversation. No document or ID image uploads through the UI. Both were deliberately deferred.

# STEPS TO RUN

Install first:

- **Python 3.12** — https://www.python.org/downloads/ (tick "Add python.exe to PATH")
- **Node.js** — https://nodejs.org
- **Ollama** — https://ollama.com/download

## Install (once)

```
ollama pull llama3.2
ollama pull nomic-embed-text
```

```
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ..\requirements.txt
copy .env.example .env
.\.venv\Scripts\python.exe ingest.py
```

```
cd ..\frontend
npm.cmd install
copy .env.example .env
```

## Run (every time)

Window 1:

```
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8100
```

Window 2:

```
cd frontend
npm.cmd run dev
```

Open **http://localhost:5273** → **Admin / Guest login** → **Create a guest account**.

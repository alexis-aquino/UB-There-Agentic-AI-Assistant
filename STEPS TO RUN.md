# STEPS TO RUN & CREDENTIALS

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
.\.venv\Scripts\python.exe -c "from app.config import get_settings as g; from app.auth.store import UserStore; s = UserStore(g().users_db, g().default_password); [s.create(e, n) for e, n in [('admin@ub.edu.ph', 'UB Admin'), ('student@ub.edu.ph', 'UB Student')]]"
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

Open **http://localhost:5273** → **Admin / Guest login** → sign in with a demo account below.

## Credentials (demo)

| Account | Email | Password |
|---|---|---|
| Student | student@ub.edu.ph | 12345678 |
| Admin | admin@ub.edu.ph | 12345678 |

Every new account (guest or UB Mail) also starts with the password **12345678**.

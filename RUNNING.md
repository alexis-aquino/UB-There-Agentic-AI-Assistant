# How to Run — UB There

Answers are written by **llama3.2** running locally in **Ollama**, orchestrated by **LlamaIndex**.
Free, no API key; nothing leaves the PC. **Ollama must be running** (open the Ollama app — it sits in
the system tray) with two models pulled:

```powershell
ollama pull llama3.2
ollama pull nomic-embed-text
```

---

## Current state on this machine

Already done: Python venv and dependencies installed, both Ollama models pulled, and your
`studenthandbook.pdf` indexed (483 passages, keyword + vector). You only need step 3.

## 1. Add your documents

Put files in **`upload uni info here`**. Supported: `.pdf`, `.docx`, `.txt`, `.md`.
The `README.md` in that folder is skipped automatically.

## 2. Build the index

```powershell
cd "C:\Users\Alex\UB THERE - Agentic AI Assistant - Self Developed AI Model\backend"
.\.venv\Scripts\python.exe ingest.py
```

Builds two indexes over the same passages: a keyword index (instant) and a LlamaIndex vector index
stored in **ChromaDB** at `backend\index\chroma\` (each passage embedded by nomic-embed-text —
about a minute for the handbook). Needs Ollama running.
Re-run after changing documents, then restart the backend.

## 3. Start it

Two terminals.

**Backend:**

```powershell
cd "C:\Users\Alex\UB THERE - Agentic AI Assistant - Self Developed AI Model\backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8100 --reload
```

**Frontend:**

```powershell
cd "C:\Users\Alex\UB THERE - Agentic AI Assistant - Self Developed AI Model\frontend"
npm.cmd run dev
```

Use `npm.cmd`, not `npm`: in Windows PowerShell, plain `npm` runs `npm.ps1`, which Windows blocks
with "running scripts is disabled on this system". The port (5273) is set in `vite.config.js`.

Open **http://localhost:5273**.

> Ports 8100/5273 are used so this can run at the same time as the original Ollama project on
> 8000/5173. The frontend reaches the backend through its own `/api` proxy (`vite.config.js`).

### Open it on your phone

The phone must be on the same network as the PC (same router). Start the backend as usual, but
start the frontend with:

```powershell
cd "C:\Users\Alex\UB THERE - Agentic AI Assistant - Self Developed AI Model\frontend"
npm.cmd run dev:phone
```

It prints a **Network** address such as `http://192.168.1.2:5273/`; open that on the phone. The
phone only talks to port 5273 — the frontend forwards `/api` to the backend, which stays private
to the PC. Voice recording is never forwarded.

**Windows Firewall blocks it until you allow it (once).** On a **Public** network profile, inbound
connections are refused. On your home network, in an **administrator** PowerShell:

```powershell
Set-NetConnectionProfile -InterfaceAlias "Ethernet" -NetworkCategory Private
New-NetFirewallRule -DisplayName "UB There (phone access)" -Direction Inbound -Protocol TCP -LocalPort 5273 -Action Allow -Profile Private
```

Don't do this on public Wi-Fi: anyone on the same network can open the app while `dev:phone` runs.
Google sign-in won't work from the phone address (Google only allows `localhost` over plain http);
email login does.

### Health check

```powershell
curl.exe http://localhost:8100/api/health
```

Reports whether the brain is ready (indexes loaded, Ollama reachable, models present), the model
names, and how many turns the query log holds.

---

## Using it

Replies stream onto the screen as llama3.2 writes them and are read aloud by an AI voice, sentence by
sentence. **Voice on/off** in the header mutes it; **Voice settings** lets each student pick one of
eight AI voices and preview it; **Read aloud** re-speaks any answer. Follow-up questions work ("what
about female students?").

Each reply shows the **source page**, a **match** figure, and a **"Where I got this"** link: the page,
the exact passage, and a picture of that handbook page with the passage highlighted (click it for
the full page).

## Accounts and sign-in

The app opens on **Sign in with UB Mail** (`#/login`) — the main way in for students and staff. Below
it, **Admin / Guest login** (`#/guest`) is the email-and-password door, with guest sign-up at
`#/signup`. Accounts are stored in
`backend/users.db` (git-ignored); passwords are salted PBKDF2 hashes.

- **Every account starts with the password `12345678`.** Sign-up pre-fills it, and accounts
  created through Google get it too, so they can also log in with email + password. Users see a
  reminder to change it (header → their name → *Change password*). Change the starting
  password with `DEFAULT_PASSWORD` in `backend/.env`.
- **Two kinds of account:**
  - **UB students and staff** sign in with Google, and only with an **@ub.edu.ph** Google
    Workspace account. The backend checks Google's verified `hd` (hosted domain) claim, so a
    personal Gmail account is refused even if its name looks like a UB address. Change the
    domain with `GOOGLE_DOMAIN` in `backend/.env`.
  - **Guests** sign up with any name and email (both required) and a password.
  - While Google sign-in is on, the guest form refuses @ub.edu.ph addresses — UB identities only
    come through Google, so nobody can pose as a UB account. Accounts made before that (like the
    starter `student@ub.edu.ph`) keep working, and link to Google on first Google sign-in.
- **Google sign-in** is off until you give it a client ID:
  1. [Google Cloud Console](https://console.cloud.google.com/) → create (or pick) a project.
  2. *APIs & Services* → *OAuth consent screen*: app name "UB There", your email as support
     contact. If the project belongs to the ub.edu.ph Google Workspace, choose **Internal** (only
     UB accounts can even try). Otherwise choose **External**, then either add testers under
     *Test users* or click **Publish app** — while it is in *Testing*, only listed test users can
     sign in. Basic sign-in (name, email) needs no Google review.
  3. *Credentials* → *Create credentials* → *OAuth client ID* → type **Web application**. Under
     *Authorized JavaScript origins* add `http://localhost:5273` and `http://localhost`.
  4. Put the client ID in `backend/.env`:
     `GOOGLE_CLIENT_ID=1234567890-abc.apps.googleusercontent.com`, then restart the backend.

  Google only allows plain-http sign-in from `localhost`, so the Google button works on the PC
  but not on a phone opening `http://192.168.x.x:5273` — guests' email sign-in works there.

## Admin dashboard

Administrators see **Admin dashboard** in the menu (`#admin`). Who counts is set in `backend\.env`,
then restart the backend:

```
ADMIN_EMAILS=registrar.head@ub.edu.ph,osa.director@ub.edu.ph
```

Only addresses in `GOOGLE_DOMAIN` (ub.edu.ph) count, so admins sign in with **Sign in with UB
Mail**; a guest account is never an admin, even if listed. The backend refuses the dashboard's data
to everyone else. `admin@ub.edu.ph` is a password test account; remove it from the list once real
admins sign in with Google.

The **Inquiry report** is built from every handbook question asked (small talk like "hi" isn't
counted): its topic, whether the handbook answered it, the source page, who asked (when signed in),
and, if it was sent to an office, the ticket and the office's answer. All of it lives in
`backend\brain_memory.db` (questions) and `backend\tickets.db` (office tickets). Questions asked
before this was added aren't in it.

**Offensive or off-topic.** The assistant flags these itself (shown as "by Assistant · offensive
language" or "· not about school"): insults or profanity in English or Filipino, and questions the
handbook didn't cover that aren't about school ("Who will win the NBA finals?", "Tell me a joke").
The student's reply is the same either way; only the report changes. The rules are keyword lists in
`backend\app\brain\moderation.py`, so they will sometimes miss one or flag a real question: an admin
can **Clear flag** on a wrong one, or **Flag** a missed one, in the Inquiry tracker. Flagged questions
are left out of the most-asked list.

**Accounts** lists every real account in `backend\users.db`: how it signs in, when it joined, when it
was last used (signing in, opening the app, or asking a question) and how many questions it asked.

- **Disable** stops an account signing in, and signs it out on its next request. **Enable** undoes it.
- **Delete** is allowed only after an account has been disabled for 30 days
  (`ACCOUNT_DELETE_AFTER_DAYS` in `backend\.env`). It removes the account but keeps its history:
  its questions stay in the Inquiry report under the student's name, marked "Account deleted", and
  its office tickets are kept. Questions that were still Rerouted or Pending become **Closed**, since
  nobody can follow them up any more; the office's answer link says the question is closed and no
  longer takes answers. Answered and Resolved questions keep their state. A flagged question still
  shows as flagged.
- An administrator can't disable or delete their own account.

## Asking an office

When the assistant can't answer, or isn't sure, its reply shows **Ask an office**. The student
picks the office (the app suggests one from keywords) and sends. The app emails that office from
its **own** address with a private **answer link**; staff answer on that page — no account needed
— and the answer appears in the student's **My questions**. Students who signed in with Google also
get an email when it's answered; guests' addresses were never verified, so they only see it in the
app. The office never sees the student's email address. Each student can send 5 a day
(`TICKETS_PER_DAY`).

- **Offices** live in `backend\offices.json`: name, email and keywords. The addresses there are
  placeholders (`@example.com`) — replace them with the real offices' addresses before turning on
  real email.
- **Until email is set up** (`MAIL_MODE=log`, the default) nothing is sent: each email is saved in
  `backend\outbox\` as an `.eml` file. Double-click one to open it in Outlook or Mail; the answer
  link inside works on this PC, so you can play the office yourself.
- **To send real email** from the app's Gmail account:
  1. Sign in to the app's Gmail account and turn on **2-Step Verification**
     (Google Account → Security).
  2. Google Account → Security → **App passwords** (or search "App passwords") → create one named
     "UB There" and copy the 16-character password.
  3. In `backend\.env`:
     ```
     MAIL_MODE=smtp
     SMTP_USER=ubthere.assistant@gmail.com
     SMTP_PASSWORD=abcdefghijklmnop
     ```
  4. Restart the backend. When UB IT gives you a ub.edu.ph address, change `SMTP_USER` and
     `SMTP_PASSWORD` the same way.
- **Answer links only work where staff can reach the app.** They point to `PUBLIC_BASE_URL`
  (default `http://localhost:5273`), which is fine for testing on this PC. For office staff on
  their own computers, the app has to be hosted at a real address; then set `PUBLIC_BASE_URL` to
  it.

## Switching the answer model (Ollama ↔ OpenAI)

Ollama's llama3.2 writes the answers by default. To have an OpenAI model write them instead, put
this in `backend\.env` and restart the backend:

```
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...your key...
OPENAI_MODEL=gpt-4o-mini
```

- The key goes **only** in `backend\.env` (git-ignored) — never in `frontend\`, which is sent to
  every browser.
- Handbook search keeps using nomic-embed-text in Ollama and the ChromaDB index, so **Ollama must
  still be running**, and there's nothing to rebuild.
- OpenAI charges per question, and questions plus handbook excerpts are sent to OpenAI.
- To switch back, set `LLM_PROVIDER=ollama` (or delete the line) and restart.

## What it does well, and what it won't

**Well:** handbook questions in the student's own words — *"can I dye my hair"*, *"what happens if
I'm absent too much"* — answered conversationally with the page to check. Off-topic questions get
an honest "I couldn't find that in the handbook" and the **Ask an office** button, never a made-up
answer.

**Speed:** first words in about 1–3 s on this PC's GTX 1660 SUPER (the model reads the excerpts
first); voice starts about a second after that. It is slower when RAM is nearly full — close heavy
apps (browsers with many tabs, Discord, Spotify) if replies drag.

**Won't:** read tables in PDFs well, since extraction flattens them; restate those figures in a
`.txt` file if you need them. llama3.2 is a small model — it can still word things clumsily.

---

## Voice

Every answer is read aloud by an AI voice. Students only ever **choose** a voice; recording and
training happen in the **voice studio**, a page the backend serves at
**http://localhost:8100/voice-studio**. It only opens on the computer running the backend, and the
student app cannot reach it.

### Generic voice (already installed)

Default, nothing more to do. Piper runs offline on CPU. The voice is loaded when the backend starts,
and each reply is spoken one sentence at a time while it is still being written — the next sentence
is prepared while the current one plays. Audio is cached by text, so repeats are instant.

Students pick from eight Piper voices under **Voice settings** (Lessac, Amy, Kristin, Ryan, Joe,
John, Alba, Alan). Only Lessac ships installed; the others download to `backend\voice_models\` the
first time anyone uses them (about 63 MB each, a few seconds). The list lives in
`backend\app\voice\catalog.py`.

Turn it off with the **Voice on/off** button in the header, or set `VOICE_PROVIDER=off` in
`backend\.env`.

### Training your own voice (Piper)

This trains a real model of your voice by fine-tuning the Lessac voice the app already uses. The
result runs exactly like the generic voice: offline, on CPU, about a third of a second per answer,
and with no licence restrictions.

**1. Record (in the backend's voice studio, any number of sessions).** With the backend running,
open **http://localhost:8100/voice-studio** on the same computer. Read each sentence, pressing **Space** to start and stop. A clean take saves and moves to
the next sentence on its own. Aim for the 25-minute mark on the progress bar, roughly 300 clips;
more helps, and fewer than 150 sounds only partly like you. Clips are saved in
`backend\voice_dataset\`, which is kept out of git because it is your voice.

**2. Install WSL (once, needs admin and a reboot).** Piper's trainer only builds on Linux. In an
**administrator** PowerShell:

```powershell
wsl --install -d Ubuntu
```

Reboot, open **Ubuntu** from the Start menu once, and create a username and password.

**3. Set up the trainer (once, about 20 minutes, several GB).**

```powershell
cd "C:\Users\Alex\UB THERE - Agentic AI Assistant - Self Developed AI Model\backend"
wsl bash voice_training/setup_wsl.sh
```

This installs build tools, clones the trainer into `~/piper-voice` inside WSL, checks PyTorch can
see your GPU, and downloads the Lessac checkpoint (850 MB).

**4. Train (several hours; leave it running).**

```powershell
wsl bash voice_training/train.sh
```

Expect roughly 4-8 hours on the GTX 1660 SUPER for the default 1000 epochs. It is resumable: press
Ctrl+C and run the command again to carry on. If it fails with *CUDA out of memory* (6 GB is below
the 8 GB Piper's authors suggest), use a smaller batch:
`wsl BATCH_SIZE=4 bash voice_training/train.sh`.

**5. Export and switch the app to it.**

```powershell
wsl bash voice_training/export.sh
```

Then in `backend\.env` set `PIPER_VOICE=en_US-myvoice-medium` and restart the backend. You can
export mid-training from a second terminal to hear how it is coming along. To go back to the
generic voice, set `PIPER_VOICE=en_US-lessac-medium`.

To change the sentences, edit `backend\voice_training\build_prompts.py` and re-run it. Do that
before recording: clips are matched to prompts by line number.

### Instant clone (XTTS)

There is **no training run** — XTTS copies your voice from a short sample.

1. Install the optional package (large — pulls PyTorch, about 2.5 GB):

   ```powershell
   cd "C:\Users\Alex\UB THERE - Agentic AI Assistant - Self Developed AI Model\backend"
   .\.venv\Scripts\python.exe -m pip install -r requirements-voice-clone.txt
   ```

2. Open **http://localhost:8100/voice-studio**, and under **Instant clone sample** click **Start
   recording**, read the script aloud for about 30 seconds in a quiet room, then **Stop**.
3. Set `VOICE_PROVIDER=xtts` in `backend\.env` and restart the backend.
4. The first reply downloads the model (about 1.8 GB), then it answers in your voice.

Expect roughly 1-3 seconds per reply on your GTX 1660 SUPER — the brain answers in 30 ms, so the
voice becomes the slow part. Cloning captures your timbre well but not strong accent or prosody: it
will sound like you, not identical to you.

**Licence:** XTTS v2 weights are non-commercial. Fine for a thesis or demo, not for resale.

---

## Setup from scratch

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe ingest.py

cd ..\frontend
npm install
Copy-Item .env.example .env
```

Install [Ollama](https://ollama.com) and pull `llama3.2` and `nomic-embed-text` first (see the top
of this file) — `ingest.py` needs it running.

## Running the tests

```powershell
cd "C:\Users\Alex\UB THERE - Agentic AI Assistant - Self Developed AI Model\backend"
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
```

Runs in a few seconds and **doesn't need Ollama**: the tests use small offline stand-ins for the
model and embeddings (`LLM_PROVIDER=mock`) and temporary databases, so your real data is untouched.
`tests/test_retrieval.py` holds golden handbook questions with the page the keyword search must
find — add a case whenever you fix a wrong answer. It skips if `ingest.py` has not been run.

Student wording the handbook never uses ("dress code" vs "uniform") is bridged for the keyword
search in `backend\app\brain\synonyms.py`. How the model is told to answer lives in
`backend\app\brain\prompts.py`.

## Troubleshooting

**"No index found" / "AI search index hasn't been built"** — run `ingest.py`.

**"The AI model isn't running"** — open the Ollama app (or run `ollama serve`), then ask again.
**"Ollama is missing the model …"** — run the `ollama pull` it names.

**Answers seem stale after changing documents** — re-run `ingest.py` and restart the backend.

**It says "I couldn't find that" for a question you think it should answer** — open "How it
decided". If both searches scored low, rephrase using the handbook's own wording; if a real handbook
question keeps failing, the thresholds in `backend\app\brain\retriever.py` may need recalibrating.

**Replies are slow** — check `ollama ps` shows `100% GPU`, and free up RAM (close heavy apps).

**No speech** — check `curl.exe http://localhost:8100/api/voice/status`. If `piper_installed` is
false, run `pip install -r requirements-voice.txt`. If the status says it is speaking but there is no
sound, the browser blocked autoplay: click once anywhere on the page, then ask again.

**Frontend won't open / "running scripts is disabled"** — start it with `npm.cmd run dev` (see
*Start it*). If it says port 5273 is in use, another copy is already running: close that window, or
just open http://localhost:5273.

**Clearing memory** — delete `backend\brain_memory.db`. It rebuilds empty.

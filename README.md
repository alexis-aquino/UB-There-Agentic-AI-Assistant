# UB There — University of Batangas Handbook Assistant

A student handbook assistant that answers in a natural, conversational voice. **LlamaIndex**
orchestrates the answer: it finds the right handbook passages, and **llama3.2** (running locally
in Ollama — free, no API key, nothing leaves the PC) writes the reply from them. Replies stream
onto the screen and are read aloud sentence by sentence.

```
React (Vite) ──HTTP──> FastAPI ──> Brain (LlamaIndex)
                                    ├── small-talk detection   (rules — skips the search)
                                    ├── hybrid search          (LlamaIndex + ChromaDB vectors, handbook keywords)
                                    │     └── grounding gate   (no confident match → no excerpts)
                                    ├── llama3.2 via Ollama    (writes the reply, streamed)
                                    └── query log              (SQLite — every question and reply)
```

Documents go in **`upload uni info here/`**. See [RUNNING.md](RUNNING.md) to start it.

## How an answer is made

`backend/app/brain/`:

| File | Role |
|---|---|
| `readers.py`, `chunker.py` | Read `.pdf` / `.docx` / `.txt` / `.md` and split into ~120-word passages |
| `vectors.py` | LlamaIndex vector index of the passages, stored in **ChromaDB** (`backend/index/chroma/`, nomic-embed-text embeddings) |
| `bm25.py`, `reflect.py`, `synonyms.py`, `text.py` | Keyword index over the same passages, with synonyms and a grounding check |
| `retriever.py` | One LlamaIndex retriever combining both, merged by reciprocal rank fusion |
| `prompts.py` | The persona and the instructions the model gets |
| `llm.py` | The Ollama model and embeddings (plus offline stand-ins for tests) |
| `engine.py` | Orchestrates it and streams the reply; keeps a few turns per chat for follow-ups |
| `memory.py` | The query log |

**Why two kinds of search.** Vectors find passages that mean the same thing in other words ("can I
dye my hair" → the hair-color rule). Keywords catch exact handbook terms that vectors blur
("overload", "TOR"). Each covers the other's misses.

**Why the grounding gate.** llama3.2 is a small model: given loosely related text, or nothing, it
will happily invent an answer. So the search decides first whether the handbook really covers the
question (calibrated thresholds in `retriever.py`). If not, the model is never asked to answer — only
to tell the student kindly that it isn't in the handbook — and the app offers **Ask an office**.

**Follow-ups.** The last few turns of each chat are kept, and a short follow-up ("what about female
students?") is searched together with the previous question.

## Voice

Answers are read aloud in an AI voice each student picks (eight free Piper voices, downloaded on
first use). Speech is made **one sentence at a time while the reply is still streaming**, and the
next sentence is prepared while the current one plays, so speaking starts about a second after the
first words appear. The default voice is loaded when the backend starts. When the voice service is
unavailable the browser's own `speechSynthesis` takes over.

Recording and training a custom voice is backend-only: the backend serves its own studio page at
`/voice-studio`, reachable only from the machine it runs on.

Voice providers (`VOICE_PROVIDER` in `backend/.env`): `piper` (default, offline, CPU), `xtts` (a
cloned voice; weights are **non-commercial**), or `off`.

## Trade-offs, honestly

- **Speed depends on the PC.** On a GTX 1660 SUPER the first words take about 1–3 s (the model reads
  ~600 tokens of excerpts first); with little free RAM it gets slower. Closing heavy apps helps.
- **A small model.** llama3.2 (3B) is quick and fits in 6 GB of VRAM, but it is not as careful as
  larger models; the grounding gate and tightly scoped prompts carry a lot of the accuracy. A bigger
  model (e.g. `OLLAMA_MODEL=llama3.1:8b`) is more careful but slower.
- **Tables in PDFs** stay hard to read — text extraction flattens them.

## Not built yet

Accounts exist (email/password and Google, see [RUNNING.md](RUNNING.md)), but only the frontend
requires sign-in — the chat API itself is still open. The admin dashboard's **Inquiry report** runs on
the real query log; its Accounts and Knowledge base pages are still sample data. No department
dashboards, and no document-audit (DFD process 4.0).

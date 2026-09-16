# Upload university info here

Put the documents you want the chatbot to answer from in this folder.

**Supported:** `.pdf`, `.docx`, `.txt`, `.md`, `.csv`, `.pptx`

Examples: course handbooks, academic policies, grading schemes, tuition and refund rules,
enrollment deadlines, program requirements.

## After adding or changing files

Rebuild the search index, then restart the backend:

```powershell
cd backend
.\.venv\Scripts\python.exe ingest.py
```

The chatbot only knows what has been indexed — adding a file here does nothing until you run
`ingest.py`.

## Note on the files currently here

The three `.txt` files are **placeholders with invented policies**, included so the app works before
you have real documents. Delete them once you add real ones, or the chatbot will quote fake rules.

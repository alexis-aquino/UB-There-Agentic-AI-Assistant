# Upload university info here

Put the documents you want the chatbot to answer from in this folder.

**Supported:** `.pdf`, `.docx`, `.txt`, `.md`. Other file types are ignored. This README is
never indexed.

Examples: course handbooks, academic policies, grading schemes, tuition and refund rules,
enrollment deadlines, program requirements.

## After adding or changing files

The chatbot only knows what has been indexed. Adding a file here does nothing until the search
index is rebuilt. There are two ways to rebuild it:

- **From the app:** sign in as an admin, go to **Documents**, and press **Rebuild index**. You can
  also add, replace and delete files there. No restart is needed, and every change is logged.
- **From a terminal:** run this, then restart the backend.

  ```powershell
  cd backend
  .\.venv\Scripts\python.exe ingest.py
  ```

Scanned PDFs (pictures of pages with no text layer) can't be read. Run OCR on them first.

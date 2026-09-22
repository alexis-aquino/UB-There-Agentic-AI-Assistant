r"""Build the vector index from the documents in the upload folder.

Run after adding or changing documents:
    .\.venv\Scripts\python.exe ingest.py

The admin dashboard's "Re-index" button runs this same code path.
"""

import sys

from app.services.indexer import NoDocumentsError, rebuild_index
from app.services.providers import ProviderNotReadyError


def main() -> int:
    try:
        rebuild_index(db=None)
    except ProviderNotReadyError as exc:
        print(exc)
        return 1
    except NoDocumentsError as exc:
        print(exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

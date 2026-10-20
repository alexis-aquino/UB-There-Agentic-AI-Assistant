r"""Give an existing account a role: guest, student, department (one office's staff) or admin.

The account must exist first (sign up, sign in with Google, or create it as in STEPS TO RUN.md).

    .\.venv\Scripts\python.exe set_role.py admin@ub.edu.ph admin
    .\.venv\Scripts\python.exe set_role.py registrar.staff@ub.edu.ph department registrar
    .\.venv\Scripts\python.exe set_role.py someone@ub.edu.ph student
    .\.venv\Scripts\python.exe set_role.py visitor@gmail.com guest

Office ids are the "id" values in offices.json.
"""

import sys

from app.auth.store import ROLES, UnknownUserError, UserStore
from app.config import get_settings
from app.tickets.offices import get_office, load_offices


def main(args: list[str]) -> int:
    if len(args) not in (2, 3) or args[1] not in ROLES:
        print(__doc__)
        return 1
    email, role = args[0], args[1]
    office_id = args[2] if len(args) == 3 else None

    if role == "department":
        if office_id is None or get_office(office_id) is None:
            ids = ", ".join(office.id for office in load_offices())
            print(f"Department accounts need an office id from offices.json: {ids}")
            return 1
    elif office_id is not None:
        print("Only department accounts take an office id.")
        return 1

    settings = get_settings()
    try:
        user = UserStore(settings.users_db, settings.default_password).set_role(email, role, office_id)
    except UnknownUserError:
        print(f"No account with the email {email}. Create it first.")
        return 1

    where = f" ({get_office(office_id).name})" if office_id else ""
    print(f"{user.email} is now: {user.role}{where}. It applies at once; an open app shows it after a reload.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

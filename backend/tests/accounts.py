"""Signed-in test accounts of any role, for endpoints that need a token."""

import uuid

from app.routers import auth


def headers_for(role="student", office_id=None):
    store = auth.get_store()
    user = store.create(f"{role}-{uuid.uuid4().hex[:8]}@example.com", f"Test {role}")
    if role != "guest":
        user = store.set_role(user.email, role, office_id)
    return {"Authorization": f"Bearer {auth._session(user).token}"}

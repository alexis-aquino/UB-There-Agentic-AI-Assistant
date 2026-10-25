"""The "answer here" page office staff open from the email. Plain HTML, no frontend needed."""

from __future__ import annotations

from html import escape

from app.tickets.store import Ticket

STYLE = """
:root { --bg:#f6f4f2; --surface:#fff; --rule:#e4dfda; --ink:#22201e; --muted:#6b645e;
        --accent:#7a1220; --ok-bg:#e9f5ee; --ok:#22613d; --bad-bg:#fdecec; --bad:#9b1c1c;
        color-scheme: light dark; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#161413; --surface:#1f1c1a; --rule:#34302c; --ink:#f1ece7; --muted:#a59d95;
          --accent:#f0b54d; --ok-bg:#1d3326; --ok:#9fdcb4; --bad-bg:#3b1f1f; --bad:#ffb4b4; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:16px/1.6 "Segoe UI", system-ui, sans-serif; }
main { max-width:640px; margin:0 auto; padding:32px 16px 48px; }
.brand { display:flex; align-items:center; gap:10px; margin-bottom:20px; font-weight:700; }
.seal { width:36px; height:36px; border-radius:9px; display:grid; place-items:center;
        background:#7a1220; color:#ffc454; font-size:.85rem; }
.card { background:var(--surface); border:1px solid var(--rule); border-radius:14px; padding:22px; }
h1 { font-size:1.25rem; margin:0 0 4px; }
.meta { color:var(--muted); font-size:.88rem; margin:0 0 16px; }
blockquote { margin:0 0 20px; padding:14px 16px; border-left:3px solid var(--accent);
             background:var(--bg); border-radius:0 10px 10px 0; font-size:1.05rem; }
label { display:block; font-weight:600; font-size:.9rem; margin:14px 0 6px; }
textarea, input { width:100%; padding:10px 12px; border:1px solid var(--rule); border-radius:10px;
                  background:var(--bg); color:var(--ink); font:inherit; }
textarea { min-height:160px; resize:vertical; }
button { margin-top:16px; padding:11px 22px; border:0; border-radius:10px; background:#7a1220;
         color:#fff; font:inherit; font-weight:600; cursor:pointer; }
.note { color:var(--muted); font-size:.85rem; margin:12px 0 0; }
.ok { background:var(--ok-bg); color:var(--ok); padding:12px 14px; border-radius:10px; margin:0 0 16px; }
.bad { background:var(--bad-bg); color:var(--bad); padding:12px 14px; border-radius:10px; margin:0 0 16px; }
"""


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} — UB There</title><style>{STYLE}</style></head>
<body><main><div class="brand"><span class="seal">UB</span>UB There</div>
<div class="card">{body}</div></main></body></html>"""


def answer_page(ticket: Ticket, student: str, token: str, *, saved: bool = False, error: str | None = None) -> str:
    banner = ""
    if saved:
        banner = '<p class="ok">Thank you — your answer was sent to the student. You can close this page.</p>'
    elif error:
        banner = f'<p class="bad">{escape(error)}</p>'
    elif ticket.answer:
        banner = '<p class="ok">This question has already been answered. Saving again updates the answer.</p>'

    return _page(
        ticket.ref,
        f"""{banner}
<h1>Question for the {escape(ticket.office_name)}</h1>
<p class="meta">{escape(ticket.ref)} · asked by {escape(student)}</p>
<blockquote>{escape(ticket.question)}</blockquote>
<form method="post" action="/answer/{escape(ticket.ref)}">
  <input type="hidden" name="t" value="{escape(token)}">
  <label for="answer">Your answer</label>
  <textarea id="answer" name="answer" required maxlength="5000">{escape(ticket.answer or "")}</textarea>
  <label for="answered_by">Your name or office (optional, shown to the student)</label>
  <input id="answered_by" name="answered_by" maxlength="80" value="{escape(ticket.answered_by or "")}">
  <button type="submit">Send answer to student</button>
</form>
<p class="note">The student sees your answer in UB There. Their email address is not shared with you,
and replies to the notification email are not read — please answer here.</p>""",
    )


def closed_page(ticket: Ticket) -> str:
    """The student's account was deleted, so an answer would reach nobody."""
    return _page(
        ticket.ref,
        f"""<p class="bad">This question is closed: the student's account has been deleted, so an answer
could no longer reach them.</p>
<h1>Question for the {escape(ticket.office_name)}</h1>
<p class="meta">{escape(ticket.ref)}</p>
<blockquote>{escape(ticket.question)}</blockquote>
<p class="note">No answer is needed. You can close this page.</p>""",
    )


def not_found_page() -> str:
    return _page(
        "Link not valid",
        "<h1>This link isn't valid</h1>"
        '<p class="meta">It may have been copied incompletely. Open the link from the email again.</p>',
    )

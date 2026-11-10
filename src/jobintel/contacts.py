"""Recruiter and hiring-manager contacts: only sourced, role-relevant, professionally published information.

Rules (Agents/AGENTS.md, job-turbo-upgrade/05): a contact needs a source URL and a checked date; a business
email is stored only when the source published it; email addresses are never guessed, pattern-derived or taken
from free-mail domains; opted-out contacts are never returned.
"""
from __future__ import annotations

import re

from .store import Store, now_iso

FREE_MAIL = {"gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "icloud.com", "live.com", "proton.me", "protonmail.com"}
RELATIONS = ("confirmed", "probable", "unknown")
EMAIL_STATES = ("source_published", "provider_verified", "not_verified")


class ContactRejected(ValueError):
    pass


def add_contact(store: Store, job_id: str, company: str, name: str, title: str, source_url: str,
                relation_to_role: str = "unknown", profile_url: str = "", business_email: str = "",
                email_verification: str = "not_verified", confidence: str = "low",
                permitted_channel: str = "linkedin", checked_at: str | None = None) -> int:
    if not re.match(r"^https?://", source_url or ""):
        raise ContactRejected("a contact needs a source URL (public page where the person and role were seen)")
    if not name.strip() or not title.strip():
        raise ContactRejected("name and role title are required")
    if relation_to_role not in RELATIONS:
        raise ContactRejected(f"relation_to_role must be one of {RELATIONS}")
    if email_verification not in EMAIL_STATES:
        raise ContactRejected(f"email_verification must be one of {EMAIL_STATES}")
    if business_email:
        domain = business_email.rsplit("@", 1)[-1].lower()
        if email_verification not in ("source_published", "provider_verified"):
            raise ContactRejected("an email without a source that published it is not stored (never guess addresses)")
        if domain in FREE_MAIL:
            raise ContactRejected("personal or free-mail addresses are not stored")
    cur = store.db.execute(
        """INSERT INTO contacts(job_id,company,name,title,relation_to_role,profile_url,business_email,email_verification,
           source_url,checked_at,confidence,permitted_channel) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (job_id, company, name.strip(), title.strip(), relation_to_role, profile_url, business_email or None,
         email_verification, source_url, checked_at or now_iso(), confidence, permitted_channel))
    store.db.commit()
    store.audit("system", "contact_added", job_id, f"{name} / {title} / {source_url}")
    return cur.lastrowid


def contacts_for_job(store: Store, job_id: str) -> list:
    return store.db.execute("SELECT * FROM contacts WHERE job_id=? AND opt_out=0 ORDER BY id", (job_id,)).fetchall()


def opt_out(store: Store, contact_id: int) -> None:
    store.db.execute("UPDATE contacts SET opt_out=1 WHERE id=?", (contact_id,))
    store.db.commit()
    store.audit("candidate", "contact_opt_out", str(contact_id))

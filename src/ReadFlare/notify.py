import smtplib
import settings
import os
import socket
from email.message import EmailMessage
from watchlist import Priority
from diff import ChangeType
#---
import re
from collections import defaultdict

CH99_LABEL = re.compile(r"9903\.\d{2}\.\d{2}(?: \([^)]*\))?")


def group_ch99_changes(changes):
    # {("added" | "removed", "9903.88.15 (general)"): [codes]}
    groups = defaultdict(list)
    for c in changes:
        before = set(CH99_LABEL.findall(c["old_description"]))
        after = set(CH99_LABEL.findall(c["new_description"]))
        for ref in after - before:
            groups[("added", ref)].append(c["code"])
        for ref in before - after:
            groups[("removed", ref)].append(c["code"])
    return groups


def format_ch99_section(changes, max_codes=5):
    lines = []
    for (direction, ref), codes in sorted(groups_items := group_ch99_changes(changes).items()):
        shown = ", ".join(format_code(c) for c in sorted(codes)[:max_codes])
        more = f" and {len(codes) - max_codes} more" if len(codes) > max_codes else ""
        verb = "now applies to" if direction == "added" else "no longer applies to"
        lines.append(f" {ref} {verb} {len(codes)} code(s): {shown}{more}")
    return lines
#---
def build_digest(split, old_edition, new_edition):
    min_priority = Priority.HIGH
    watched = []
    related = []

    for c in split["watchlist"]:
        if c["priority"] >= min_priority:
            watched.append(c)
    
    watched_codes = {c["code"] for c in watched}

    related = []
    for c in split["related"]:
        if c["priority"] >= Priority.MEDIUM and not set(c["related_to"]) <= watched_codes:
            related.append(c)

    if not watched and not related:
        return None

    lines = []
    if watched:
        lines.append("Changes to your watchlist codes:\n")
        for c in watched:
            lines.append(format_change(c, old_edition, new_edition))
    if related:
        lines.append("\nRelated changes you might want to look at:\n")
        for c in related:
            lines.append(format_change(c, old_edition, new_edition))
            lines.append(f"    Related to: {', '.join(c['related_to'])}")
    return "\n".join(lines)

def send_alert(body, subject="HTS update: changes to tracked codes", attachments=()):
    if not settings.get_setting("email_enabled"):
        print("Email is not enabled in Settings.py")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.get_setting("email_from")
    msg["To"] = ', '.join(settings.get_setting("email_recipients"))
    msg.set_content(body)

    #email attachment
    for filename, content, subtype, in attachments:
        msg.add_attachment(content.encode("utf-8"), maintype="text", subtype=subtype, filename=filename)

    with smtplib.SMTP(settings.get_setting("smtp_host"), settings.get_setting("smtp_port"), timeout=30) as smtp:
        if settings.get_setting("smtp_use_tls"):
            smtp.starttls()
        password = os.environ.get("READFLARE_SMTP_PASSWORD")
        if settings.get_setting("smtp_user") and password:
            smtp.login(settings.get_setting("smtp_user"), password)
        smtp.send_message(msg)
    return True

def format_code(code):
    # "2404121090" -> "2404.12.10.90"
    parts = [code[:4], code[4:6], code[6:8], code[8:10]]
    return ".".join(p for p in parts if p)

def parent_context(code, edition):
    # ancestors of a code, top-down: heading (4), subheading (6), tariff line (8)
    lines = []
    for length in (4, 6, 8):
        if len(code) > length:
            prefix = code[:length]
            if prefix in edition:
                lines.append(f"{format_code(prefix)} {edition[prefix]}")
    return lines

def needs_context(description):
    return (description or "").strip().lower().startswith("other")

def format_change(c, old_edition, new_edition):
    # removed codes only exist in the old edition, everything else in the new one
    edition = old_edition if c["change_type"] == ChangeType.REMOVED else new_edition
    description = c["old_description"] if c["change_type"] == ChangeType.REMOVED else c["new_description"]

    lines = [f" [{c['change_type']}] {c['code']}"]

    if needs_context(description):
        parents = parent_context(c["code"], edition)
        if parents:
            lines.append(f"    Under: {parents[0]}")
            for parent in parents[1:]:
                lines.append(f"           {parent}")

    lines.append(f"    Before: {c['old_description'] or '(none)'}")
    lines.append(f"    After: {c['new_description'] or '(none)'}")
    return "\n".join(lines)

def send_test_email():
    # returns (ok, message) for the settings page to show
    if not settings.get_setting("smtp_host"):
        return False, "No mail server set. Enter the SMTP host first."
    if not settings.get_setting("email_recipients"):
        return False, "No recipients set. Add at least one email address."
    try:
        was_enabled = settings.get_setting("email_enabled")
        settings.set_setting("email_enabled", True)
        try:
            send_alert(
                subject="ReadFlare test email",
                body="If you can read this, ReadFlare can send HTS alerts with the current settings.",
            )
        finally:
            settings.set_setting("email_enabled", was_enabled)
        return True, "Test email sent. Check the recipients' inboxes (and spam folders)."
    except smtplib.SMTPNotSupportedError:
        return False, "This server doesn't support TLS. Turn TLS off (common for internal relays)."
    except smtplib.SMTPAuthenticationError:
        return False, "Login failed. Check the username and password. Microsoft 365 may require app-specific access or a relay instead."
    except smtplib.SMTPSenderRefused:
        return False, "The server rejected the From address. Ask IT which address this app is allowed to send as."
    except smtplib.SMTPRecipientsRefused:
        return False, "The server refused the recipients. An internal relay may only allow internal addresses, or this server's IP may need to be allowlisted."
    except (ConnectionRefusedError, socket.gaierror, socket.timeout, OSError) as e:
        return False, f"Can't reach the mail server ({e}). Check the host and port, and that this machine can reach it on the network."
    except Exception as e:
        return False, f"Unexpected error: {e}"
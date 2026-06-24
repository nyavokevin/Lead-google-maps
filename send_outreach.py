"""
send_outreach.py
----------------
Reads output/leads_outreach.csv and sends messages:
  - channel == 'email'     → sends via SMTP (Gmail/any provider)
  - channel == 'whatsapp'  → sends via Twilio WhatsApp API
  - channel == 'none'      → skipped (logged)

Features:
  - Dry-run mode (default ON) — prints messages without sending
  - Progress log saved to output/send_log.csv
  - Rate limiting (configurable delay between sends)
  - Resume support — skips already-sent leads (checks send_log)

Setup:
  pip install requests
  Copy .env.example → .env and fill in your credentials.

  Email (SMTP):
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=your@gmail.com
    SMTP_PASS=your_app_password   ← Gmail: use App Password, not main pwd
    SMTP_FROM=Ny Avo Kevin <your@gmail.com>

  WhatsApp (Twilio):
    TWILIO_SID=ACxxxxx
    TWILIO_TOKEN=your_auth_token
    TWILIO_WA_FROM=whatsapp:+14155238886   ← Twilio sandbox or verified number
"""

import os
import csv
import time
import smtplib
import json
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ─── Config ───────────────────────────────────────────────────────────────────

DRY_RUN            = True      # Set False to actually send
DELAY_BETWEEN_SENDS = 3        # seconds between sends (be polite, avoid bans)
MAX_SENDS_PER_RUN  = 50        # safety cap per run (avoid burning quota)

INPUT_CSV  = Path("output/leads_outreach.csv")
LOG_CSV    = Path("output/send_log.csv")


# ─── .env loader ──────────────────────────────────────────────────────────────

def load_dotenv(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


# ─── CSV helpers ──────────────────────────────────────────────────────────────

def load_outreach() -> list[dict]:
    if not INPUT_CSV.exists():
        print(f"[!] {INPUT_CSV} not found. Run collect_leads.py first.")
        return []
    with open(INPUT_CSV, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_already_sent() -> set[str]:
    """Return set of 'name|email_or_phone' already logged as sent."""
    if not LOG_CSV.exists():
        return set()
    sent = set()
    with open(LOG_CSV, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("status") == "sent":
                key = f"{row.get('name','')}|{row.get('contact','')}"
                sent.add(key)
    return sent


def append_log(rows: list[dict]) -> None:
    is_new = not LOG_CSV.exists()
    with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
        fields = ["timestamp", "name", "region", "channel", "contact", "status", "note"]
        writer = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            writer.writeheader()
        writer.writerows(rows)


# ─── Email sender ──────────────────────────────────────────────────────────────

def _build_smtp() -> smtplib.SMTP:
    host  = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port  = int(os.environ.get("SMTP_PORT", "587"))
    user  = os.environ.get("SMTP_USER", "")
    pwd   = os.environ.get("SMTP_PASS", "")
    if not user or not pwd:
        raise EnvironmentError("SMTP_USER and SMTP_PASS must be set in .env")
    server = smtplib.SMTP(host, port, timeout=30)
    server.ehlo()
    server.starttls()
    server.login(user, pwd)
    return server


def send_email(lead: dict, smtp: smtplib.SMTP) -> None:
    sender   = os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", ""))
    to_email = lead["email"]
    subject  = lead.get("subject", "(no subject)")
    body     = lead.get("body", "")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = to_email

    # Plain text version
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # Basic HTML version (preserve line breaks)
    html_body = "<br>\n".join(body.splitlines())
    msg.attach(MIMEText(f"<html><body><p>{html_body}</p></body></html>", "html", "utf-8"))

    smtp.sendmail(sender, to_email, msg.as_string())


# ─── WhatsApp sender (Twilio) ─────────────────────────────────────────────────

def send_whatsapp(lead: dict) -> None:
    try:
        from twilio.rest import Client as TwilioClient
    except ImportError:
        raise ImportError("pip install twilio  — then set TWILIO_SID, TWILIO_TOKEN, TWILIO_WA_FROM in .env")

    sid    = os.environ.get("TWILIO_SID", "")
    token  = os.environ.get("TWILIO_TOKEN", "")
    from_  = os.environ.get("TWILIO_WA_FROM", "whatsapp:+14155238886")

    if not sid or not token:
        raise EnvironmentError("TWILIO_SID and TWILIO_TOKEN must be set in .env")

    client = TwilioClient(sid, token)
    phone  = lead.get("whatsapp") or lead.get("phone") or ""
    # Ensure whatsapp: prefix
    to_ = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"

    client.messages.create(
        from_=from_,
        to=to_,
        body=lead.get("body", ""),
    )


# ─── Main send loop ───────────────────────────────────────────────────────────

def main():
    load_dotenv()

    rows    = load_outreach()
    sent    = load_already_sent()
    log_buf : list[dict] = []

    if not rows:
        return

    # Filter skippable rows
    to_send = [
        r for r in rows
        if r.get("channel") in ("email", "whatsapp")
        and f"{r.get('name','')}|{r.get('email') or r.get('whatsapp','')}" not in sent
    ]

    skipped_no_contact = sum(1 for r in rows if r.get("channel") == "none")
    already_sent_count  = len(rows) - len(to_send) - skipped_no_contact

    print(f"\n{'='*65}")
    print(f"  📬 Outreach Sender — {'DRY RUN (no actual sends)' if DRY_RUN else '🔴 LIVE MODE'}")
    print(f"{'='*65}")
    print(f"  Total rows in CSV : {len(rows)}")
    print(f"  Already sent      : {already_sent_count}")
    print(f"  No contact info   : {skipped_no_contact}")
    print(f"  Ready to send     : {len(to_send)}")
    print(f"  Cap this run      : {MAX_SENDS_PER_RUN}")
    print(f"{'='*65}\n")

    # Batch split
    email_leads = [r for r in to_send if r.get("channel") == "email"]
    wa_leads    = [r for r in to_send if r.get("channel") == "whatsapp"]

    sends_done  = 0
    smtp_conn   = None

    try:
        # ── Email sends ───────────────────────────────────────────────────────
        if email_leads:
            print(f"  📧 Sending {min(len(email_leads), MAX_SENDS_PER_RUN)} emails…\n")
            if not DRY_RUN:
                smtp_conn = _build_smtp()

            for lead in email_leads:
                if sends_done >= MAX_SENDS_PER_RUN:
                    break

                contact = lead.get("email", "")
                name    = lead.get("name", "?")
                log_row = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "name":      name,
                    "region":    lead.get("region", ""),
                    "channel":   "email",
                    "contact":   contact,
                    "status":    "",
                    "note":      "",
                }

                if DRY_RUN:
                    print(f"  [DRY] EMAIL → {contact}")
                    print(f"    Subject : {lead.get('subject','')}")
                    print(f"    Preview : {lead.get('body','')[:120]}…\n")
                    log_row["status"] = "dry_run"
                else:
                    try:
                        send_email(lead, smtp_conn)
                        print(f"  [✓] Email sent → {contact} ({name})")
                        log_row["status"] = "sent"
                        time.sleep(DELAY_BETWEEN_SENDS)
                    except Exception as e:
                        print(f"  [✗] Email failed → {contact}: {e}")
                        log_row["status"] = "failed"
                        log_row["note"]   = str(e)

                log_buf.append(log_row)
                sends_done += 1

        # ── WhatsApp sends ────────────────────────────────────────────────────
        # if wa_leads:
        #     print(f"\n  💬 Sending {min(len(wa_leads), MAX_SENDS_PER_RUN - sends_done)} WhatsApp messages…\n")

        #     for lead in wa_leads:
        #         if sends_done >= MAX_SENDS_PER_RUN:
        #             break

        #         contact = lead.get("whatsapp") or lead.get("phone", "")
        #         name    = lead.get("name", "?")
        #         log_row = {
        #             "timestamp": datetime.utcnow().isoformat(),
        #             "name":      name,
        #             "region":    lead.get("region", ""),
        #             "channel":   "whatsapp",
        #             "contact":   contact,
        #             "status":    "",
        #             "note":      "",
        #         }

        #         if DRY_RUN:
        #             print(f"  [DRY] WHATSAPP → {contact}")
        #             print(f"    Message : {lead.get('body','')[:200]}…\n")
        #             log_row["status"] = "dry_run"
        #         else:
        #             try:
        #                 send_whatsapp(lead)
        #                 print(f"  [✓] WhatsApp sent → {contact} ({name})")
        #                 log_row["status"] = "sent"
        #                 time.sleep(DELAY_BETWEEN_SENDS)
        #             except Exception as e:
        #                 print(f"  [✗] WhatsApp failed → {contact}: {e}")
        #                 log_row["status"] = "failed"
        #                 log_row["note"]   = str(e)

        #         log_buf.append(log_row)
        #         sends_done += 1

    finally:
        if smtp_conn:
            try:
                smtp_conn.quit()
            except Exception:
                pass

        if log_buf:
            append_log(log_buf)
            print(f"\n  [✓] Log saved → {LOG_CSV}")

    # ── Summary ───────────────────────────────────────────────────────────────
    sent_ok   = sum(1 for r in log_buf if r["status"] == "sent")
    dry_count = sum(1 for r in log_buf if r["status"] == "dry_run")
    failed    = sum(1 for r in log_buf if r["status"] == "failed")

    print(f"\n{'─'*65}")
    if DRY_RUN:
        print(f"  ✅ Dry run complete. {dry_count} messages previewed.")
        print(f"  Set DRY_RUN = False in send_outreach.py to actually send.")
    else:
        print(f"  ✅ Done. Sent: {sent_ok} | Failed: {failed}")
    print(f"{'─'*65}\n")


if __name__ == "__main__":
    main()
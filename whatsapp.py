"""
WhatsApp Lead Sender — Personal Account via WhatsApp Web
- Types message manually (doesn't rely on URL pre-fill)
- Retries if new-chat screen appears
- Saves history immediately after each attempt
"""

import pandas as pd
import time
import urllib.parse
import logging
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ─── CONFIG ────────────────────────────────────────────────────────────────────
CSV_FILE      = "emails_generes.csv"
DELAY_BETWEEN = 12
MAX_DAILY     = 50
LOG_FILE      = "whatsapp_log.txt"
HISTORY_FILE  = Path("leads_history/number_sent.txt")
MAX_RETRIES   = 3
RETRY_WAIT    = 5
# ───────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


def format_number(raw) -> str | None:
    if pd.isna(raw) or str(raw).strip() in ("", "nan", "0"):
        return None
    number = str(raw).strip().replace(" ", "").replace("-", "")
    if number.startswith("+261"):  return number
    if number.startswith("261"):   return "+" + number
    if number.startswith("0"):     return "+261" + number[1:]
    return "+261" + number


def load_sent_numbers() -> set[str]:
    if not HISTORY_FILE.exists():
        return set()
    return {
        line.strip()
        for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def save_sent_number(phone: str):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(phone + "\n")


def load_leads(csv_path: str) -> list[dict]:
    df = pd.read_csv(csv_path, dtype=str)
    sent_numbers = load_sent_numbers()
    leads, skipped = [], 0
    for _, row in df.iterrows():
        phone = format_number(row.get("whatsapp", ""))
        if not phone:
            skipped += 1
            log.warning(f"⚠️  Skipped '{row.get('name', '?')}' — no number")
            continue
        if phone in sent_numbers:
            skipped += 1
            log.info(f"⏭️  Already sent to '{row.get('name', '?')}' ({phone})")
            continue
        leads.append({"name": row.get("name", ""), "phone": phone, "message": row.get("body", "")})
    log.info(f"✅ {len(leads)} new leads | ⏭️  {skipped} skipped")
    return leads


def dismiss_popup(driver) -> bool:
    """Returns True if 'not on WhatsApp' popup was found and dismissed."""
    try:
        popups = driver.find_elements(By.CSS_SELECTOR, '[data-testid="confirm-popup"]')
        if not popups or not popups[0].is_displayed():
            return False
        buttons = driver.find_elements(By.CSS_SELECTOR, '[data-testid="confirm-popup"] button')
        if not buttons:
            return False
        driver.execute_script("arguments[0].click();", buttons[0])
        time.sleep(1)
        log.warning("  ⚠️  Popup dismissed — number not on WhatsApp")
        return True
    except Exception:
        return False


def open_chat(driver, phone: str, message: str) -> bool:
    """
    Open chat for a phone number. Retries if WhatsApp shows
    the new-chat/loading screen instead of the contact chat.
    Returns True when the message box is ready to type into.
    """
    # Keep ?text= so WhatsApp pre-fills, but we'll clear and retype anyway
    encoded = urllib.parse.quote(message)
    url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded}"

    for attempt in range(1, MAX_RETRIES + 1):
        if attempt > 1:
            log.info(f"  🔄 Retry {attempt}/{MAX_RETRIES}…")

        driver.get(url)
        time.sleep(5)

        if dismiss_popup(driver):
            return False

        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'div[aria-placeholder="Type a message"]')
                )
            )
            return True

        except TimeoutException:
            if dismiss_popup(driver):
                return False
            log.warning(f"  ⚠️  Message box not ready (attempt {attempt}), retrying in {RETRY_WAIT}s…")
            time.sleep(RETRY_WAIT)

    log.error(f"  ❌ Could not open chat after {MAX_RETRIES} attempts")
    return False


def type_and_send(driver, message: str) -> bool:
    """
    Clear the message box, type the message character by character,
    then click Send. Typing manually ensures WhatsApp activates the Send button.
    """
    try:
        # Get fresh reference to message box
        boxes = driver.find_elements(By.CSS_SELECTOR, 'div[aria-placeholder="Type a message"]')
        if not boxes:
            log.warning("  ❌ Message box disappeared before typing")
            return False

        box = boxes[0]
        box.click()
        time.sleep(0.5)

        # Clear any pre-filled text (from URL param if any)
        box.send_keys(Keys.CONTROL + "a")
        box.send_keys(Keys.COMMAND + "a")   # Mac
        time.sleep(0.3)
        box.send_keys(Keys.DELETE)
        box.send_keys(Keys.BACK_SPACE)
        time.sleep(0.3)

        # Type message using JS to handle special characters and newlines reliably
        # Split on newlines and send each line with Shift+Enter between them
        lines = message.split("\n")
        for j, line in enumerate(lines):
            driver.execute_script(
                "arguments[0].focus(); document.execCommand('insertText', false, arguments[1]);",
                box, line
            )
            time.sleep(0.1)
            if j < len(lines) - 1:
                box.send_keys(Keys.SHIFT + Keys.ENTER)
                time.sleep(0.1)

        time.sleep(1)  # wait for Send button to activate after typing

        # ── Click Send button ───────────────────────────────────────────────────
        try:
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Send"]'))
            )
            buttons = driver.find_elements(By.CSS_SELECTOR, 'button[aria-label="Send"]')
            if buttons:
                driver.execute_script("arguments[0].click();", buttons[0])
                time.sleep(2)
                log.info("  → Clicked Send button")
                return True
        except TimeoutException:
            pass

        # ── Fallback: Enter key ─────────────────────────────────────────────────
        box = driver.find_elements(By.CSS_SELECTOR, 'div[aria-placeholder="Type a message"]')
        if box:
            box[0].send_keys(Keys.ENTER)
            time.sleep(2)
            log.info("  → Sent via Enter key")
            return True

    except Exception as e:
        log.error(f"  ❌ type_and_send error: {e}")

    return False


def send_message(driver, phone: str, message: str) -> bool:
    chat_ready = open_chat(driver, phone, message)
    if not chat_ready:
        return False

    time.sleep(1)
    ok = type_and_send(driver, message)

    if dismiss_popup(driver):
        return False

    return ok


def send_messages(leads: list[dict]):
    options = webdriver.ChromeOptions()
    options.add_argument("--user-data-dir=./wa_session")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    sent = failed = 0

    try:
        driver.get("https://web.whatsapp.com")
        log.info("🔐 Waiting for WhatsApp Web (scan QR if needed)…")
        WebDriverWait(driver, 90).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'input[aria-label="Search or start a new chat"]')
            )
        )
        log.info("✅ Logged in!")

        for i, lead in enumerate(leads):
            if sent >= MAX_DAILY:
                log.warning(f"🛑 Daily cap of {MAX_DAILY} reached. Stopping.")
                break

            name, phone, msg = lead["name"], lead["phone"], lead["message"]
            log.info(f"[{i+1}/{len(leads)}] → {name} ({phone})")

            try:
                ok = send_message(driver, phone, msg)
            except Exception as e:
                log.error(f"  ❌ Unexpected error for {name}: {e}")
                ok = False

            if ok:
                log.info(f"  ✅ Sent to {name}")
            else:
                log.warning(f"  ❌ Skipped {name} — not on WhatsApp or failed")

            save_sent_number(phone)
            sent += ok
            failed += not ok

            if i < len(leads) - 1:
                log.info(f"  ⏳ Waiting {DELAY_BETWEEN}s…")
                time.sleep(DELAY_BETWEEN)

    finally:
        driver.quit()
        log.info("─" * 50)
        log.info(f"📊 DONE — ✅ Sent: {sent} | ❌ Failed/not on WA: {failed}")


if __name__ == "__main__":
    leads = load_leads(CSV_FILE)
    if not leads:
        log.info("✅ No new leads — all already contacted.")
    else:
        print(f"\n🚀 About to send to {len(leads)} new leads.")
        print("   Chrome will open — scan QR on first run.\n")
        input("   Press ENTER to start…\n")
        send_messages(leads)
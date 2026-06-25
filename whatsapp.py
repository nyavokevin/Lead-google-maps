"""
WhatsApp Lead Sender — Personal Account via WhatsApp Web
Selectors confirmed from live WhatsApp Web HTML.
"""

import pandas as pd
import time
import urllib.parse
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ─── CONFIG ────────────────────────────────────────────────────────────────────
CSV_FILE      = "emails_generes.csv"
DELAY_BETWEEN = 12
MAX_DAILY     = 40
LOG_FILE      = "whatsapp_log.txt"
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


def load_leads(csv_path: str) -> list[dict]:
    df = pd.read_csv(csv_path, dtype=str)
    leads, skipped = [], 0
    for _, row in df.iterrows():
        phone = format_number(row.get("whatsapp", ""))
        if not phone:
            skipped += 1
            log.warning(f"⚠️  Skipped '{row.get('name', '?')}' — no number")
            continue
        leads.append({"name": row.get("name", ""), "phone": phone, "message": row.get("body", "")})
    log.info(f"✅ {len(leads)} leads ready | ⚠️  {skipped} skipped")
    return leads


def check_not_on_whatsapp(driver) -> bool:
    """
    Detect the popup: data-testid="confirm-popup"
    Content: "The number +XXX isn't on WhatsApp."
    Returns True if popup appeared (number not on WA), and dismisses it.
    """
    try:
        popup = driver.find_element(By.CSS_SELECTOR, '[data-testid="confirm-popup"]')
        if popup.is_displayed():
            # Click the OK button inside the popup
            ok_btn = popup.find_element(By.CSS_SELECTOR, 'button')
            ok_btn.click()
            time.sleep(1)
            return True
    except NoSuchElementException:
        pass
    return False


def send_message(driver, phone: str, message: str) -> bool:
    encoded = urllib.parse.quote(message)
    driver.get(f"https://web.whatsapp.com/send?phone={phone}&text={encoded}")

    wait = WebDriverWait(driver, 20)

    # ── Wait for page to settle, then check for "not on WhatsApp" popup ────────
    time.sleep(4)
    if check_not_on_whatsapp(driver):
        return False  # number not on WhatsApp

    # ── Strategy 1: click Send button ──────────────────────────────────────────
    try:
        send_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Send"]'))
        )
        time.sleep(1)
        send_btn.click()
        time.sleep(2)

        # Double-check: popup may appear right after clicking
        if check_not_on_whatsapp(driver):
            return False

        return True
    except TimeoutException:
        pass

    # ── Strategy 2: Enter key on message box ───────────────────────────────────
    try:
        msg_box = driver.find_element(By.CSS_SELECTOR, 'div[aria-placeholder="Type a message"]')
        msg_box.send_keys(Keys.ENTER)
        time.sleep(2)
        return True
    except NoSuchElementException:
        pass

    return False


def send_messages(leads: list[dict]):
    options = webdriver.ChromeOptions()
    options.add_argument("--user-data-dir=./wa_session")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    sent = failed = not_on_wa = 0

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

            ok = send_message(driver, phone, msg)

            if ok:
                log.info(f"  ✅ Sent to {name}")
                sent += 1
            else:
                # Check if it was a "not on WhatsApp" vs other error
                log.warning(f"  ❌ {name} ({phone}) — not on WhatsApp or failed")
                not_on_wa += 1
                failed += 1

            if i < len(leads) - 1:
                log.info(f"  ⏳ Waiting {DELAY_BETWEEN}s…")
                time.sleep(DELAY_BETWEEN)

    finally:
        driver.quit()
        log.info("─" * 50)
        log.info(f"📊 DONE — ✅ Sent: {sent} | ❌ Not on WA / failed: {not_on_wa}")


if __name__ == "__main__":
    leads = load_leads(CSV_FILE)
    if not leads:
        log.error("No valid leads found.")
    else:
        print(f"\n🚀 About to send to {len(leads)} leads.")
        print("   Chrome will open — scan QR on first run.\n")
        input("   Press ENTER to start…\n")
        send_messages(leads)
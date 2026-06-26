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
CSV_FILE      = "output/leads_raw.csv"
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
    if number.startswith("+33"):  return number
    if number.startswith("33"):   return "+" + number
    if number.startswith("0"):     return "+33" + number[1:]
    return "+33" + number


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


def dismiss_popup(driver) -> bool:
    """
    Detect 'number not on WhatsApp' popup and dismiss it.
    Re-queries elements fresh each time to avoid StaleElementReferenceException.
    Uses JS click to avoid ElementNotInteractableException.
    """
    try:
        # find_elements returns [] instead of raising — safe against StaleElement
        popups = driver.find_elements(By.CSS_SELECTOR, '[data-testid="confirm-popup"]')
        if not popups or not popups[0].is_displayed():
            return False

        # Query button fresh in one shot — never reuse a stored reference
        buttons = driver.find_elements(By.CSS_SELECTOR, '[data-testid="confirm-popup"] button')
        if not buttons:
            return False

        # JS click bypasses both interactability and stale reference issues
        driver.execute_script("arguments[0].click();", buttons[0])
        time.sleep(1)
        log.warning("  ⚠️  Popup dismissed — number not on WhatsApp")
        return True

    except Exception as e:
        log.warning(f"  ⚠️  Popup check error (ignored): {e}")
        return False


def send_message(driver, phone: str, message: str) -> bool:
    encoded = urllib.parse.quote(message)
    driver.get(f"https://web.whatsapp.com/send?phone={phone}&text={encoded}")

    time.sleep(4)
    if dismiss_popup(driver):
        return False

    wait = WebDriverWait(driver, 20)

    # ── Strategy 1: JS click on Send button ────────────────────────────────────
    try:
        send_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Send"]'))
        )
        time.sleep(1)
        driver.execute_script("arguments[0].click();", send_btn)
        time.sleep(2)

        if dismiss_popup(driver):
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
                sent += 1
            else:
                log.warning(f"  ❌ Skipped {name} — not on WhatsApp or error")
                failed += 1

            if i < len(leads) - 1:
                log.info(f"  ⏳ Waiting {DELAY_BETWEEN}s…")
                time.sleep(DELAY_BETWEEN)

    finally:
        driver.quit()
        log.info("─" * 50)
        log.info(f"📊 DONE — ✅ Sent: {sent} | ❌ Not on WA / failed: {failed}")


if __name__ == "__main__":
    leads = load_leads(CSV_FILE)
    if not leads:
        log.error("No valid leads found.")
    else:
        print(f"\n🚀 About to send to {len(leads)} leads.")
        print("   Chrome will open — scan QR on first run.\n")
        input("   Press ENTER to start…\n")
        send_messages(leads)
"""
collect_leads.py
----------------
Full pipeline:
  1. Scrape 250 leads across 3 regions (Madagascar · France · International)
     using SerpApi (google_maps — no-website filter)
  2. Generate personalized email OR WhatsApp message via Claude API
  3. Export two CSVs:
       leads_raw.csv       — all leads with contact info (no messages)
       leads_outreach.csv  — leads with generated messages, ready to send

Target split:
  50 × Madagascar (5 cities × 10 leads)
  50 × France (5 cities × 10 leads)
  50 × International (5 cities × 10 leads)
  → 150 guaranteed no-website leads (message generated for all)
  → Up to 100 bonus leads with website (low-rating) if quota not met

Setup:
  pip install requests
  export SERPAPI_KEY="your_key"
  # No LM Studio needed — uses Claude API (already connected in claude.ai)
"""

import os
import csv
import time
from pathlib import Path
from lib.serpapi import (
    REGION_TARGETS,
    PROSPECT_QUERIES,
    find_no_website_leads,
    find_low_rated_leads,
    extract_contacts,
)
from lib.message_gen import generate_messages_batch


# ─── Config ───────────────────────────────────────────────────────────────────

TARGET_PER_REGION = {
    "madagascar":    50,
    "france":        50,
    "international": 50,
}
LEADS_PER_CITY   = 10   # target per city (regions have 5 cities each)
PAGES_PER_QUERY  =  1   # 1 page = 20 results scanned = 1 SerpApi credit
MAX_OUTREACH     = 250  # cap for message generation

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

RAW_CSV      = OUTPUT_DIR / "leads_raw.csv"
OUTREACH_CSV = OUTPUT_DIR / "leads_outreach.csv"


def _section(title: str) -> None:
    print(f"\n{'='*65}\n  {title}\n{'='*65}")


def load_dotenv(dotenv_file: str = ".env") -> None:
    path = Path(dotenv_file)
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key   = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def save_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        print(f"  [!] Nothing to save → {path}")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  [✓] {len(rows)} rows → {path}")


# ─── Lead collection ──────────────────────────────────────────────────────────

def collect_region(
    targets: list[tuple],
    region_label: str,
    goal: int,
) -> list[dict]:
    """
    Collect up to `goal` no-website leads from all cities in the region.
    Falls back to low-rated leads if quota is not met.
    """
    all_contacts: list[dict] = []
    per_city_goal = max(2, goal // len(targets))

    for city_name, lat, lon, country, language, _ in targets:
        if len(all_contacts) >= goal:
            break

        city_contacts: list[dict] = []
        print(f"\n  📍 {city_name} ({region_label})")

        for query in PROSPECT_QUERIES:
            if len(city_contacts) >= per_city_goal:
                break
            try:
                raw = find_no_website_leads(
                    query=query,
                    lat=lat, lon=lon,
                    language=language,
                    country=country,
                    pages=PAGES_PER_QUERY,
                )
                contacts = extract_contacts(
                    raw,
                    region_label=region_label,
                    city_name=city_name,
                    language=language,
                )
                # Deduplicate by name+address
                seen = {f"{c['name']}|{c['address']}" for c in city_contacts}
                fresh = [c for c in contacts if f"{c['name']}|{c['address']}" not in seen]
                city_contacts.extend(fresh)
                print(f"    [{query}] → {len(fresh)} no-website leads")
                time.sleep(0.5)   # polite delay
            except Exception as e:
                print(f"    [!] {query}: {e}")

        if len(city_contacts) < per_city_goal:
            shortfall = per_city_goal - len(city_contacts)
            print(f"    → Short by {shortfall}, fetching low-rated leads as fallback…")
            try:
                raw = find_low_rated_leads(
                    query="entreprise",
                    lat=lat, lon=lon,
                    max_rating=3.5,
                    language=language,
                    country=country,
                    pages=1,
                )
                contacts = extract_contacts(raw, region_label, city_name, language)
                seen = {f"{c['name']}|{c['address']}" for c in city_contacts}
                fresh = [c for c in contacts if f"{c['name']}|{c['address']}" not in seen]
                city_contacts.extend(fresh[:shortfall])
                print(f"    [fallback] → {len(fresh[:shortfall])} low-rated leads added")
            except Exception as e:
                print(f"    [!] Fallback failed: {e}")

        all_contacts.extend(city_contacts[:per_city_goal])
        print(f"    City total: {len(city_contacts[:per_city_goal])} | Region running total: {len(all_contacts)}")

    return all_contacts[:goal]


def collect_all_leads() -> list[dict]:
    regions: dict[str, list] = {"madagascar": [], "france": [], "international": []}
    for target in REGION_TARGETS:
        regions[target[5]].append(target)

    all_leads: list[dict] = []

    for region_label, goal in TARGET_PER_REGION.items():
        _section(f"Region: {region_label.upper()} — goal: {goal} leads")
        leads = collect_region(regions[region_label], region_label, goal)
        all_leads.extend(leads)
        print(f"\n  ✅ {region_label}: {len(leads)} leads collected")

    return all_leads


def main():
    load_dotenv(Path(__file__).resolve().parent / ".env")

    if not os.environ.get("SERPAPI_KEY"):
        print("\n[!] SERPAPI_KEY missing. Run:\n    export SERPAPI_KEY=your_key\n")
        exit(1)

    _section("STEP 1 — Collecting leads from SerpApi")
    all_leads = collect_all_leads()

    print(f"\n  📊 Total raw leads collected: {len(all_leads)}")
    save_csv(all_leads, RAW_CSV)

    if not all_leads:
        print("[!] No leads found. Check your SERPAPI_KEY and network.")
        return

    _section(f"STEP 2 — Generating messages for up to {MAX_OUTREACH} leads")
    print(f"  Leads with email: {sum(1 for l in all_leads if l.get('email'))}")
    print(f"  Leads with phone: {sum(1 for l in all_leads if l.get('phone'))}")
    print(f"  Leads with neither: {sum(1 for l in all_leads if not l.get('email') and not l.get('phone'))}\n")

    messages = generate_messages_batch(all_leads, max_leads=MAX_OUTREACH, verbose=True)

    _section("STEP 3 — Saving outreach CSV")
    save_csv(messages, OUTREACH_CSV)

    by_channel = {"email": 0, "whatsapp": 0, "none": 0}
    by_region  = {}
    for m in messages:
        by_channel[m.get("channel", "none")] = by_channel.get(m.get("channel","none"), 0) + 1
        r = m.get("region", "unknown")
        by_region[r] = by_region.get(r, 0) + 1

    print(f"\n{'─'*65}")
    print(f"  ✅ Done! {len(messages)} messages generated.")
    print(f"\n  By channel:")
    for ch, count in by_channel.items():
        print(f"    {ch:10s}: {count}")
    print(f"\n  By region:")
    for rg, count in by_region.items():
        print(f"    {rg:14s}: {count}")
    print(f"\n  Files:")
    print(f"    {RAW_CSV}")
    print(f"    {OUTREACH_CSV}")
    print(f"{'─'*65}\n")


if __name__ == "__main__":
    main()

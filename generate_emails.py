"""
generate_emails.py
------------------
Reads a leads dataset (JSON array) from the `dataset/` folder, pings each
lead's website to catch broken/missing sites, generates a personalized cold
email for each lead via a local LM Studio model, and writes the results to
`emails_generes.csv` (which `whatsapp.py` consumes).

Pipeline:
    dataset/<file>.json → website check → LM Studio (email) → emails_generes.csv

Setup:
    pip install requests
    cp env.example .env   and set LM_STUDIO_HOST, LM_STUDIO_PORT, LM_MODEL

Run:
    python generate_emails.py                         # default dataset, French
    python generate_emails.py --lang=en               # English emails
    python generate_emails.py dataset/other.json --lang=en --skip-website-check
"""

import os
import sys
import json
import csv
import argparse
from pathlib import Path

from lib.lmstudio import generate_emails_for_leads, print_email
from website_checker import check_leads_websites


# ─── Config ───────────────────────────────────────────────────────────────────

OUTPUT_CSV  = Path("emails_generes.csv")
MODEL       = os.environ.get("LM_MODEL", "google/gemma-4-e4b")
MAX_LEADS   = 100


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate cold emails from a leads dataset JSON via LM Studio."
    )
    parser.add_argument(
        "dataset",
        nargs="?",
        default=os.environ.get("DATASET_FILE", "dataset/dataset_reastau_NA.json"),
        help="Path to the leads dataset JSON file (default: dataset/dataset_reastau_NA.json, "
             "or DATASET_FILE env var).",
    )
    parser.add_argument(
        "--skip-website-check",
        action="store_true",
        help="Skip pinging websites (faster, but no broken-site note in emails).",
    )
    parser.add_argument(
        "--lang",
        choices=["fr", "en"],
        default="fr",
        help="Language of the generated emails (fr = French [default], en = English).",
    )
    return parser.parse_args(argv)


# ─── .env loader ──────────────────────────────────────────────────────────────

def load_dotenv(dotenv_file: str = ".env") -> None:
    path = Path(dotenv_file)
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


# ─── Lead mapping (dataset JSON → lead dict expected by lib.lmstudio) ─────────

def to_lead(item: dict) -> dict:
    """Map a dataset JSON entry into the lead dict lib.lmstudio expects."""
    phone = item.get("phoneUnformatted") or item.get("phone", "")
    return {
        "title":    item.get("title", ""),
        "name":     item.get("title", item.get("name", "")),
        "type":     item.get("categoryName", ""),   # classify_lead() reads "type"
        "address":  item.get("address", ""),
        "rating":   item.get("rating", ""),
        "whatsapp": phone,
        "phone":    phone,
        "email":    item.get("email", ""),
        "website":  item.get("website", ""),         # needed by website_checker
    }


def load_leads(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array of lead objects")
    return [to_lead(item) for item in data]


def save_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        print(f"  [!] Nothing to save → {path}")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  [✓] {len(rows)} emails → {path}")


def main() -> None:
    args = parse_args()
    input_json = Path(args.dataset)
    load_dotenv()

    if not input_json.exists():
        print(f"\n[!] Dataset not found: {input_json}")
        print(f"    Pass the path as an argument: python generate_emails.py path/to/leads.json\n")
        exit(1)

    if not MODEL or not MODEL.strip():
        print("\n[!] LM_MODEL not set. Add it to .env, e.g.:")
        print("    LM_MODEL=google/gemma-4-e4b\n")
        exit(1)

    print(f"\n{'='*65}")
    print(f"  📧 Email generator — LM Studio ({MODEL})  [lang: {args.lang}]")
    print(f"  Dataset : {input_json}")
    print(f"{'='*65}\n")

    leads = load_leads(input_json)
    print(f"  📊 {len(leads)} leads loaded from dataset")

    # Ping each website before generating emails, so the prompt can reference
    # a broken/missing site instead of guessing.
    if not args.skip_website_check:
        leads = check_leads_websites(leads, max_workers=10)
    else:
        for lead in leads:
            lead["website_status"] = None
            lead["website_note"] = None

    emails = generate_emails_for_leads(leads, model_name=MODEL, max_leads=MAX_LEADS, lang=args.lang)

    print()
    save_csv(emails, OUTPUT_CSV)

    for email in emails:
        print_email(email)

    print(f"\n{'─'*65}")
    print(f"  ✅ Done — {len(emails)} emails generated.")
    print(f"{'─'*65}\n")


if __name__ == "__main__":
    main()

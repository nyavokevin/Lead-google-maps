# Plan: Trim project to LM Studio + email + WhatsApp(Selenium)

## Goal
Keep only what is needed for the local pipeline:
**dataset JSON → emails via LM Studio → `emails_generes.csv` → send via WhatsApp (Selenium)**.
Make the LM Studio host/port configurable through env (currently hardcoded `192.168.16.106:1234`).

The "create email from LM Studio" script reads a **JSON file from the `dataset/` folder**
(`dataset/dataset_reastau_NA.json`) instead of a CSV. Each JSON entry is mapped into the
lead dict that `lib.lmstudio` expects.

## KEEP (and modify)
- `lib/llm_http.py` — LM Studio HTTP connector. Make host/port env-driven.
- `lib/lmstudio.py` — email generation from LM Studio. Drop SerpApi dependency.
- `whatsapp.py` — WhatsApp sender via Selenium (reads `emails_generes.csv`). No change.
- `lib/__init__.py` — keep (already imports `lib.lmstudio`).

## CREATE
- `generate_emails.py` — new script: loads `.env`, reads a **JSON dataset file** from `dataset/`,
  maps each entry into a lead dict, calls `lib.lmstudio.generate_emails_for_leads`,
  writes `emails_generes.csv`.
- `dataset/` folder is **kept** (it holds the input leads JSON).

## DELETE
- `ollama.py` (redundant `lmstudio` package demo)
- `script.py` (SerpApi demos; superseded by `generate_emails.py`)
- `collect_leads.py` (SerpApi + `message_gen` pipeline)
- `send_outreach.py` (SMTP/Twilio; not Selenium WhatsApp)
- `db.py` (PostgreSQL layer, unused by kept scripts)
- `lib/message_gen.py` (alt LM Studio message gen via package)
- `lib/serpapi.py` (SerpApi scraping, removed dependency)
- `lib/__pycache__/*`
- Any stray root-level `leads.csv` / `*.csv` demo outputs if present (not the `dataset/` JSON).

## Changes detail

### 1. `lib/llm_http.py`
- Add `import os`.
- `LMStudioClient.__init__(self, host=None, port=None, timeout=120)`:
  - `host = host or os.environ.get("LM_STUDIO_HOST", "192.168.16.106")`
  - `port = port if port is not None else int(os.environ.get("LM_STUDIO_PORT", "1234"))`
  - Keep `self.base_url = f"http://{host}:{port}/v1"`.

### 2. `lib/lmstudio.py`
- Replace `from .serpapi import extract_contacts` (delete that import).
- Line 19: `_client = LMStudioClient()` (reads env; drop hardcoded `host='192.168.16.106', port='1234'`).
- In `generate_email_for_lead`: replace
  `contact = extract_contacts([lead])[0]` and the `whatsapp`/`email` fields with
  `"whatsapp": lead.get("whatsapp", lead.get("phone", "")), "email": lead.get("email", "")`.
- Keep `classify_lead`, `generate_email_for_lead`, `generate_emails_for_leads`, `print_email`.

### 3. `generate_emails.py` (new) — reads dataset JSON, not CSV
- `load_dotenv()` helper (KEY=VALUE, same style as deleted scripts).
- `INPUT_JSON = Path(os.environ.get("DATASET_FILE", "dataset/dataset_reastau_NA.json"))`.
  The file is a JSON **array of objects**, e.g.:
  ```json
  [{"title":"Lena Trattoria","categoryName":"Italian restaurant",
    "address":"3470 E Tremont Ave, Bronx, NY 10465","website":"https://...",
    "phone":"(718) 239-5362","phoneUnformatted":"+17182395362",
    "location":{"lat":40.8315,"lng":-73.8273}}, ...]
  ```
- Map each entry to the lead dict `lib.lmstudio` expects (`title`, `name`, `type`, `address`,
  `rating`, `whatsapp`/`phone`, `email`):
  ```python
  def to_lead(item: dict) -> dict:
      phone = item.get("phoneUnformatted") or item.get("phone", "")
      return {
          "title":   item.get("title", ""),
          "name":    item.get("title", ""),
          "type":    item.get("categoryName", ""),   # classify_lead reads "type"
          "address": item.get("address", ""),
          "rating":  item.get("rating", ""),
          "whatsapp": phone,
          "phone":    phone,
          "email":    item.get("email", ""),          # usually empty in this dataset
      }
  ```
- `OUTPUT_CSV = Path("emails_generes.csv")` — columns `name, category, subject, body, whatsapp, email`
  (whatsapp.py needs `name`, `whatsapp`, `body`).
- `MODEL = os.environ.get("LM_MODEL", "google/gemma-4-e4b")`.
- `main()`: load_dotenv → verify INPUT_JSON exists → `leads = [to_lead(i) for i in json.load(...)]` →
  `emails = generate_emails_for_leads(leads, model_name=MODEL, max_leads=100)` →
  write OUTPUT_CSV → `print_email` each.
- Error out clearly if `LM_MODEL` missing or INPUT_JSON absent / not valid JSON.

> Note: the dataset has **no `email` field**, so generated rows will have an empty `email`
> column — that is expected; the script still produces the email **message** (subject+body)
> from LM Studio. `whatsapp` is populated from `phoneUnformatted` for sending via WhatsApp.

> Risk: `whatsapp.py` `format_number()` currently assumes **+261 (Madagascar)** numbers
> (`+261` prefix logic). This dataset has **US (+1)** numbers, so `format_number` would
> produce a wrong `+261+1...` value. Out of scope for this change, but flag it: the
> WhatsApp sender must be updated to handle the dataset's country code, or it will fail.

### 4. `env.example`
Replace contents with LM Studio settings only:
```
# ─── LM Studio ──────────────────────────────────────────────────────────────
# IP/host of the machine running LM Studio (the "script that connects to LM Studio")
LM_STUDIO_HOST=192.168.16.106
LM_STUDIO_PORT=1234
# Exact model identifier shown in LM Studio
LM_MODEL=google/gemma-4-e4b
```

## Validation
- `python -c "from lib.llm_http import LMStudioClient; c=LMStudioClient(); print(c.base_url)"` → prints `http://192.168.16.106:1234/v1` (and honors env overrides).
- `python -c "import lib.lmstudio"` imports cleanly (no `serpapi` import error).
- `python generate_emails.py` (with `dataset/dataset_reastau_NA.json` present) produces `emails_generes.csv` with `name,whatsapp,body` columns.
- `python whatsapp.py` still loads `emails_generes.csv` (no schema change).
- Confirm deleted files no longer referenced anywhere (`grep` for `serpapi`, `message_gen`, `collect_leads`, `send_outreach`, `db`, `ollama`).

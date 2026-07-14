# Outreach Pipeline — Ny Avo Kevin

Local lead → email → WhatsApp pipeline powered by a local LM Studio model.

Pipeline:

```
dataset/*.json  →  generate_emails.py (LM Studio)  →  emails_generes.csv  →  whatsapp.py (Selenium)
```

---

## Project structure

```
outreach/
├── lib/
│   ├── llm_http.py     # LM Studio OpenAI-compatible HTTP client
│   └── lmstudio.py     # Email generation from LM Studio (no external APIs)
├── generate_emails.py  # Step 1+2: dataset JSON → generated emails CSV
├── whatsapp.py         # Step 3: send via WhatsApp Web (Selenium)
├── env.example         # Copy to .env and set LM Studio host/port/model
└── emails_generes.csv  # Generated output (auto-created), read by whatsapp.py
```

---

## Setup

```bash
pip install pandas selenium
cp env.example .env
# Edit .env with your LM Studio host/port and model id
```

### Settings needed

| Key | Description |
|-----|-------------|
| `LM_STUDIO_HOST` | IP/host of the machine running LM Studio |
| `LM_STUDIO_PORT` | Port LM Studio listens on (default 1234) |
| `LM_MODEL` | Exact model identifier shown in LM Studio |

> **LM Studio required.** Start LM Studio and load the model you set in `LM_MODEL`
> (it exposes an OpenAI-compatible API at `http://<host>:<port>/v1`).

---

## Step 1 & 2 — Generate emails

`generate_emails.py` reads a JSON dataset of leads (an array of objects) from the
`dataset/` folder. By default it uses `dataset/dataset_reastau_NA.json`; override with the
`DATASET_FILE` env var. Each entry is mapped to the fields LM Studio needs:

| Dataset field | Mapped to | Description |
|---------------|-----------|-------------|
| `title` | `name` / `title` | Business name |
| `categoryName` | `type` | Business type (used to classify the pitch) |
| `address` | `address` | Full address |
| `phoneUnformatted` / `phone` | `whatsapp` / `phone` | Phone number for WhatsApp |
| `email` | `email` | Email address (usually empty in this dataset) |

Then run:

```bash
python generate_emails.py
```

This writes `emails_generes.csv` with columns `name, category, subject, body, whatsapp, email`.

---

## Step 3 — Send via WhatsApp

```bash
python whatsapp.py
```

Reads `emails_generes.csv`, opens WhatsApp Web via Selenium (Chrome), and sends each
message. Scan the QR code on first run. Sent numbers are tracked in
`leads_history/number_sent.txt` so already-contacted leads are skipped.

**Safety features:**
- `MAX_DAILY = 40` — daily cap
- `DELAY_BETWEEN = 12` — seconds between sends
- `MAX_RETRIES = 3` — retries if the chat screen doesn't load

---

## Customization

### Add business categories
Edit `CATEGORY_KEYWORDS` and the pitch maps (`_build_system_prompt`) in `lib/lmstudio.py`.

### Your services (edit the pitch)
Kevin's specializations live in the pitch dictionaries inside
`lib/lmstudio.py` (restaurant, hotel, medical, legal, accounting, retail, education, generic):
- **ERP** (medical, legal, accounting, retail, hotel)
- **Web application** (all categories)
- **E-commerce** (retail)

---

## Tips

- **WhatsApp Web via Selenium** uses your personal account. Respect WhatsApp's
  anti-spam limits — keep the daily cap low and the delay between sends high.
- **Numbers** are normalized in `whatsapp.py`. Its `format_number()` currently defaults to
  `+261` (Madagascar). For datasets with other country codes (e.g. the US `+1` entries in
  `dataset_reastau_NA.json`), update `format_number()` to handle the correct prefix, or
  sends will fail.

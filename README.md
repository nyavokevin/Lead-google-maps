# Outreach Pipeline — Ny Avo Kevin

Automated lead collection + personalized message generation + email/WhatsApp sender.

---

## Project structure

```
outreach/
├── lib/
│   ├── serpapi.py       # SerpApi wrapper — multi-region lead scraping
│   └── message_gen.py   # Claude API — generates email or WhatsApp message per lead
├── collect_leads.py     # Step 1 + 2: scrape leads → generate messages → CSV
├── send_outreach.py     # Step 3: send email (SMTP) or WhatsApp (Twilio)
├── .env.example         # Copy to .env and fill in your keys
└── output/
    ├── leads_raw.csv        # All leads with contact info (no messages)
    ├── leads_outreach.csv   # Leads + generated messages, ready to send
    └── send_log.csv         # Send history (auto-created)
```

---

## Setup

```bash
pip install requests twilio
cp .env.example .env
# Edit .env with your real keys
```

### Keys needed

| Key | Where to get it |
|-----|----------------|
| `SERPAPI_KEY` | https://serpapi.com — free trial: 100 searches/month |
| `SMTP_USER` / `SMTP_PASS` | Gmail App Password: https://myaccount.google.com/apppasswords |
| `TWILIO_SID` / `TWILIO_TOKEN` | https://www.twilio.com — free sandbox available |

> **No LM Studio needed.** Messages are generated via Claude API (already connected in claude.ai).

---

## Step 1 & 2 — Collect leads + generate messages

```bash
export SERPAPI_KEY=your_key     # or put it in .env
python collect_leads.py
```

**What it does:**
- Scrapes **250 leads** across 3 regions (no-website filter):
  - 🇲🇬 50 × Madagascar (Antananarivo, Toamasina, Antsirabe, Fianarantsoa, Mahajanga)
  - 🇫🇷 50 × France (Paris, Lyon, Marseille, Bordeaux, Nantes)
  - 🌍 50 × International (Dubai, London, Toronto, Singapore, Nairobi)
- For each lead:
  - If **email found** → generates a full professional email (subject + body)
  - If **phone only** → generates a short professional WhatsApp message (≤320 chars)
- Language adapts: French for Madagascar/France, English for international
- Pitch adapts to business type: ERP-first for medical/legal/accounting, web for resto/hotel, mobile/web app for tech
- Saves `output/leads_raw.csv` and `output/leads_outreach.csv`

### SerpApi cost estimate
- 5 cities × 3 regions × 5 queries × 1 page = **75 API credits**
- Fallback queries: up to ~15 extra = **~90 credits total**
- Free plan: 100/month → upgrade or space your runs

---

## Step 3 — Send messages

```bash
python send_outreach.py
```

**Default: DRY RUN** — prints messages, does NOT send.

To actually send, open `send_outreach.py` and set:
```python
DRY_RUN = False
```

**Sending logic:**
- `channel == 'email'` → SMTP (Gmail or any provider)
- `channel == 'whatsapp'` → Twilio WhatsApp API
- `channel == 'none'` → skipped (no contact info found)

**Safety features:**
- `MAX_SENDS_PER_RUN = 50` — cap per run (edit to increase)
- `DELAY_BETWEEN_SENDS = 3` — seconds between sends
- Resume support — already-sent leads are skipped (tracked in `send_log.csv`)

---

## CSV columns

### leads_outreach.csv
| Column | Description |
|--------|-------------|
| `name` | Business name |
| `category` | Classified type (restaurant, hotel, medical, legal, accounting, retail, tech, generic…) |
| `channel` | `email` / `whatsapp` / `none` |
| `subject` | Email subject (empty for WA) |
| `body` | Full message body |
| `email` | Email address (if found) |
| `whatsapp` | Phone number for WhatsApp |
| `phone` | Raw phone |
| `city` | City scraped from |
| `region` | `madagascar` / `france` / `international` |
| `language` | `fr` / `en` |
| `website` | Website (empty = no-website lead) |
| `rating` | Google Maps rating |
| `address` | Full address |
| `place_id` | Google Maps place_id |

---

## Customization

### Add more cities
Edit `REGION_TARGETS` in `lib/serpapi.py`:
```python
("Toliara", -23.3500, 43.6667, "mg", "fr", "madagascar"),
```

### Change target quota
Edit `TARGET_PER_REGION` in `collect_leads.py`:
```python
TARGET_PER_REGION = {
    "madagascar":    100,
    "france":        100,
    "international": 50,
}
```

### Add business categories
Edit `CATEGORY_KEYWORDS` and `PITCH_BY_CATEGORY` in `lib/message_gen.py`.

### Your services (edit the pitch)
Kevin's specializations are set in `lib/message_gen.py → PITCH_BY_CATEGORY`:
- **ERP** (medical, legal, accounting, retail, hotel)
- **Web application** (all categories)
- **Mobile app** (tech, on request)

---

## Tips

- **WhatsApp Business API**: Twilio sandbox works for testing but requires the recipient to opt in first. For production, use a verified Twilio number or the Meta Cloud API.
- **Gmail App Password**: never use your real password. Generate at https://myaccount.google.com/apppasswords (2FA must be enabled).
- **SerpApi email extraction**: Google Maps rarely shows emails publicly. Most leads will be `channel=whatsapp`. To enrich emails, consider adding a Hunter.io or Apollo.io step.
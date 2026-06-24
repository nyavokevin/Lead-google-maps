"""
main.py
-------
Démonstration de toutes les fonctions de serpapi_lib.py.

Setup:
    pip install requests
    export SERPAPI_KEY="your_api_key_here"
"""

import os
import csv
from pathlib import Path
from lib.serpapi import (
    search_places_maps,
    get_place_details,
    search_places_local,
    search_jobs,
    find_no_website_leads,
    find_low_rated_leads,
    find_tech_companies,
    paginate_maps_search,
    extract_contacts,
    CITY_COORDS,
)


def load_dotenv(dotenv_file: str = ".env") -> None:
    """Load simple KEY=VALUE pairs from a .env file into os.environ.

    Existing environment variables are not overwritten.
    """
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


# Load .env from the script directory if present
load_dotenv(Path(__file__).resolve().parent / ".env")

# ─── Config ───────────────────────────────────────────────────────────────────

# os.environ["SERPAPI_KEY"] = "your_key_here"  # ou export SERPAPI_KEY=...

LOCATION = "Antananarivo, Madagascar"   # doit être dans CITY_COORDS
COUNTRY  = "mg"                         # code ISO pays
LANGUAGE = "fr"                         # langue des résultats


def _section(title: str) -> None:
    print(f"\n{'='*60}\n  {title}\n{'='*60}")


def _save_csv(contacts: list[dict], filename: str) -> None:
    if not contacts:
        print(f"  [!] Aucun résultat à sauvegarder dans {filename}")
        return
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=contacts[0].keys())
        writer.writeheader()
        writer.writerows(contacts)
    print(f"  [✓] {len(contacts)} contacts → {filename}")


# ─── 1. Recherche Maps de base ────────────────────────────────────────────────

def demo_maps_search():
    _section("1. Google Maps — restaurants à Antananarivo")
    places = search_places_maps(
        query="restaurant",
        location=LOCATION,
        language=LANGUAGE,
        country=COUNTRY,
    )
    for p in places[:5]:
        print(f"  • {p.get('title')} | ⭐{p.get('rating')} | {p.get('address')}")


# ─── 2. Détails d'un lieu ─────────────────────────────────────────────────────

def demo_place_details():
    _section("2. Détails d'un hôtel (téléphone, site, horaires)")
    places = search_places_maps(
        query="hotel",
        location=LOCATION,
        language=LANGUAGE,
        country=COUNTRY,
    )
    if not places:
        print("  [!] Aucun résultat.")
        return

    first = places[0]
    print(f"  Lieu : {first.get('title')} (place_id={first.get('place_id')})")
    details = get_place_details(place_id=first["place_id"], language=LANGUAGE)
    print(f"  Téléphone : {details.get('phone', 'N/A')}")
    print(f"  Site web  : {details.get('website', 'N/A')}")
    print(f"  Horaires  : {details.get('hours', 'N/A')}")
    print(f"  Note      : {details.get('rating')} ({details.get('reviews', 0)} avis)")


# ─── 3. Google Local (pas besoin de GPS) ──────────────────────────────────────

def demo_local_search():
    _section("3. Google Local — cabinets d'avocats")
    results = search_places_local(
        query="cabinet d'avocat",
        location=LOCATION,
        language=LANGUAGE,
        country=COUNTRY,
    )
    for r in results[:5]:
        print(f"  • {r.get('title')} | {r.get('address')} | {r.get('phone', 'pas de tel')}")


# ─── 4. Recherche d'emploi / missions freelance ───────────────────────────────

def demo_job_search():
    _section("4a. Jobs Python/Django remote")
    jobs = search_jobs(
        role="Python developer Django remote",
        language="en",
        country="us",
        num=10,
    )
    for j in jobs[:5]:
        print(f"  • {j.get('title')}")
        print(f"    {j.get('link')}")
        print()

    _section("4b. Missions freelance dev web sur LinkedIn")
    gigs = search_jobs(
        role="freelance web developer Madagascar",
        site="linkedin.com",
        language="en",
        country="us",
    )
    for j in gigs[:3]:
        print(f"  • {j.get('title')} — {j.get('link')}")


# ─── 5. Leads sans site web ───────────────────────────────────────────────────

def demo_no_website_leads():
    _section("5. Restaurants SANS site web (leads création de site)")
    leads = find_no_website_leads(
        query="restaurant",
        location=LOCATION,
        language=LANGUAGE,
        country=COUNTRY,
        pages=2,   # 2 × 20 résultats scannés = 2 crédits API
    )
    contacts = extract_contacts(leads)
    print(f"  {len(contacts)} leads sans site trouvés")
    for c in contacts[:5]:
        print(f"  • {c['name']} | {c['address']} | {c['phone'] or 'pas de tel'}")
    _save_csv(contacts, "leads_sans_site.csv")


# ─── 6. Leads mal notés ───────────────────────────────────────────────────────

def demo_low_rating_leads():
    _section("6. Hôtels mal notés ≤ 3.5 (leads refonte digitale)")
    leads = find_low_rated_leads(
        query="hotel",
        location=LOCATION,
        language=LANGUAGE,
        country=COUNTRY,
        max_rating=3.5,
        pages=2,
    )
    contacts = extract_contacts(leads)
    print(f"  {len(contacts)} hôtels notés ≤ 3.5")
    for c in contacts[:5]:
        print(f"  • {c['name']} | ⭐{c['rating']} | {c['website'] or 'pas de site'}")
    _save_csv(contacts, "leads_mal_notes.csv")


# ─── 7. Entreprises tech / agences ────────────────────────────────────────────

def demo_tech_companies():
    _section("7. Entreprises tech / agences web (leads emploi ou partenariat)")
    companies = find_tech_companies(
        location=LOCATION,
        language=LANGUAGE,
        country=COUNTRY,
    )
    contacts = extract_contacts(companies)
    print(f"  {len(contacts)} résultats tech/agence")
    for c in contacts[:5]:
        print(f"  • {c['name']} ({c['type']}) | {c['website'] or 'pas de site'}")
    _save_csv(contacts, "entreprises_tech.csv")


# ─── 8. Scrape multi-pages + export CSV ──────────────────────────────────────

def demo_paginate_and_export():
    _section("8. Scrape multi-pages — tous les cafés (3 pages × 20 = 60 max)")
    places = paginate_maps_search(
        query="café",
        location=LOCATION,
        language=LANGUAGE,
        country=COUNTRY,
        pages=3,
    )
    contacts = extract_contacts(places)
    print(f"  {len(contacts)} cafés collectés au total")
    _save_csv(contacts, "cafes.csv")


# ─── Ajouter une ville non listée ────────────────────────────────────────────

def demo_custom_city():
    _section("Bonus — ajouter une ville non présente dans CITY_COORDS")
    # Exemple : Toamasina, Madagascar
    CITY_COORDS["toamasina"] = (-18.1492, 49.4023)
    CITY_COORDS["toamasina, madagascar"] = (-18.1492, 49.4023)
    places = search_places_maps(
        query="restaurant",
        location="Toamasina, Madagascar",
        language=LANGUAGE,
        country=COUNTRY,
    )
    print(f"  {len(places)} restaurants trouvés à Toamasina")


# ─── LM Studio email generation ───────────────────────────────────────────────
# Add this import at the top of your main.py:
# from lib.lmstudio import generate_emails_for_leads, print_email

def demo_generate_emails(model_name: str = "google/gemma-4-e4b"):
    """
    Full pipeline:
      1. Fetch leads without a website (via SerpApi)
      2. Generate a personalized cold email for each (via LM Studio)
      3. Print results
    """
    from lib.lmstudio import generate_emails_for_leads, print_email

    _section("9. Pipeline complet — Leads → Emails personnalisés")

    # Step 1: collect leads without website for multiple business types
    all_leads = []
    for category_query in ["restaurant", "hotel", "cabinet médical", "boutique"]:
        leads = find_no_website_leads(
            query=category_query,
            location=LOCATION,
            language=LANGUAGE,
            country=COUNTRY,
            pages=1,   # 1 page = 20 results scanned, 1 API credit
        )
        print(f"  [{category_query}] → {len(leads)} leads sans site")
        all_leads.extend(leads)

    print(f"\n  Total : {len(all_leads)} leads. Génération des emails...\n")

    # Step 2: generate emails (capped at 5 to avoid long wait)
    emails = generate_emails_for_leads(
        leads=all_leads,
        model_name=model_name,
        max_leads=50,
    )

    # Step 3: print each email
    for email in emails:
        print_email(email)

    # Optional: save to CSV
    if emails:
        _save_csv(emails, "emails_generes.csv")


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not os.environ.get("SERPAPI_KEY"):
        print("\n[!] SERPAPI_KEY manquant. Lance d'abord :")
        print("    export SERPAPI_KEY=ta_cle_ici\n")
        exit(1)

    # demo_maps_search()
    # demo_place_details()
    # demo_local_search()
    # demo_job_search()
    # demo_no_website_leads()
    # demo_low_rating_leads()
    # demo_paginate_and_export()
    # demo_custom_city()
    demo_generate_emails()
    print("\n[✓] Terminé.\n")



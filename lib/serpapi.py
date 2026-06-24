"""
lib/serpapi.py
--------------
Multi-region SerpApi wrapper — Madagascar · France · High-value countries.

Extracts: name, address, phone, email, website, WhatsApp hint, rating, type.

Engine rules (SerpApi):
  - google_maps  : requires `ll` GPS coords, NOT location string
  - google_local : accepts plain location string
  - google       : accepts plain location string
"""

import os
import re
import requests
from typing import Optional

BASE_URL = "https://serpapi.com/search"

# ─── Regional target config ───────────────────────────────────────────────────
# 50 leads Madagascar · 50 France · 50 high-value countries
# Each entry: (display_name, lat, lon, country_code, language, region_label)

REGION_TARGETS = [
    # ── Madagascar (50 leads) — spread across major cities ──────────────────
    ("Antananarivo",           -18.9100,  47.5361, "mg", "fr", "madagascar"),
    ("Toamasina",              -18.1492,  49.4023, "mg", "fr", "madagascar"),
    ("Antsirabe",              -19.8659,  47.0310, "mg", "fr", "madagascar"),
    ("Fianarantsoa",           -21.4527,  47.0868, "mg", "fr", "madagascar"),
    ("Mahajanga",              -15.7167,  46.3167, "mg", "fr", "madagascar"),

    # ── France (50 leads) — mix of major + mid-size cities ──────────────────
    ("Paris",                   48.8566,   2.3522, "fr", "fr", "france"),
    ("Lyon",                    45.7640,   4.8357, "fr", "fr", "france"),
    ("Marseille",               43.2965,   5.3698, "fr", "fr", "france"),
    ("Bordeaux",                44.8378,  -0.5792, "fr", "fr", "france"),
    ("Nantes",                  47.2184,  -1.5536, "fr", "fr", "france"),

    # ── High-value international (50 leads) — English-speaking + EU ─────────
    ("Dubai",                   25.2048,  55.2708, "ae", "en", "international"),
    ("London",                  51.5074,  -0.1278, "gb", "en", "international"),
    ("Toronto",                 43.6532, -79.3832, "ca", "en", "international"),
    ("Singapore",                1.3521, 103.8198, "sg", "en", "international"),
    ("Nairobi",                 -1.2921,  36.8219, "ke", "en", "international"),
]

# Business categories to prospect per region
PROSPECT_QUERIES = [
    "restaurant",
    "hotel",
    "cabinet médical",
    "boutique",
    "agence immobilière",
]

# GPS city lookup (for direct use)
CITY_COORDS: dict[str, tuple[float, float]] = {
    r[0].lower(): (r[1], r[2]) for r in REGION_TARGETS
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ll(lat: float, lon: float, zoom: int = 14) -> str:
    return f"@{lat},{lon},{zoom}z"


def _get(params: dict) -> dict:
    api_key = os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        raise EnvironmentError("SERPAPI_KEY environment variable is not set.")
    params.setdefault("api_key", api_key)
    params.setdefault("output", "json")
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ─── Email / WhatsApp extraction from place data ──────────────────────────────

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"[\+\d][\d\s\-\(\)\.]{6,20}\d")
_WA_INDICATORS = ["whatsapp", "wa.me", "wa ", "+261", "+33", "+971", "+44", "+1", "+65", "+254"]


def _extract_email_from_text(text: str) -> str:
    """Try to find an email address in any raw text blob."""
    match = _EMAIL_RE.search(text or "")
    return match.group(0).lower() if match else ""


def _guess_whatsapp(phone: str, region: str) -> str:
    """
    Returns the phone number if it looks like it could be a WhatsApp number.
    Phones from MG/Dubai/Kenya are almost always on WhatsApp.
    France/UK/CA/SG: majority are on WhatsApp too.
    We flag ALL non-empty phones as potential WA — the sender script will try.
    """
    return phone.strip() if phone else ""


def _normalize_phone(raw: str) -> str:
    """Strip decorative chars, keep + and digits."""
    return re.sub(r"[^\d\+]", "", raw or "")


# ─── Core search functions ────────────────────────────────────────────────────

def search_places_maps(
    query: str,
    lat: float,
    lon: float,
    zoom: int = 14,
    language: str = "fr",
    country: str = "mg",
    start: int = 0,
) -> list[dict]:
    params = {
        "engine": "google_maps",
        "q": query,
        "type": "search",
        "ll": _ll(lat, lon, zoom),
        "hl": language,
        "gl": country,
        "start": start,
    }
    data = _get(params)
    return data.get("local_results", [])


def get_place_details(place_id: str, language: str = "fr") -> dict:
    params = {
        "engine": "google_maps",
        "place_id": place_id,
        "hl": language,
    }
    data = _get(params)
    return data.get("place_results", {})


def search_places_local(
    query: str,
    location: str = "",
    language: str = "fr",
    country: str = "mg",
    start: int = 0,
) -> list[dict]:
    params: dict = {
        "engine": "google_local",
        "q": query,
        "hl": language,
        "gl": country,
        "start": start,
    }
    if location:
        params["location"] = location
    data = _get(params)
    return data.get("ads_results", []) + data.get("local_results", [])


def search_jobs(
    role: str,
    location: str = "",
    site: str = "",
    language: str = "en",
    country: str = "us",
    num: int = 10,
    start: int = 0,
) -> list[dict]:
    query = role
    if location:
        query += f" {location}"
    if site:
        query += f" site:{site}"
    params = {
        "engine": "google",
        "q": query,
        "hl": language,
        "gl": country,
        "num": num,
        "start": start,
    }
    data = _get(params)
    return data.get("organic_results", [])


def find_no_website_leads(
    query: str,
    lat: float,
    lon: float,
    zoom: int = 14,
    language: str = "fr",
    country: str = "mg",
    pages: int = 1,
) -> list[dict]:
    leads = []
    for page in range(pages):
        results = search_places_maps(
            query=query, lat=lat, lon=lon, zoom=zoom,
            language=language, country=country, start=page * 20,
        )
        if not results:
            break
        leads.extend(p for p in results if not p.get("website"))
    return leads


def find_low_rated_leads(
    query: str,
    lat: float,
    lon: float,
    zoom: int = 14,
    max_rating: float = 3.5,
    language: str = "fr",
    country: str = "mg",
    pages: int = 1,
) -> list[dict]:
    leads = []
    for page in range(pages):
        results = search_places_maps(
            query=query, lat=lat, lon=lon, zoom=zoom,
            language=language, country=country, start=page * 20,
        )
        if not results:
            break
        leads.extend(
            p for p in results
            if p.get("rating") is not None and float(p["rating"]) <= max_rating
        )
    return leads


def find_tech_companies(
    lat: float,
    lon: float,
    zoom: int = 13,
    language: str = "fr",
    country: str = "mg",
) -> list[dict]:
    leads = []
    for query in ["software company", "web agency", "IT company", "digital agency"]:
        results = search_places_maps(
            query=query, lat=lat, lon=lon, zoom=zoom,
            language=language, country=country,
        )
        for p in results:
            p["_search_query"] = query
            leads.append(p)
    return leads


def paginate_maps_search(
    query: str,
    lat: float,
    lon: float,
    zoom: int = 14,
    pages: int = 3,
    language: str = "fr",
    country: str = "mg",
) -> list[dict]:
    all_results = []
    for page in range(pages):
        batch = search_places_maps(
            query=query, lat=lat, lon=lon, zoom=zoom,
            language=language, country=country, start=page * 20,
        )
        if not batch:
            break
        all_results.extend(batch)
    return all_results


# ─── Contact extraction — enriched with email + WhatsApp ─────────────────────

def extract_contacts(
    places: list[dict],
    region_label: str = "",
    city_name: str = "",
    language: str = "fr",
) -> list[dict]:
    """
    Flatten place dicts into contact cards.
    Fields: name, address, city, region, phone, whatsapp, email,
            website, rating, reviews, type, place_id, language
    """
    contacts = []
    for p in places:
        raw_phone = p.get("phone", "") or ""
        phone = _normalize_phone(raw_phone)

        # Try to find email in any text field (description, extensions, etc.)
        text_blob = " ".join([
            str(p.get("description", "")),
            str(p.get("extensions", "")),
            str(p.get("details", "")),
        ])
        email = _extract_email_from_text(text_blob)

        # WhatsApp: normalized phone (all phones are potential WA targets)
        whatsapp = _guess_whatsapp(phone, region_label)

        contacts.append({
            "name":      p.get("title", ""),
            "address":   p.get("address", ""),
            "city":      city_name,
            "region":    region_label,
            "language":  language,
            "phone":     phone,
            "whatsapp":  whatsapp,
            "email":     email,
            "website":   p.get("website", ""),
            "rating":    p.get("rating", ""),
            "reviews":   p.get("reviews", ""),
            "type":      p.get("type", ""),
            "place_id":  p.get("place_id", ""),
        })
    return contacts
"""
lmstudio_mail.py
----------------
Generates personalized cold emails using a local LM Studio model.
The email content adapts based on the lead's business type:
  - Restaurants / cafés / hotels  → propose a website (menu, booking, reviews)
  - Medical / legal / accounting  → propose a website + ERP (appointments, billing)
  - Retail / shops                → propose an e-commerce website
  - Tech / agencies               → propose a portfolio / SaaS landing page
  - Generic / unknown             → generic website pitch
"""

import re

_lmstudio = None


def _get_lmstudio():
    """Lazily import the external `lmstudio` package and cache it.

    This avoids import-time side-effects and makes errors clearer when the
    runtime package is missing or fails to initialize.
    """
    global _lmstudio
    if _lmstudio is not None:
        return _lmstudio
    try:
        import lmstudio as _m
    except Exception as exc:
        raise ImportError(
            "The external package 'lmstudio' could not be imported. "
            "Install it or ensure it's available in your environment."
        ) from exc
    _lmstudio = _m
    return _lmstudio


# ─── Response cleaner ─────────────────────────────────────────────────────────

def _clean_response(text: str) -> str:
    """Strip known thinking/reasoning blocks from model output."""
    patterns = [
        r"<\|channel>thought.*?<channel\|>",
        r"<think>.*?</think>",
        r"<thinking>.*?</thinking>",
        r"<\|thinking\|>.*?<\|/thinking\|>",
    ]
    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()


# ─── Business type classifier ─────────────────────────────────────────────────

# Maps keywords (lowercase) found in the place "type" or "name" to a category
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "restaurant":  ["restaurant", "café", "cafe", "bar", "brasserie", "pizzeria",
                    "snack", "traiteur", "food", "grill", "buffet"],
    "hotel":       ["hotel", "hôtel", "lodge", "auberge", "guesthouse", "motel",
                    "resort", "inn"],
    "medical":     ["clinic", "clinique", "doctor", "médecin", "pharmacy",
                    "pharmacie", "dentist", "dentiste", "hospital", "hôpital",
                    "cabinet médical", "infirmier"],
    "legal":       ["avocat", "lawyer", "notaire", "notary", "cabinet juridique",
                    "huissier", "attorney"],
    "accounting":  ["comptable", "accountant", "audit", "fiscal", "fiduciaire",
                    "expert-comptable"],
    "retail":      ["shop", "boutique", "store", "magasin", "commerce",
                    "supermarché", "épicerie", "librairie"],
    "education":   ["école", "school", "université", "formation", "académie",
                    "tutoring", "cours"],
}


def classify_lead(lead: dict) -> str:
    """
    Determine the business category from a lead dict.
    Uses the 'type' and 'name' fields from SerpApi Maps results.
    Returns a category key or 'generic'.
    """
    text = " ".join([
        str(lead.get("type", "")),
        str(lead.get("name", "")),
        str(lead.get("title", "")),
    ]).lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "generic"


# ─── Prompt builder ───────────────────────────────────────────────────────────

def _build_system_prompt(category: str, lead: dict) -> str:
    """Build the system prompt tailored to the business category."""
    business_name = lead.get("title") or lead.get("name", "cette entreprise")
    address = lead.get("address", "")
    rating = lead.get("rating", "")
    rating_note = f" (note actuelle {rating}/5 sur Google)" if rating else ""

    identity = (
        "Ny Avo Kevin — Développeur Web & Solutions Digitales\n"
        "📞 +261 34 17 539 53\n"
        "🌐 nyavokevin.space"
    )

    base = (
        f"Tu es Ny Avo Kevin, développeur web freelance basé à Antananarivo, Madagascar. "
        f"Tu crées des sites web professionnels, des applications web sur mesure et des logiciels ERP "
        f"de gestion d'entreprise pour les PME malgaches. "
        f"Tu écris un email de prospection en FRANÇAIS uniquement, professionnel, percutant et personnalisé. "
        f"L'entreprise ciblée s'appelle '{business_name}'"
        + (f", située à {address}" if address else "")
        + f"{rating_note}. "
        f"Elle n'a AUCUN site web pour le moment. "
        f"\n\n{identity}\n\n"
        f"RÈGLES STRICTES — respecte absolument toutes ces règles :\n"
        f"  - Écris UNIQUEMENT le corps de l'email. Rien d'autre.\n"
        f"  - INTERDIT : raisonnement, plan, analyse, balises <think> <thinking> <|channel> ou similaires.\n"
        f"  - INTERDIT : ligne d'objet, crochets [placeholder], texte en anglais.\n"
        f"  - Commence directement par la formule de salutation (ex: 'Bonjour,').\n"
        f"  - Termine TOUJOURS par exactement cette signature, sur 3 lignes séparées :\n"
        f"    Ny Avo Kevin\n"
        f"    +261 34 17 539 53\n"
        f"    nyavokevin.space\n"
        f"  - Maximum 160 mots, style professionnel et engageant.\n"
        f"  - Mentionne concrètement ce que tu peux livrer (site web, ERP, application sur mesure).\n"
        f"  - Propose un appel ou une réunion courte comme call-to-action.\n"
    )

    pitches = {
        "restaurant": (
            "Propose un site web restaurant moderne avec : menu en ligne, système de réservation de tables, "
            "galerie photos, horaires, et carte Google Maps. Mentionne aussi la possibilité d'une application "
            "de gestion des commandes et réservations sur mesure pour simplifier leur quotidien."
        ),
        "hotel": (
            "Propose un site web hôtel avec : présentation des chambres, galerie photos, formulaire de réservation "
            "en ligne, tarifs et disponibilités. Mentionne un logiciel de gestion hôtelière (ERP) sur mesure : "
            "gestion des réservations, check-in/check-out, facturation client, et tableau de bord."
        ),
        "medical": (
            "Propose un site web professionnel ET un logiciel de gestion de cabinet (ERP médical) : "
            "prise de rendez-vous en ligne, dossiers patients numériques, gestion des ordonnances, "
            "facturation et rapports. Souligne le gain de temps et la confidentialité des données."
        ),
        "legal": (
            "Propose un site web professionnel ET un logiciel de gestion de cabinet juridique : "
            "suivi des dossiers clients, gestion des échéances, portail client sécurisé, facturation "
            "et archivage de documents. Souligne l'image de marque et la confiance client."
        ),
        "accounting": (
            "Propose un site web professionnel ET un ERP comptable : portail client, dépôt de documents "
            "en ligne, suivi des déclarations fiscales, facturation automatisée et alertes d'échéances. "
            "Mets en avant la modernisation du cabinet et la fidélisation des clients."
        ),
        "retail": (
            "Propose un site e-commerce complet : catalogue produits, panier, paiement en ligne sécurisé, "
            "gestion des stocks et suivi des livraisons. Mentionne aussi un logiciel de caisse et gestion "
            "de stock sur mesure pour piloter leur activité depuis un seul tableau de bord."
        ),
        "education": (
            "Propose un site web institutionnel avec : présentation des formations, inscriptions en ligne, "
            "espace étudiant et paiement des frais de scolarité. Mentionne aussi une plateforme "
            "e-learning sur mesure pour digitaliser l'enseignement et attirer plus d'élèves."
        ),
        "generic": (
            "Propose un site web professionnel vitrine qui valorise leurs services, améliore leur "
            "référencement Google et inclut un formulaire de contact. Mentionne aussi la possibilité "
            "d'un logiciel de gestion sur mesure (ERP) adapté à leur secteur d'activité."
        ),
    }

    return base + " " + pitches.get(category, pitches["generic"])


def _build_user_message(category: str, lead: dict) -> str:
    business_name = lead.get("title") or lead.get("name", "cette entreprise")
    return (
        f"Rédige un email de prospection professionnelle à '{business_name}'. "
        f"Ils n'ont aucun site web. "
        f"L'email doit être percutant, professionnel, entièrement en français, "
        f"et donner envie de répondre. Mets en avant la valeur concrète apportée "
        f"(site web, ERP, application sur mesure). Termine avec ta signature complète."
    )


# ─── Subject line generator ───────────────────────────────────────────────────

def _build_subject_prompt(category: str, lead: dict) -> str:
    business_name = lead.get("title") or lead.get("name", "this business")
    subjects = {
        "restaurant":  f"Développons votre présence digitale — {business_name}",
        "hotel":       f"Site web & logiciel de gestion hôtelière pour {business_name}",
        "medical":     f"Modernisez votre cabinet avec un site web + ERP médical — {business_name}",
        "legal":       f"Solution digitale sur mesure pour votre cabinet — {business_name}",
        "accounting":  f"Site web & ERP comptable pour moderniser votre cabinet — {business_name}",
        "retail":      f"Développez vos ventes en ligne — Site e-commerce pour {business_name}",
        "education":   f"Digitalisez votre établissement — Site & plateforme e-learning",
        "generic":     f"Proposition de solution digitale sur mesure — {business_name}",
    }
    return subjects.get(category, subjects["generic"])


# ─── Main public functions ────────────────────────────────────────────────────

def generate_email_for_lead(lead: dict, model_name: str) -> dict:
    """
    Generate a full cold email (subject + body) for a single lead dict.

    Args:
        lead       : dict from serpapi_lib extract_contacts() or raw Maps result
        model_name : LM Studio model identifier, e.g. "llama-3-8b"

    Returns:
        dict with keys: name, category, subject, body
    """
    category = classify_lead(lead)
    lm = _get_lmstudio()
    model = lm.llm(model_name)

    # Build the chat
    system_prompt = _build_system_prompt(category, lead)
    chat = lm.Chat(system_prompt)
    chat.add_user_message(_build_user_message(category, lead))

    # Generate email body
    response = model.respond(chat)
    body = _clean_response(str(response))

    # Subject line (static, no LLM call needed — saves credits)
    subject = _build_subject_prompt(category, lead)

    return {
        "name":     lead.get("title") or lead.get("name", ""),
        "category": category,
        "subject":  subject,
        "body":     body,
    }


def generate_emails_for_leads(
    leads: list[dict],
    model_name: str,
    max_leads: int = 10,
) -> list[dict]:
    """
    Batch-generate emails for a list of leads.

    Args:
        leads      : list of lead dicts (from serpapi_lib)
        model_name : LM Studio model identifier
        max_leads  : safety cap to avoid burning too many LLM calls

    Returns:
        List of email dicts (name, category, subject, body)
    """
    emails = []
    for lead in leads[:max_leads]:
        print(f"  → Generating email for: {lead.get('title') or lead.get('name')}")
        try:
            email = generate_email_for_lead(lead, model_name)
            emails.append(email)
        except Exception as e:
            print(f"    [!] Failed: {e}")
    return emails


def print_email(email: dict) -> None:
    """Pretty-print a single generated email."""
    print(f"\n{'─'*60}")
    print(f"  To      : {email['name']}  [{email['category']}]")
    print(f"  Subject : {email['subject']}")
    print(f"{'─'*60}")
    print(email["body"])
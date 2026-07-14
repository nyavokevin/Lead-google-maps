"""
lmstudio.py
----------------
Generates personalized cold emails using a local LM Studio model.
The email content adapts based on:
  1. The lead's WEBSITE STATUS (checked by website_checker.py before this runs):
     - "missing" → propose creating a website
     - "broken"  → mention (with tact) that their current site is down, propose fixing/rebuilding it
     - "ok"      → don't propose a new site, propose adding booking/ERP/delivery features instead
  2. The lead's BUSINESS TYPE:
     - Restaurants / cafés / hotels  → booking, menu, delivery
     - Medical / legal / accounting  → website + ERP (appointments, billing)
     - Retail / shops                → e-commerce website
     - Tech / agencies               → portfolio / SaaS landing page
     - Generic / unknown             → generic website pitch
  3. The LANGUAGE (lang="fr" | "en") — all prompts are generated in the chosen language.
"""

import re

from .llm_http import LMStudioClient

_client = LMStudioClient()

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
    Category is derived from the lead's business type.
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


# ─── Website-status classifier ────────────────────────────────────────────────

def classify_website_mode(lead: dict) -> str:
    """
    Determine what action to pitch based on website_checker.py's output.
    Returns one of: "creation_site" | "reparation_site" | "amelioration_erp".

    If website_checker.py hasn't run (website_status is None/missing key),
    falls back to treating the lead as if it had no website, which matches
    the previous (pre-check) behaviour.
    """
    status = lead.get("website_status")
    if status == "broken":
        return "reparation_site"
    if status == "ok":
        return "amelioration_erp"
    # status is "missing", None (check skipped), or key absent
    return "creation_site"


# ─── Feature descriptions per category (what could be built/added) ───────────

FEATURES_FR: dict[str, str] = {
    "restaurant": (
        "un menu en ligne, un système de réservation de tables, une galerie photos, "
        "les horaires, la carte Google Maps, et une gestion des commandes à emporter/livraison"
    ),
    "hotel": (
        "la présentation des chambres, une galerie photos, un formulaire de réservation en ligne, "
        "les tarifs et disponibilités, et un logiciel de gestion hôtelière (check-in/check-out, "
        "facturation, tableau de bord)"
    ),
    "medical": (
        "la prise de rendez-vous en ligne, des dossiers patients numériques, la gestion des "
        "ordonnances, la facturation et des rapports (ERP médical)"
    ),
    "legal": (
        "le suivi des dossiers clients, la gestion des échéances, un portail client sécurisé, "
        "la facturation et l'archivage de documents"
    ),
    "accounting": (
        "un portail client, le dépôt de documents en ligne, le suivi des déclarations fiscales, "
        "la facturation automatisée et des alertes d'échéances"
    ),
    "retail": (
        "un catalogue produits, un panier, le paiement en ligne sécurisé, la gestion des stocks, "
        "le suivi des livraisons, et un logiciel de caisse/gestion de stock"
    ),
    "education": (
        "la présentation des formations, les inscriptions en ligne, un espace étudiant, le paiement "
        "des frais de scolarité, et une plateforme e-learning"
    ),
    "generic": (
        "une vitrine qui valorise leurs services, un meilleur référencement Google, un formulaire "
        "de contact, et un logiciel de gestion (ERP) adapté à leur secteur"
    ),
}

FEATURES_EN: dict[str, str] = {
    "restaurant": (
        "an online menu, a table reservation system, a photo gallery, opening hours, "
        "Google Maps integration, and takeaway/delivery order management"
    ),
    "hotel": (
        "room showcases, a photo gallery, an online booking form, rates and availability, "
        "and hotel management software (check-in/check-out, billing, dashboard)"
    ),
    "medical": (
        "online appointment booking, digital patient records, prescription management, "
        "billing and reports (medical ERP)"
    ),
    "legal": (
        "client case tracking, deadline management, a secure client portal, "
        "billing and document archiving"
    ),
    "accounting": (
        "a client portal, online document submission, tax filing tracking, "
        "automated billing and deadline alerts"
    ),
    "retail": (
        "a product catalogue, a cart, secure online payment, stock management, "
        "delivery tracking, and a POS/stock management system"
    ),
    "education": (
        "course presentations, online enrolment, a student space, tuition fee payment, "
        "and an e-learning platform"
    ),
    "generic": (
        "a storefront that showcases their services, better Google SEO, a contact form, "
        "and management software (ERP) suited to their sector"
    ),
}


def _features_for(category: str, lang: str) -> str:
    table = FEATURES_EN if lang == "en" else FEATURES_FR
    return table.get(category, table["generic"])


def _website_situation_and_pitch(mode: str, category: str, lead: dict, lang: str) -> tuple[str, str]:
    """
    Returns (situation_text, pitch_instruction) for the system prompt, based on
    the website mode ("creation_site" | "reparation_site" | "amelioration_erp")
    and the requested language.
    """
    features = _features_for(category, lang)
    website = lead.get("website", "")

    if mode == "reparation_site":
        raw_note = lead.get("website_note") or (
            "j'ai vu que votre site web ne marche pas actuellement"
            if lang == "fr" else
            "I noticed your website doesn't seem to be working at the moment"
        )
        if lang == "en":
            situation = (
                f"They have a website ({website}) but it is currently INACCESSIBLE / DOWN "
                f"(a technical issue was observed). Here is the raw observation to rephrase "
                f"tactfully and professionally, without copying it word for word: \"{raw_note}\"."
            )
            pitch = (
                f"First mention, tactfully and without being alarmist, that you noticed their current "
                f"site seems inaccessible right now — point out this can cost them customers. Then "
                f"propose to fix it or rebuild it, including: {features}."
            )
        else:
            situation = (
                f"Elle a un site web ({website}) mais il est actuellement INACCESSIBLE / EN PANNE "
                f"(problème technique constaté). Voici l'observation brute à reformuler avec tact et "
                f"professionnalisme, sans la copier mot pour mot : \"{raw_note}\"."
            )
            pitch = (
                f"Mentionne d'abord, avec tact et sans être alarmiste, que tu as remarqué que leur site "
                f"actuel semble inaccessible en ce moment — précise que cela peut faire perdre des clients. "
                f"Propose ensuite de le réparer ou d'en refaire un, incluant : {features}."
            )
    elif mode == "amelioration_erp":
        if lang == "en":
            situation = (
                f"They already have a working website ({website}). Do NOT propose building a new site."
            )
            pitch = (
                f"Since their site already works, do not propose a new one. Instead propose adding or "
                f"improving, on their existing site or via a complementary app: {features}."
            )
        else:
            situation = (
                f"Elle a déjà un site web fonctionnel ({website}). NE propose PAS de créer un nouveau site."
            )
            pitch = (
                f"Comme leur site fonctionne déjà, ne propose surtout pas d'en créer un nouveau. Propose "
                f"plutôt d'ajouter ou d'améliorer, sur leur site existant ou via une application "
                f"complémentaire : {features}."
            )
    else:  # creation_site
        if lang == "en":
            situation = "They have NO website at the moment."
            pitch = f"Propose a website with: {features}."
        else:
            situation = "Elle n'a AUCUN site web pour le moment."
            pitch = f"Propose un site web avec : {features}."

    return situation, pitch


# ─── Prompt builder ───────────────────────────────────────────────────────────

IDENTITY = (
    "Ny Avo Kevin — Développeur Web & Solutions Digitales\n"
    "📞 +261 34 17 539 53\n"
    "🌐 nyavokevin.space"
)


def _build_system_prompt(category: str, mode: str, lead: dict, lang: str = "fr") -> str:
    """Build the system prompt tailored to the business category, website status and language."""
    business_name = lead.get("title") or lead.get("name", "cette entreprise")
    address = lead.get("address", "")
    rating = lead.get("rating", "")
    rating_note = f" (note actuelle {rating}/5 sur Google)" if (rating and lang == "fr") else (
        f" (current rating {rating}/5 on Google)" if rating else ""
    )

    situation, pitch = _website_situation_and_pitch(mode, category, lead, lang)

    if lang == "en":
        base = (
            f"You are Ny Avo Kevin, a freelance web developer based in Antananarivo, Madagascar. "
            f"You build professional websites, custom web applications and ERP management software "
            f"for SMEs. Write a cold outreach email in ENGLISH ONLY, professional, punchy and personalized. "
            f"The target business is called '{business_name}'"
            + (f", located at {address}" if address else "")
            + f"{rating_note}. "
            f"{situation} "
            f"\n\n{IDENTITY}\n\n"
            f"STRICT RULES — follow absolutely all of them:\n"
            f"  - Write ONLY the email body. Nothing else.\n"
            f"  - FORBIDDEN: reasoning, plan, analysis, <think> <thinking> <|channel> tags or similar.\n"
            f"  - FORBIDDEN: subject line, [placeholder] brackets, French text.\n"
            f"  - Start directly with a greeting (e.g. 'Hello,').\n"
            f"  - ALWAYS end with exactly this 3-line signature:\n"
            f"    Ny Avo Kevin\n"
            f"    +261 34 17 539 53\n"
            f"    nyavokevin.space\n"
            f"  - Maximum 160 words, professional and engaging.\n"
            f"  - Mention concretely what you can deliver.\n"
            f"  - Propose a short call or meeting as a call-to-action.\n"
        )
    else:
        base = (
            f"Tu es Ny Avo Kevin, développeur web freelance basé à Antananarivo, Madagascar. "
            f"Tu crées des sites web professionnels, des applications web sur mesure et des logiciels ERP "
            f"de gestion d'entreprise pour les PME malgaches. "
            f"Tu écris un email de prospection en FRANÇAIS uniquement, professionnel, percutant et personnalisé. "
            f"L'entreprise ciblée s'appelle '{business_name}'"
            + (f", située à {address}" if address else "")
            + f"{rating_note}. "
            f"{situation} "
            f"\n\n{IDENTITY}\n\n"
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
            f"  - Mentionne concrètement ce que tu peux livrer.\n"
            f"  - Propose un appel ou une réunion courte comme call-to-action.\n"
        )

    return base + " " + pitch


def _build_user_message(category: str, mode: str, lead: dict, lang: str = "fr") -> str:
    business_name = lead.get("title") or lead.get("name", "cette entreprise")

    if lang == "en":
        situation_hint = {
            "creation_site": "They have no website.",
            "reparation_site": "Their current website is not working (inaccessible).",
            "amelioration_erp": "They already have a working website — don't propose building another one.",
        }[mode]
        return (
            f"Write a professional cold outreach email to '{business_name}'. "
            f"{situation_hint} "
            f"The email must be punchy, professional, entirely in English, and make them want to reply. "
            f"Highlight the concrete value delivered (website, ERP, custom app). "
            f"End with your full signature."
        )
    else:
        situation_hint = {
            "creation_site": "Ils n'ont aucun site web.",
            "reparation_site": "Leur site web actuel ne fonctionne pas (inaccessible).",
            "amelioration_erp": "Ils ont déjà un site web fonctionnel — ne propose pas d'en créer un autre.",
        }[mode]
        return (
            f"Rédige un email de prospection professionnelle à '{business_name}'. "
            f"{situation_hint} "
            f"L'email doit être percutant, professionnel, entièrement en français, "
            f"et donner envie de répondre. Mets en avant la valeur concrète apportée "
            f"(site web, ERP, application sur mesure). Termine avec ta signature complète."
        )


# ─── Subject line generator ───────────────────────────────────────────────────

def _build_subject_prompt(category: str, mode: str, lead: dict, lang: str = "fr") -> str:
    business_name = lead.get("title") or lead.get("name", "this business")

    if mode == "reparation_site":
        return (
            f"Votre site web semble inaccessible — proposition de solution pour {business_name}"
            if lang == "fr" else
            f"Your website seems inaccessible — proposed solution for {business_name}"
        )

    if lang == "en":
        subjects = {
            "restaurant":  f"Let's grow your digital presence — {business_name}",
            "hotel":       f"Website & hotel management software for {business_name}",
            "medical":     f"Modernize your practice with a website + medical ERP — {business_name}",
            "legal":       f"Tailored digital solution for your firm — {business_name}",
            "accounting":  f"Website & accounting ERP to modernize your firm — {business_name}",
            "retail":      f"Boost your online sales — E-commerce site for {business_name}",
            "education":   f"Digitalize your institution — Website & e-learning platform",
            "generic":     f"Tailored digital solution — {business_name}",
        }
        return subjects.get(category, subjects["generic"])

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

def generate_email_for_lead(lead: dict, model_name: str, lang: str = "fr") -> dict:
    """
    Generate a full cold email (subject + body) for a single lead dict.

    Args:
        lead       : dict from a leads dataset entry (title/name, type, address, whatsapp,
                     email, website, and — if website_checker.py ran — website_status/website_note)
        model_name : LM Studio model identifier, e.g. "llama-3-8b"
        lang       : "fr" (default) or "en" — language of the generated email

    Returns:
        dict with keys: name, category, website_mode, subject, body, whatsapp, email
    """
    category = classify_lead(lead)
    mode = classify_website_mode(lead)

    chat = _client.Chat(_build_system_prompt(category, mode, lead, lang))
    chat.add_user_message(_build_user_message(category, mode, lead, lang))

    body = _clean_response(_client.respond(chat, model=model_name))
    subject = _build_subject_prompt(category, mode, lead, lang)

    # Pull contact info straight from the lead row
    whatsapp = lead.get("whatsapp", lead.get("phone", ""))
    email = lead.get("email", "")

    return {
        "name":         lead.get("title") or lead.get("name", ""),
        "category":     category,
        "website_mode": mode,
        "subject":      subject,
        "body":         body,
        "whatsapp":     whatsapp,
        "email":        email,
    }


def generate_emails_for_leads(
    leads: list[dict],
    model_name: str,
    max_leads: int = 10,
    lang: str = "fr",
) -> list[dict]:
    """
    Batch-generate emails for a list of leads.

    Args:
        leads      : list of lead dicts (from a leads CSV/JSON, optionally enriched by
                     website_checker.py with website_status/website_note)
        model_name : LM Studio model identifier
        max_leads  : safety cap to avoid burning too many LLM calls
        lang       : "fr" (default) or "en" — language of the generated emails

    Returns:
        List of email dicts (name, category, website_mode, subject, body, whatsapp, email)
    """
    emails = []
    for lead in leads[:max_leads]:
        print(f"  → Generating email for: {lead.get('title') or lead.get('name')}")
        try:
            email = generate_email_for_lead(lead, model_name, lang=lang)
            emails.append(email)
        except Exception as e:
            print(f"    [!] Failed: {e}")
    return emails


def print_email(email: dict) -> None:
    """Pretty-print a single generated email."""
    print(f"\n{'─'*60}")
    print(f"  To      : {email['name']}  [{email['category']} / {email.get('website_mode', '?')}]")
    print(f"  Subject : {email['subject']}")
    print(f"{'─'*60}")
    print(email["body"])

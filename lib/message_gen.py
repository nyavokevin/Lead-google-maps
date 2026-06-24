"""
lib/message_gen.py
------------------
Generates personalized cold outreach messages via LM Studio (local model).
Model name is read from the LM_MODEL env variable (set in .env).

  - If lead has EMAIL  → full professional email (subject + body)
  - If lead has PHONE  → short WhatsApp message (≤ 320 chars)
  - Language adapts    : French for mg/france, English for international
  - Pitch adapts       : ERP-first for medical/legal/accounting,
                         web for resto/hotel, mobile/web app for tech
"""

import os
import re

# ─── LM Studio lazy loader (exact pattern from your lmstudio.py) ──────────────

_lmstudio = None


def _get_lmstudio():
    global _lmstudio
    if _lmstudio is not None:
        return _lmstudio
    try:
        import lmstudio as _m
    except Exception as exc:
        raise ImportError(
            "The 'lmstudio' package could not be imported. "
            "Install it with: pip install lmstudio\n"
            "And make sure LM Studio is running locally."
        ) from exc
    _lmstudio = _m
    return _lmstudio


def _get_model_name() -> str:
    name = os.environ.get("LM_MODEL", "").strip()
    if not name:
        raise EnvironmentError(
            "LM_MODEL is not set. Add it to your .env:\n"
            "  LM_MODEL=google/gemma-4-e4b\n"
            "  (use the exact identifier shown in LM Studio)"
        )
    return name


# ─── Response cleaner (strips thinking blocks) ────────────────────────────────

def _clean(text: str) -> str:
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


# ─── Business classifier ──────────────────────────────────────────────────────

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "restaurant":  ["restaurant", "café", "cafe", "bar", "brasserie", "pizzeria",
                    "snack", "traiteur", "food", "grill", "buffet", "cuisine"],
    "hotel":       ["hotel", "hôtel", "lodge", "auberge", "guesthouse", "motel",
                    "resort", "inn", "villa", "guest house"],
    "medical":     ["clinic", "clinique", "doctor", "médecin", "pharmacy",
                    "pharmacie", "dentist", "dentiste", "hospital", "hôpital",
                    "cabinet médical", "infirmier", "health", "santé"],
    "legal":       ["avocat", "lawyer", "notaire", "notary", "cabinet juridique",
                    "huissier", "attorney", "barreau", "law"],
    "accounting":  ["comptable", "accountant", "audit", "fiscal", "fiduciaire",
                    "expert-comptable", "finance", "conseil"],
    "retail":      ["shop", "boutique", "store", "magasin", "commerce",
                    "supermarché", "épicerie", "librairie", "vente", "market"],
    "tech":        ["software", "web agency", "digital", "IT company", "agence web",
                    "informatique", "développement", "startup", "tech"],
    "education":   ["école", "school", "université", "formation", "académie",
                    "tutoring", "cours", "institute", "training"],
    "realestate":  ["immobilier", "real estate", "agence immobilière", "property",
                    "appartement", "maison", "rental", "location"],
}


def classify_lead(lead: dict) -> str:
    text = " ".join([
        str(lead.get("type", "")),
        str(lead.get("name", "")),
        str(lead.get("title", "")),
        str(lead.get("category", "")),
    ]).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "generic"


def _get_lang(lead: dict) -> str:
    return "fr" if lead.get("language", "fr") in ("fr",) else "en"


# ─── Pitch library (what you offer per business type) ─────────────────────────

PITCHES_FR = {
    "restaurant":  (
        "un site web restaurant moderne : menu en ligne, réservation de tables, galerie photos, "
        "horaires et carte Google Maps. Et une application de gestion des commandes/réservations sur mesure."
    ),
    "hotel":       (
        "un site web hôtelier avec présentation des chambres, réservation en ligne, galerie et tarifs. "
        "Et un logiciel ERP hôtelier : gestion des réservations, check-in/check-out, facturation, tableau de bord."
    ),
    "medical":     (
        "un ERP médical complet : prise de rendez-vous en ligne, dossiers patients numériques, "
        "gestion des ordonnances, facturation et rapports. Plus un site web professionnel."
    ),
    "legal":       (
        "un logiciel de gestion de cabinet juridique : suivi des dossiers, gestion des échéances, "
        "portail client sécurisé, facturation et archivage. Plus un site web professionnel."
    ),
    "accounting":  (
        "un ERP comptable : portail client, dépôt de documents en ligne, suivi fiscal, "
        "facturation automatisée et alertes d'échéances. Plus un site web professionnel."
    ),
    "retail":      (
        "un site e-commerce complet : catalogue produits, paiement en ligne, gestion des stocks "
        "et suivi des livraisons. Et un logiciel de caisse/stock sur mesure."
    ),
    "tech":        (
        "une application web ou mobile sur mesure, ou un partenariat de sous-traitance "
        "pour vos projets clients."
    ),
    "education":   (
        "un site institutionnel avec inscriptions en ligne, espace étudiant et paiement des frais. "
        "Et une plateforme e-learning sur mesure pour digitaliser l'enseignement."
    ),
    "realestate":  (
        "un site vitrine de biens immobiliers et une application de gestion : CRM, agenda visites, "
        "contrats et reporting."
    ),
    "generic":     (
        "un site web professionnel vitrine et un logiciel ERP de gestion sur mesure "
        "adapté à votre secteur d'activité."
    ),
}

PITCHES_EN = {
    "restaurant":  (
        "a modern restaurant website: online menu, table bookings, photo gallery, hours and Google Maps. "
        "Plus a custom order/reservation management app."
    ),
    "hotel":       (
        "a hotel website with room showcase, online booking, gallery and rates. "
        "Plus a property management ERP: reservations, check-in/out, billing, dashboard."
    ),
    "medical":     (
        "a full medical ERP: online appointments, digital patient records, prescriptions, billing and reports. "
        "Plus a professional website."
    ),
    "legal":       (
        "a legal practice management system: case tracking, deadlines, secure client portal, billing and archiving. "
        "Plus a professional website."
    ),
    "accounting":  (
        "an accounting ERP: client portal, document upload, tax tracking, automated billing and deadline alerts. "
        "Plus a professional website."
    ),
    "retail":      (
        "a full e-commerce site: product catalogue, online payment, inventory and delivery tracking. "
        "Plus a custom POS and stock management system."
    ),
    "tech":        (
        "a custom web or mobile application, or a subcontracting partnership for your client projects."
    ),
    "education":   (
        "an institutional website with online enrolment, student portal and fee payment. "
        "Plus a custom e-learning platform."
    ),
    "realestate":  (
        "a property listing website and a management app: CRM, visit scheduler, contracts and reports."
    ),
    "generic":     (
        "a professional website and a custom ERP management system tailored to your business."
    ),
}


# ─── System prompt builders ───────────────────────────────────────────────────

IDENTITY = (
    "Ny Avo Kevin — ERP · Web · Mobile Dev\n"
    "📞 +261 34 17 539 53\n"
    "🌐 nyavokevin.space"
)


def _build_email_system(category: str, lead: dict) -> str:
    lang       = _get_lang(lead)
    name       = lead.get("title") or lead.get("name", "cette entreprise")
    address    = lead.get("address", "")
    rating     = lead.get("rating", "")
    rating_note = f" (note {rating}/5 sur Google)" if rating else ""
    pitch      = (PITCHES_FR if lang == "fr" else PITCHES_EN).get(category, PITCHES_FR["generic"])

    if lang == "fr":
        return (
            f"Tu es Ny Avo Kevin, développeur freelance spécialisé en ERP, applications web et mobile, "
            f"basé à Antananarivo, Madagascar. Tu travailles avec des clients en Madagascar, en France "
            f"et à l'international.\n\n"
            f"{IDENTITY}\n\n"
            f"L'entreprise ciblée s'appelle '{name}'"
            + (f", située à {address}" if address else "")
            + f"{rating_note}. Elle n'a AUCUN site web ni solution digitale actuellement.\n\n"
            f"RÈGLES STRICTES — à respecter absolument :\n"
            f"  - Écris UNIQUEMENT le corps de l'email. Rien d'autre.\n"
            f"  - INTERDIT : raisonnement, plan, analyse, balises <think> <thinking> <|channel> ou similaires.\n"
            f"  - INTERDIT : ligne d'objet, crochets [placeholder], texte en anglais.\n"
            f"  - Commence directement par la formule de salutation (ex : 'Bonjour,').\n"
            f"  - Termine TOUJOURS par exactement cette signature sur 3 lignes :\n"
            f"    Ny Avo Kevin\n"
            f"    +261 34 17 539 53\n"
            f"    nyavokevin.space\n"
            f"  - Maximum 160 mots, style professionnel et engageant.\n"
            f"  - Ce que tu proposes concrètement : {pitch}\n"
            f"  - Call-to-action : propose un appel de 15 minutes cette semaine.\n"
        )
    else:
        return (
            f"You are Ny Avo Kevin, a freelance developer specializing in ERP systems, web and mobile apps, "
            f"based in Antananarivo, Madagascar. You work with clients in Madagascar, France and internationally.\n\n"
            f"{IDENTITY}\n\n"
            f"Target business: '{name}'"
            + (f", located at {address}" if address else "")
            + f"{rating_note}. They have NO website or digital solution currently.\n\n"
            f"STRICT RULES:\n"
            f"  - Write ONLY the email body. Nothing else.\n"
            f"  - FORBIDDEN: reasoning blocks, plans, <think> <thinking> <|channel> tags.\n"
            f"  - FORBIDDEN: subject line, [placeholders], French text.\n"
            f"  - Start directly with a greeting (e.g. 'Hello,').\n"
            f"  - ALWAYS end with exactly this 3-line signature:\n"
            f"    Ny Avo Kevin\n"
            f"    +261 34 17 539 53\n"
            f"    nyavokevin.space\n"
            f"  - Maximum 160 words. Professional and engaging.\n"
            f"  - What you offer: {pitch}\n"
            f"  - Call-to-action: propose a 15-minute call this week.\n"
        )


def _build_email_user(category: str, lead: dict) -> str:
    lang = _get_lang(lead)
    name = lead.get("title") or lead.get("name", "cette entreprise")
    pitch = (PITCHES_FR if lang == "fr" else PITCHES_EN).get(category, PITCHES_FR["generic"])
    if lang == "fr":
        return (
            f"Rédige un email de prospection professionnelle à '{name}'. "
            f"Ils n'ont aucun site web. Tu proposes : {pitch}. "
            f"L'email doit être percutant, professionnel, entièrement en français "
            f"et donner envie de répondre. Termine avec ta signature complète."
        )
    else:
        return (
            f"Write a professional cold outreach email to '{name}'. "
            f"They have no website. You offer: {pitch}. "
            f"The email must be impactful, professional, entirely in English "
            f"and compelling enough to get a reply. End with your full signature."
        )


def _build_whatsapp_system(category: str, lead: dict) -> str:
    lang  = _get_lang(lead)
    pitch = (PITCHES_FR if lang == "fr" else PITCHES_EN).get(category, PITCHES_FR["generic"])

    if lang == "fr":
        return (
            f"Tu es Ny Avo Kevin, développeur ERP & web freelance basé à Antananarivo.\n"
            f"Tu rédiges un message WhatsApp de prospection en FRANÇAIS.\n\n"
            f"RÈGLES STRICTES :\n"
            f"  - Maximum 320 caractères (WhatsApp court).\n"
            f"  - Professionnel mais naturel pour WhatsApp, pas de HTML.\n"
            f"  - INTERDIT : balises <think>, raisonnement, texte en anglais.\n"
            f"  - Commence directement par le message (pas de sujet, pas d'en-tête).\n"
            f"  - Inclus toujours : nyavokevin.space et +261 34 17 539 53.\n"
            f"  - Termine par une question d'appel à l'action courte.\n"
            f"  - Ce que tu proposes : {pitch}\n"
        )
    else:
        return (
            f"You are Ny Avo Kevin, freelance ERP & web developer based in Antananarivo.\n"
            f"Write a WhatsApp prospecting message in ENGLISH.\n\n"
            f"STRICT RULES:\n"
            f"  - Maximum 320 characters.\n"
            f"  - Professional but conversational for WhatsApp, no HTML.\n"
            f"  - FORBIDDEN: <think> tags, reasoning, French text.\n"
            f"  - Start the message directly (no subject, no header).\n"
            f"  - Always include: nyavokevin.space and +261 34 17 539 53.\n"
            f"  - End with a short call-to-action question.\n"
            f"  - What you offer: {pitch}\n"
        )


def _build_whatsapp_user(category: str, lead: dict) -> str:
    lang  = _get_lang(lead)
    name  = lead.get("title") or lead.get("name", "cette entreprise")
    pitch = (PITCHES_FR if lang == "fr" else PITCHES_EN).get(category, PITCHES_FR["generic"])
    if lang == "fr":
        return f"Message WhatsApp de prospection pour '{name}'. Tu proposes : {pitch}."
    else:
        return f"WhatsApp prospecting message for '{name}'. You offer: {pitch}."


# ─── Subject lines (static — no LLM call needed) ─────────────────────────────

SUBJECTS_FR = {
    "restaurant":  "Développons votre présence digitale — {name}",
    "hotel":       "Site web & logiciel de gestion hôtelière — {name}",
    "medical":     "ERP médical + site web professionnel — {name}",
    "legal":       "Solution digitale pour votre cabinet — {name}",
    "accounting":  "ERP comptable & site web — {name}",
    "retail":      "Site e-commerce sur mesure — {name}",
    "tech":        "Partenariat dev web/mobile — {name}",
    "education":   "Digitalisez votre établissement — {name}",
    "realestate":  "Application de gestion immobilière — {name}",
    "generic":     "Solution digitale sur mesure — {name}",
}
SUBJECTS_EN = {
    "restaurant":  "Custom digital solution for your business — {name}",
    "hotel":       "Hotel website & management system — {name}",
    "medical":     "Medical ERP + professional website — {name}",
    "legal":       "Legal practice management software — {name}",
    "accounting":  "Accounting ERP & website — {name}",
    "retail":      "Custom e-commerce website — {name}",
    "tech":        "Web/mobile dev partnership — {name}",
    "education":   "Digital platform for your institution — {name}",
    "realestate":  "Property management app — {name}",
    "generic":     "Custom digital solution — {name}",
}


def _subject(lead: dict, category: str) -> str:
    lang  = _get_lang(lead)
    name  = lead.get("title") or lead.get("name", "")
    table = SUBJECTS_FR if lang == "fr" else SUBJECTS_EN
    return table.get(category, table["generic"]).format(name=name)


# ─── Core LM Studio call (same pattern as your original) ─────────────────────

def _generate(system_prompt: str, user_message: str) -> str:
    model_name = _get_model_name()
    lm    = _get_lmstudio()
    model = lm.llm(model_name)
    chat  = lm.Chat(system_prompt)
    chat.add_user_message(user_message)
    response = model.respond(chat)
    return _clean(str(response))


# ─── Main public API ──────────────────────────────────────────────────────────

def generate_message_for_lead(lead: dict) -> dict:
    """
    Generate the right message for a lead based on contact availability.

    Returns dict with:
      name, category, channel ('email'|'whatsapp'|'none'),
      subject (email only), body, email, whatsapp, phone,
      city, region, language, website, rating, address, place_id
    """
    category  = classify_lead(lead)
    has_email = bool((lead.get("email") or "").strip())
    has_phone = bool((lead.get("whatsapp") or lead.get("phone") or "").strip())

    if has_email:
        channel = "email"
        body    = _generate(
            _build_email_system(category, lead),
            _build_email_user(category, lead),
        )
        subject = _subject(lead, category)
    elif has_phone:
        channel = "whatsapp"
        body    = _generate(
            _build_whatsapp_system(category, lead),
            _build_whatsapp_user(category, lead),
        )
        subject = ""
    else:
        channel = "none"
        body    = ""
        subject = ""

    return {
        "name":     lead.get("title") or lead.get("name", ""),
        "category": category,
        "channel":  channel,
        "subject":  subject,
        "body":     body,
        "email":    lead.get("email", ""),
        "whatsapp": lead.get("whatsapp", lead.get("phone", "")),
        "phone":    lead.get("phone", ""),
        "city":     lead.get("city", ""),
        "region":   lead.get("region", ""),
        "language": lead.get("language", "fr"),
        "website":  lead.get("website", ""),
        "rating":   lead.get("rating", ""),
        "address":  lead.get("address", ""),
        "place_id": lead.get("place_id", ""),
    }


def generate_messages_batch(
    leads: list[dict],
    max_leads: int = 250,
    verbose: bool = True,
) -> list[dict]:
    results = []
    for i, lead in enumerate(leads[:max_leads]):
        name = lead.get("name") or lead.get("title") or "?"
        if verbose:
            print(f"  [{i+1}/{min(len(leads), max_leads)}] → {name} ({lead.get('region', '')}) ", end="", flush=True)
        try:
            msg = generate_message_for_lead(lead)
            results.append(msg)
            if verbose:
                print(f"✓ [{msg['channel']}]")
        except Exception as e:
            if verbose:
                print(f"✗ {e}")
    return results


def print_message(msg: dict) -> None:
    """Pretty-print a generated message (email or WhatsApp)."""
    print(f"\n{'─'*60}")
    print(f"  To       : {msg['name']}  [{msg['category']}]  ({msg['channel']})")
    if msg.get("subject"):
        print(f"  Subject  : {msg['subject']}")
    if msg.get("email"):
        print(f"  Email    : {msg['email']}")
    if msg.get("whatsapp"):
        print(f"  WhatsApp : {msg['whatsapp']}")
    print(f"{'─'*60}")
    print(msg.get("body", "(no message generated)"))
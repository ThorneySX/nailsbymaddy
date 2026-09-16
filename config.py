"""
Nails by Maddy — site content.

Everything Maddy still owes us lives in OUTSTANDING below. Fill a value in,
re-run build_site.py, and that section switches from placeholder to real.

DRAFT = True   → missing sections render as visible, labelled placeholders,
                 plus a draft ribbon and noindex. Safe to share, not to launch.
DRAFT = False  → missing sections are omitted entirely, so nothing half-built
                 is ever public. Flip this on launch day.
"""

DRAFT = True

DOMAIN = "nailsbymaddy.co.uk"
SITE_URL = f"https://{DOMAIN}"

BUSINESS = {
    "name": "Nails by Maddy",
    "tagline": "Natural nail specialist",
    "phone": "07727 674214",
    "phone_e164": "+447727674214",
    # wa.me wants the number with no + and no leading zero.
    # Confirmed 15 Sept 2026: WhatsApp is on this same mobile.
    # Set to "" to drop the WhatsApp button entirely.
    "whatsapp": "447727674214",
    "whatsapp_msg": "Hi Maddy, I'd like to book an appointment.",
    "email": f"hello@{DOMAIN}",
    "venue": "Kizuri Beauty Parlour",
    "street": "162 Hamlet Court Road",
    "town": "Westcliff-on-Sea",
    "county": "Essex",
    "postcode": "SS0 7LJ",
    "country": "GB",
    "instagram": "nailsbymads.x",
    "maps": "https://maps.app.goo.gl/h7EepLr9fGA2HLPu8",
    "years": 8,
}

# ---------------------------------------------------------------- outstanding
# Every one of these is waiting on Maddy. Empty = not supplied yet.

OUTSTANDING = {
    # Full URL of whichever booking system wins — Booksy or Kizuri's Ovatu.
    # Until then every "Book" button falls back to the phone number, which
    # always works.
    "booking_url": "",

    # [{"day": "Tuesday", "open": "09:30", "close": "18:00"}, ...]
    # Use an empty list for days she isn't at the salon.
    "hours": [],

    # Photos of her work. {"file": "work-01.jpg", "alt": "..."}
    "gallery": [],

    # {"file": "maddy.jpg", "alt": "Maddy at her station at Kizuri"}
    "portrait": None,

    # e.g. "VTCT Level 3 Nail Technology" — and her insurer, for the footer.
    "qualifications": "",
    "insurer": "",

    # The builder gel she uses. Decides whether we can legally say "BIAB",
    # which is a trademark of The Gel Bottle Inc — not a generic term.
    "builder_gel_brand": "",
}

# --------------------------------------------------------------------- copy

HERO = {
    "eyebrow": f"{BUSINESS['town']} · Southend",
    "h1": "Nails that last, on nails that stay healthy.",
    "lead": (
        "Natural nail specialist. Gel, builder and hard gel, nail art and "
        "spa pedicures — eight years in the trade, and no acrylic in sight."
    ),
}

TRUST = ["8 years' experience", "Natural nails only", "Sensitive nails welcome", "Nail art"]

ABOUT = [
    "I work from Kizuri Beauty Parlour on Hamlet Court Road, and I look after "
    "natural nails — strengthening them with builder and hard gel rather than "
    "covering them up.",
    "If your nails are sensitive, peeling, or recovering from acrylics, that is "
    "what I do all day. You'll get the same pair of hands every time, and an "
    "honest answer about what your nails can take.",
]

# Real reviews. Confirm with each client before this goes live — the Google one
# is already public, the other two came off the booking system.
REVIEWS = [
    {"text": "Always incredible service from Maddy. Nails are perfect and uniform every single time.",
     "who": "Charley A", "src": "Google", "public": True},
    {"text": "Maddy always is very professional and I am always happy with the result.",
     "who": "Sarah", "src": "Booking system", "public": False},
    {"text": "I leave every appointment feeling so pampered.",
     "who": "Paula", "src": "Booking system", "public": False},
]

# Prices come from services.json — the live booking menu — grouped for reading.
# (raw title in services.json, name shown on the site)
GROUPS = [
    ("Gel manicures & pedicures", [
        ("Gel Manicure- Natural Nails", "Gel manicure"),
        ("Gel Manicure & Removal- Natural Nails", "Gel manicure & removal"),
        ("Gel Pedicure- Natural nails", "Gel pedicure"),
        ("Gel pedicure & removal", "Gel pedicure & removal"),
        ("Gel Manicure & Pedicure Combination- Natural Nails", "Gel manicure & pedicure"),
        ("Gel Manicure & Pedicure with removals- Natural Nails", "Gel mani & pedi, with removals"),
    ]),
    ("Overlays & extensions", [
        ("Natural Nail Overlays- Builder Gel", "Builder gel overlays"),
        ("Natural Nail Overlays-Builder Gel- Infill", "Builder gel infill"),
        ("Natural Nail overlays- Hard Gel", "Hard gel overlays"),
        ("Natural nail overlays- Hard Gel- Infill", "Hard gel infill"),
        ("Hard Gel Extensions", "Hard gel extensions"),
        ("Non standard acryclic removal", "Removal of another salon's acrylics"),
    ]),
    ("Spa pedicures", [
        ("Spa Pedicure- Natural Nails", "Spa pedicure"),
        ("Spa pedicure & removal- Natural Nails", "Spa pedicure & removal"),
        ("Spa Pedicure & Manicure- Natural Nails", "Spa pedicure & manicure"),
        ("Spa Pedicure & Manicure with removal- Natural Nails", "Spa pedi & mani, with removal"),
        ("Men’s Pedicure", "Men's pedicure"),
    ]),
    ("Nail art — added to any service", [
        ("Nail Art- Level 1- 15mins- Add on", "Level 1 — French, ombré, minimal"),
        ("Nail Art Level 2- 30 mins- Add on", "Level 2 — intricate art"),
        ("Nail Art Level 3- Add on", "Level 3 — line work, watercolour, 3D"),
    ]),
]

SEO = {
    # "Westcliff-on-Sea" alone was costing us the town that actually gets
    # searched: "nail salon southend" 590/mo and "nails southend on sea"
    # 320/mo, against 10/mo for "nail salon westcliff on sea". Westcliff stays
    # — it's where she is, and it's what the map pack matches on — but Southend
    # has to be in the title too.
    # Keep both towns but stay inside what Google actually displays: ~60
    # characters for the title, ~155 for the description.
    "title": "Nails by Maddy | Gel & Builder Gel Nails, Westcliff, Southend",
    "description": (
        "Gel, builder gel and hard gel on natural nails, plus nail art and "
        "pedicures. Nail technician at Kizuri, Hamlet Court Road, "
        "Westcliff-on-Sea. No acrylics."
    ),
}

# FAQ. Each one is a real question clients ask, and three of them also happen
# to be things people type into Google. The builder gel / BIAB answer is the
# important one — see the note in the README.
FAQS = [
    ("What's the difference between builder gel, hard gel and BIAB?",
     "BIAB stands for Builder In A Bottle, and it is a specific product made by "
     "The Gel Bottle Inc — not a general term, though plenty of salons use it "
     "that way. Builder gel is the category: a thicker gel painted over your own "
     "nail to add strength, which soaks off like a normal gel. Hard gel is a "
     "different chemistry again — stronger, better for adding length, and it has "
     "to be filed off rather than soaked. I'll tell you which one suits your "
     "nails when I see them."),

    ("Do you do acrylics?",
     "No, and I don't take them off as part of a normal appointment either — "
     "removing another salon's acrylics is its own booking. I work on natural "
     "nails, strengthening them rather than covering them up."),

    ("My nails are wrecked from acrylics. Can you fix them?",
     "Usually, yes, though it takes a few appointments rather than one. We take "
     "the old product off properly, then use builder or hard gel to protect the "
     "nail while it grows out. You'll get an honest answer about how long it "
     "will take at the first appointment."),

    ("How long will a set last?",
     "Three to four weeks for most people before you'll want an infill, though "
     "it depends on how fast your nails grow and what you do with your hands. "
     "If a set lifts within a week, come back and I'll sort it."),

    ("Where are you, and do you cover Southend?",
     "I work from Kizuri Beauty Parlour at 162 Hamlet Court Road in "
     "Westcliff-on-Sea — a few minutes from Westcliff station, and easy to get "
     "to from anywhere in Southend, Leigh or Chalkwell."),
]

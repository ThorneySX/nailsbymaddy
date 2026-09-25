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
    # The bold line on the address is HER name, not the salon's. She is the
    # business; the salon is where she works from. It also means the page does
    # not lean on Kizuri's name before Kizuri has agreed to it.
    "venue": "Kizuri Beauty Parlour",
    "venue_note": "inside Kizuri Beauty Parlour",
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

    # Confirmed by Maddy 25 Sept 2026. Days not listed are days she isn't at
    # Kizuri. A "season" key marks hours that only apply part of the year —
    # see SEASONS below. Everything else runs all year.
    "hours": [
        {"day": "Monday",   "open": "09:00", "close": "15:00"},
        {"day": "Thursday", "open": "09:00", "close": "21:00", "season": "summer"},
        {"day": "Thursday", "open": "09:00", "close": "19:00", "season": "winter"},
        {"day": "Friday",   "open": "09:00", "close": "18:30"},
        {"day": "Saturday", "open": "09:00", "close": "18:30"},
    ],

    # Photos of her work, supplied 25 Sept 2026 in two batches. Squared from her
    # own photographs and ordered for impact rather than by date — the line work
    # and the hand-painted art are what stop someone scrolling, and the plain
    # gloss sets are what a nervous first-timer is looking for. Alternating the
    # two means neither run of images reads as "she only does one thing".
    #
    # Alt text describes the nails, not the client. It is what a screen reader
    # reads out and what Google has to go on, so "red glitter with silver line
    # work" earns its place where "nails" does not.
    "gallery": [
        {"file": "work-09.jpg",
         "alt": "Almond nails hand-painted in an autumn stained-glass design — "
                "olive green, burnt orange, mustard and burgundy panels outlined "
                "in gold line work",
         "level": 3,
         "note": "Every panel is painted by hand and then outlined in gold — that outline "
                 "is what makes it read as stained glass rather than blocks of colour. "
                 "Slow work, and worth it."},
        {"file": "work-01.jpg",
         "alt": "Short square nails in dark red glitter gel with fine silver "
                "star and swirl line work",
         "level": 3,
         "note": "A dark red glitter gel with the stars and swirls drawn on afterwards in "
                 "fine silver. Line work this thin is steadier on a shorter nail, which is "
                 "exactly what this set is."},
        {"file": "work-17.jpg",
         "alt": "Almond nails in black gel with sculpted silver liquid-metal chrome, a "
                 "checkerboard panel and flame detail",
         "level": 3,
         "note": "Long almond nails with a silver liquid-metal chrome sculpted over "
                 "black, plus a checkerboard and flames. The raised chrome is built up "
                 "in gel, so it catches the light the way real metal does."},
        {"file": "work-06.jpg",
         "alt": "Short square natural nails in a classic white French manicure "
                "over a sheer pink base",
         "level": 1,
         "note": "A proper French on natural nails — no extensions, no overlay, just a "
                 "clean smile line on the nail you already have. It's the set I do most, "
                 "and the one that shows up any shortcuts."},
        {"file": "work-14.jpg",
         "alt": "Short round nails in a midnight blue glitter ombré with "
                "hand-painted gold stars, crescent moons and fine gold dots",
         "level": 2,
         "note": "Midnight blue glitter faded up from the tip, then stars and moons picked "
                 "out in gold on top. The ombré does the work and the gold gives it "
                 "somewhere to land."},
        {"file": "work-18.jpg",
         "alt": "Long almond nails with baby blue French tips marbled with fine white "
                 "swirls",
         "level": 2,
         "note": "Almond nails with baby blue tips and a fine white swirl marbled "
                 "through each one. A French that stays soft — the swirl stops it "
                 "looking like a flat block of colour."},
        {"file": "work-08.jpg",
         "alt": "Short natural nails in an iridescent pearl chrome finish with a "
                "hand-painted neon pink wave across each nail",
         "level": 2,
         "note": "A pearl chrome pressed over a soft white base, with a single neon pink "
                 "line painted across each nail. Chrome shifts as your hand moves, so it "
                 "never photographs quite the way it looks."},
        {"file": "work-13.jpg",
         "alt": "Long nails with hand-sculpted 3D gemstones in jade, amber, rose "
                "and teal, set in gold line work over a soft pink base",
         "level": 3,
         "note": "Each stone is sculpted in gel on the nail, cured, then framed in gold. "
                 "It's the most involved thing I do — and it still falls under the Level 3 "
                 "add-on."},
        {"file": "work-05.jpg",
         "alt": "Almond nails with red French tips finished in white polka dots",
         "level": 1,
         "note": "Red tips with white dots placed over the top — a French with something "
                 "to say. Easy to wear, and it grows out neatly."},
        {"file": "work-15.jpg",
         "alt": "Short almond nails in black gel and nude French tips with tiny "
                 "hand-painted cats peeking over the edge",
         "level": 2,
         "note": "Tiny cats peeking over the tips, painted freehand on a black and nude "
                 "French. Faces this small are all in the eyes — a fraction out and it "
                 "stops looking like a cat."},
        {"file": "work-11.jpg",
         "alt": "Short nails on a man's hand in black gel with deep red glitter "
                "panels and hand-painted silver line work",
         "level": 3,
         "note": "Men's nails, and one of my favourite sets to do. Black gel with red "
                 "glitter broken through it and silver line work over the top — short, "
                 "tidy, nothing that gets in the way."},
        {"file": "work-10.jpg",
         "alt": "Short round natural nails alternating deep plum gloss with a "
                "hand-painted tortoiseshell print in brown, burgundy and cream",
         "level": 2,
         "note": "Deep plum on alternate nails and a tortoiseshell painted on the rest, "
                 "built in layers so the edges stay soft. Short natural nails take a dark "
                 "colour better than people expect."},
        {"file": "work-03.jpg",
         "alt": "Almond nails with a soft pink base, magenta hand-painted stars, "
                "gold glitter and magenta French tips",
         "level": 2,
         "note": "Hand-painted stars over a soft pink base, with gold glitter and a "
                 "magenta tip. Painted rather than stuck on, so there's nothing to catch."},
        {"file": "work-04.jpg",
         "alt": "Medium almond nails in a glossy bright red gel",
         "level": None,
         "note": "No art at all — just a bright red gel on natural nails, applied "
                 "properly. A good red is harder than it looks: it shows every ridge and "
                 "every thin patch."},
        {"file": "work-12.jpg",
         "alt": "Short nails in a pastel summer set — lemon yellow with striped "
                "and ruched finishes, a pink French tip and a hand-sculpted 3D "
                "flower",
         "level": 3,
         "note": "A summer set with four finishes on one hand — flat yellow, stripes, a "
                 "ruched texture and a sculpted flower. The flower is built up in gel on "
                 "the nail, not glued on."},
        {"file": "work-19.jpg",
         "alt": "Almond nails mixing a white French with a hand-painted black star, "
                 "blotted pink dots, a black-and-white zebra tip and glossy burgundy",
         "level": 2,
         "note": "Four different finishes on one hand: a black star on a white French, "
                 "blotted pink dots, a zebra tip, and a plain burgundy. A good way to "
                 "try a few things without committing the whole set to one."},
        {"file": "work-16.jpg",
         "alt": "Short almond nails with bright orange French tips and hand-painted "
                 "oranges with green leaves on the accent nail",
         "level": 2,
         "note": "Bright orange French tips with oranges painted on the ring finger, "
                 "leaves and all. A summer set that still reads as a French from across "
                 "a room."},
        {"file": "work-02.jpg",
         "alt": "Short natural nails with a pale pink base and multicoloured "
                "French tips in yellow, pink and blue with fine dots",
         "level": 1,
         "note": "Bright French tips in a different colour on each nail, finished with "
                 "fine dots. Short natural nails, no overlay underneath."},
        {"file": "work-07.jpg",
         "alt": "Almond nails with striped French tips in pastel blue, yellow, "
                "pink and chocolate brown",
         "level": 2,
         "note": "Four colours striped across each tip, in the same order every time. "
                 "Getting them even across ten nails is the whole job."},
    ],

    # Supplied 25 Sept 2026. Cropped to 4:5 from her own photograph; the file
    # lives in photos/ and is copied into public/img at build time.
    "portrait": {
        "file": "maddy.jpg",
        "alt": "Maddy at her station at Kizuri Beauty Parlour in Westcliff-on-Sea",
    },

    # Confirmed by Maddy 25 Sept 2026. She gave the levels, not the awarding
    # body, so the awarding body is deliberately not named — do not guess it.
    # Insurance certificate still to arrive; the insurer is her own statement.
    "qualifications": "Level 2 and Level 3 qualified in Nail Technology",
    "insurer": "Simply Business",

    # The builder gel she uses. Decides whether we can legally say "BIAB",
    # which is a trademark of The Gel Bottle Inc — not a generic term.
    # Confirmed by Maddy 25 Sept 2026: Twenty Pro and American Creator hard
    # gels, plus builder gel and other bases. Both HEMA and HEMA-free lines.
    # She does NOT use The Gel Bottle Inc, so the site must never say "BIAB"
    # as her product — the first FAQ explains why, and that stays.
    "builder_gel_brand": "Twenty Pro and American Creator hard gel",
}

# --------------------------------------------------------------------- copy

HERO = {
    "eyebrow": f"{BUSINESS['town']} · Southend",
    # The old line — "Nails that last, on nails that stay healthy" — sold a
    # category. Plenty of salons could put it up. This sells HER: eight years,
    # Level 3 qualified, natural nails only, and the one thing that actually
    # decides whether a nervous client books, which is that she will say no.
    "h1": "Eight years of natural nails, Westcliff and Southend.",
    "lead": (
        "Level 2 and Level 3 qualified, and no acrylic in sight. I strengthen "
        "your own nails with builder and hard gel rather than covering them "
        "up — and if your nails can't take what you're asking for, I'll tell "
        "you before we start, not after."
    ),
}

TRUST = ["8 years' experience", "Level 2 & 3 qualified",
         "HEMA-free available", "Natural nails only"]

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
# (group heading, one-line description, [(raw title in services.json, name shown)])
#
# The description exists because a price list without one makes the reader do
# the work: "Overlays & extensions" tells someone who already knows what they
# want nothing they did not know, and tells a first-timer nothing at all. One
# sentence under each heading is the difference between a menu and a list.
GROUPS = [
    ("Gel manicures & pedicures",
     "Colour on your own nails, soaked off cleanly when you are ready. "
     "No overlay, no extensions.", [
        ("Gel Manicure- Natural Nails", "Gel manicure"),
        ("Gel Manicure & Removal- Natural Nails", "Gel manicure & removal"),
        ("Gel Pedicure- Natural nails", "Gel pedicure"),
        ("Gel pedicure & removal", "Gel pedicure & removal"),
        ("Gel Manicure & Pedicure Combination- Natural Nails", "Gel manicure & pedicure"),
        ("Gel Manicure & Pedicure with removals- Natural Nails", "Gel mani & pedi, with removals"),
    ]),
    ("Overlays & extensions",
     "Hard gel or builder gel over the natural nail for strength, or added "
     "length where you want it.", [
        ("Natural Nail Overlays- Builder Gel", "Builder gel overlays"),
        ("Natural Nail Overlays-Builder Gel- Infill", "Builder gel infill"),
        ("Natural Nail overlays- Hard Gel", "Hard gel overlays"),
        ("Natural nail overlays- Hard Gel- Infill", "Hard gel infill"),
        ("Hard Gel Extensions", "Hard gel extensions"),
        ("Non standard acryclic removal", "Removal of another salon's acrylics"),
    ]),
    ("Spa pedicures",
     "A full foot treatment rather than a polish change, using medical-grade "
     "Footlogix and Margaret Dabbs products.", [
        ("Spa Pedicure- Natural Nails", "Spa pedicure"),
        ("Spa pedicure & removal- Natural Nails", "Spa pedicure & removal"),
        ("Spa Pedicure & Manicure- Natural Nails", "Spa pedicure & manicure"),
        ("Spa Pedicure & Manicure with removal- Natural Nails", "Spa pedi & mani, with removal"),
        ("Men’s Pedicure", "Men's pedicure"),
    ]),
    ("Nail art — added to any service",
     "Priced by how long it takes, from a simple French through to hand-painted "
     "line work and sculpted 3D.", [
        ("Nail Art- Level 1- 15mins- Add on", "Level 1 — French, ombré, minimal"),
        ("Nail Art Level 2- 30 mins- Add on", "Level 2 — intricate art"),
        ("Nail Art Level 3- Add on", "Level 3 — line work, watercolour, 3D"),
    ]),
]

# The products she uses, in her words. This sits with the prices because the
# first question a careful client asks is what is going on their nails, and the
# second is whether it will set them off.
#
# The brand names are set in type, never as their logos: Twenty Pro and
# American Creator are other companies' trademarks and we do not hold their
# artwork. Naming the products you use is ordinary and factual; redrawing
# someone's logo is not.
PRODUCTS = {
    "heading": "What I use",
    "body": (
        "Professional hard gel systems from Twenty Pro — SCULPT and BOOST, in "
        "both bottled and pot formulas — and American Creator Framework Gel. "
        "Less flexibility, which is what allows maximum strength. Builder gel "
        "and other bases are available too."
    ),
    # Set apart on the page and on the printed list. It is the line that makes
    # someone who has reacted before feel able to book at all.
    "highlight": (
        "HEMA and HEMA-free products are available, to tailor to every nail "
        "type and sensitivity."
    ),
    "aside": (
        "Any questions about products or services — message me on WhatsApp or "
        "Instagram, or email hello@nailsbymaddy.co.uk."
    ),
}

SEO = {
    # "Westcliff-on-Sea" alone was costing us the town that actually gets
    # searched: "nail salon southend" 590/mo and "nails southend on sea"
    # 320/mo, against 10/mo for "nail salon westcliff on sea". Westcliff stays
    # — it's where she is, and it's what the map pack matches on — but Southend
    # has to be in the title too.
    # Keep both towns but stay inside what Google actually displays: ~60
    # characters for the title, ~155 for the description.
    "title": "Nails by Maddy | Gel & Builder Gel Nails, Westcliff, Southend",
    # Leads with what is searched (Southend, Westcliff, gel nails), says what
    # makes her different in four words (natural nails, no acrylics), and
    # carries the qualification. It no longer leans on Kizuri's name — that
    # is where she works, not what she is selling, and their sign-off on
    # using the address is still outstanding.
    "description": (
        "Level 2 and 3 qualified nail technician in Westcliff-on-Sea and "
        "Southend. Gel, builder gel and hard gel on natural nails. HEMA-free "
        "available, no acrylics."
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
     "different chemistry again — less flexible, so it takes more before it "
     "gives. That makes it stronger and better for adding length, and it has to "
     "be filed off rather than soaked. I use Twenty Pro and American Creator "
     "hard gels, and I keep builder gel and other bases as well. I'll tell you "
     "which one suits your nails when I see them."),

    ("My nails are sensitive, or I've reacted to gel before. Can you still do them?",
     "Usually, yes. I stock both HEMA and HEMA-free products, so I can work "
     "around different nail types and sensitivities rather than putting everyone "
     "through the same system. If you've had a reaction before, tell me when you "
     "book and I'll use the HEMA-free range. If you're not sure what caused it, "
     "say so anyway — I'd rather start gently and work it out than guess."),

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


# Seasonal hours. Maddy's Thursday changes with the clocks: later in summer
# because people come after work while it's light.
#
# The page states both windows in plain English, so it is right whether or not
# anyone remembers to rebuild. The structured data carries only the window that
# is actually in force at build time, with explicit dates — schema.org's
# validFrom/validThrough take real dates, not recurring ones, so publishing
# both would mean publishing one that is false today.
SEASONS = {
    "summer": {"label": "April to September", "start": (4, 1),  "end": (9, 30)},
    "winter": {"label": "October to March",   "start": (10, 1), "end": (3, 31)},
}


# ---------------------------------------------------------------- nail art
# The three art tiers, tied to the exact rows in services.json so the price
# shown on a photograph can never drift from the price shown on the menu.
# build_site.py reads the price from there; nothing here repeats a number.
#
# Level 3 is the gold standard — line work, watercolour and 3D — and it is
# the tier most of her best sets fall into. Naming it on the photograph is
# the point of the whole feature: someone sees the gemstones, learns that is
# a £10 add-on, and books it.
#
# >>> THE LEVEL ON EACH PHOTOGRAPH IS NOT YET CONFIRMED BY MADDY. <<<
# They were read off the images against her own tier descriptions (Level 1
# French/ombré/minimal, Level 2 intricate, Level 3 line work/watercolour/3D).
# A wrong level sits next to a real price, so she signs these off before
# DRAFT flips to False.
ART_LEVELS = {
    1: {"label": "Level 1 nail art",
        "blurb": "French, ombré and minimal detail",
        "service": "Nail Art- Level 1- 15mins- Add on"},
    2: {"label": "Level 2 nail art",
        "blurb": "intricate hand-painted art",
        "service": "Nail Art Level 2- 30 mins- Add on"},
    3: {"label": "Level 3 nail art",
        "blurb": "line work, watercolour and 3D — the top tier",
        "service": "Nail Art Level 3- Add on"},
}

"""Musical style/genre vocabulary.

Each entry is the spoken form (lowercased, space-separated tokens).
The canonical form (sent over OSC) is the snake_case version unless overridden.

Add new styles here — that's all you need. The grammar builder pulls
unique tokens automatically and the parser does longest-match.
"""

# (spoken_phrase, canonical_id) — canonical defaults to snake_case if None.
STYLES: list[tuple[str, str | None]] = [
    # Rock family
    ("rock", None),
    ("punk", None),
    ("punk rock", None),
    ("hard rock", None),
    ("classic rock", None),
    ("indie rock", None),
    ("alt rock", None),
    ("garage rock", None),
    ("psychedelic rock", None),
    ("progressive rock", "prog_rock"),
    ("prog rock", "prog_rock"),

    # Metal
    ("metal", None),
    ("heavy metal", None),
    ("death metal", None),
    ("thrash metal", None),
    ("black metal", None),
    ("doom metal", None),
    ("nu metal", None),

    # Pop
    ("pop", None),
    ("indie pop", None),
    ("synth pop", None),
    ("dream pop", None),

    # Jazz
    ("jazz", None),
    ("smooth jazz", None),
    ("jazz fusion", None),
    ("bebop", None),
    ("swing", None),
    ("gypsy jazz", None),
    ("cool jazz", None),
    ("modal jazz", None),

    # Blues
    ("blues", None),
    ("delta blues", None),
    ("chicago blues", None),

    # Funk / Soul / R&B
    ("funk", None),
    ("soul", None),
    ("motown", None),
    ("disco", None),
    ("r and b", "rnb"),
    ("rhythm and blues", "rnb"),
    ("neo soul", None),

    # Hip-hop / Rap
    ("hip hop", None),
    ("rap", None),
    ("trap", None),
    ("drill", None),
    ("boom bap", None),
    ("lo fi hip hop", "lofi_hiphop"),

    # Electronic
    ("electronic", None),
    ("house", None),
    ("deep house", None),
    ("tech house", None),
    ("techno", None),
    ("trance", None),
    ("dubstep", None),
    ("drum and bass", "dnb"),
    ("dnb", None),
    ("garage", None),
    ("ambient", None),
    ("edm", None),
    ("synthwave", None),
    ("lofi", None),
    ("lo fi", "lofi"),
    ("chill", None),
    ("downtempo", None),
    ("idm", None),

    # Latin
    ("latin", None),
    ("bossa nova", None),
    ("samba", None),
    ("salsa", None),
    ("reggaeton", None),
    ("cumbia", None),
    ("tango", None),
    ("mambo", None),
    ("cha cha", None),
    ("merengue", None),
    ("flamenco", None),

    # Caribbean
    ("reggae", None),
    ("ska", None),
    ("dub", None),
    ("dancehall", None),

    # Country / Folk / Americana
    ("country", None),
    ("folk", None),
    ("bluegrass", None),
    ("americana", None),
    ("honky tonk", None),

    # Classical / Cinematic
    ("classical", None),
    ("baroque", None),
    ("orchestral", None),
    ("cinematic", None),
    ("score", None),

    # World / Other
    ("afrobeat", None),
    ("afro", None),
    ("gospel", None),
    ("ballad", None),
    ("waltz", None),
    ("march", None),
    ("shuffle", None),
    ("groove", None),
    ("acoustic", None),
]


def canonical(spoken: str, override: str | None) -> str:
    return override if override else spoken.replace(" ", "_")


def all_style_tokens() -> set[str]:
    """All unique single-word tokens used by any style phrase."""
    out: set[str] = set()
    for spoken, _ in STYLES:
        out.update(spoken.split())
    return out


def all_style_phrases() -> list[tuple[str, str]]:
    """[(spoken_phrase, canonical_id)] sorted longest-first for greedy matching."""
    phrases = [(s, canonical(s, c)) for s, c in STYLES]
    phrases.sort(key=lambda p: len(p[0].split()), reverse=True)
    return phrases

"""
Human-readable slug generator for agents.

Generates three-word slugs in adjective-verb-noun pattern,
e.g. "brave-sailing-fox" or "quiet-dancing-river".

Used as a stable, human-friendly identifier that LLMs can
reliably reproduce in output (unlike opaque hex IDs).
"""

import random

_ADJECTIVES = [
    "amber", "bold", "bright", "calm", "clear", "cool", "coral", "crisp",
    "dark", "deep", "eager", "fair", "fast", "firm", "fond", "fresh",
    "glad", "gold", "grand", "green", "happy", "keen", "kind", "light",
    "live", "lunar", "mild", "neat", "noble", "olive", "opal", "pale",
    "plain", "polar", "proud", "pure", "quick", "quiet", "rapid", "rare",
    "red", "rich", "ripe", "rosy", "ruby", "safe", "sage", "sharp",
    "shy", "silk", "slim", "smart", "soft", "solar", "solid", "sonic",
    "spry", "stark", "steel", "still", "stone", "stout", "sunny", "sure",
    "sweet", "swift", "tall", "teal", "tidy", "tiny", "true", "vast",
    "vivid", "warm", "white", "whole", "wide", "wild", "wise", "young",
    "azure", "blaze", "cedar", "chill", "civic", "cloud", "cobalt", "dawn",
    "delta", "dusk", "dusty", "ember", "equal", "fern", "fiery", "fleet",
    "flint", "flora", "focal", "forge", "frost", "gale", "gentle", "giant",
    "gleam", "glow", "grove", "hazel", "heron", "humble", "iron", "ivory",
    "jade", "jolly", "lemon", "lilac", "lofty", "loyal", "lucid", "maple",
    "merry", "misty", "mossy", "natal", "nimble", "north", "nova", "ocean",
    "onyx", "otter", "outer", "pearl", "petal", "pilot", "pine", "pixel",
    "plum", "prime", "prism", "quartz", "raven", "ready", "reef", "royal",
    "rustic", "sable", "sandy", "satin", "scout", "serene", "shore", "silver",
    "slate", "sleek", "snowy", "south", "spark", "spiral", "spring", "spruce",
    "steady", "storm", "straw", "stripe", "terra", "thorn", "tiger", "timber",
    "topaz", "torch", "trail", "tulip", "ultra", "upper", "urban", "velvet",
    "verdant", "vigor", "violet", "vital", "vocal", "woven", "zephyr", "zinc",
]

_VERBS = [
    "baking", "blazing", "bold", "calling", "carving", "casting",
    "chasing", "climbing", "coasting", "crafting", "crossing", "curving",
    "dancing", "daring", "dashing", "diving", "drawing", "dreaming",
    "drifting", "driving", "falling", "fading", "feeding", "fishing",
    "flashing", "floating", "flowing", "flying", "folding", "forging",
    "forming", "gaining", "gazing", "gliding", "glowing", "going",
    "gracing", "growing", "guiding", "hailing", "healing", "hearing",
    "hiding", "hiking", "holding", "hoping", "hosting", "hunting",
    "joining", "jumping", "keeping", "landing", "lasting", "leading",
    "leaning", "leaping", "lifting", "linking", "living", "loading",
    "making", "mapping", "marching", "mending", "mining", "missing",
    "mixing", "molding", "moving", "naming", "nesting", "noting",
    "pacing", "paving", "paying", "picking", "planting", "playing",
    "pouring", "pressing", "pulling", "pushing", "racing", "raining",
    "raising", "ranging", "reading", "reaping", "riding", "ringing",
    "rising", "roaming", "rolling", "rowing", "ruling", "running",
    "rushing", "sailing", "saving", "scaling", "seeing", "seeking",
    "sending", "setting", "shaping", "sharing", "shining", "singing",
    "sitting", "skating", "sliding", "soaring", "solving", "sorting",
    "sowing", "spinning", "standing", "starting", "staying", "steering",
    "storing", "striking", "surfing", "swimming", "swinging", "taking",
    "talking", "taming", "tending", "testing", "thinking", "tipping",
    "tossing", "tracing", "trading", "trailing", "turning", "typing",
    "using", "viewing", "wading", "waiting", "waking", "walking",
    "waving", "wearing", "weaving", "winding", "winning", "wishing",
    "working", "writing", "yawning", "yielding",
]

_NOUNS = [
    "acorn", "anchor", "ant", "arch", "arrow", "aspen", "atlas", "badge",
    "bark", "basin", "bay", "beam", "bear", "bell", "berry", "birch",
    "blade", "bloom", "boat", "bolt", "bone", "book", "bow", "branch",
    "brass", "breeze", "brick", "bridge", "brook", "brush", "cedar",
    "chain", "chalk", "cliff", "cloud", "coast", "comet", "cone", "coral",
    "crane", "creek", "crest", "crow", "crown", "dagger", "dawn", "deer",
    "delta", "dove", "drum", "dust", "eagle", "echo", "edge", "elk",
    "elm", "ember", "eve", "falcon", "fawn", "fern", "finch", "flame",
    "flint", "flower", "fog", "forest", "forge", "fossil", "fox", "frost",
    "gate", "gem", "glade", "glen", "globe", "grain", "grove", "gull",
    "harbor", "hare", "harp", "hawk", "heath", "heron", "hill", "holly",
    "horn", "hound", "isle", "ivy", "jade", "jay", "jewel", "key",
    "kite", "knoll", "lake", "lark", "laurel", "leaf", "ledge", "light",
    "lily", "lion", "lodge", "lotus", "lynx", "maple", "marsh", "meadow",
    "mesa", "mill", "mint", "mist", "moon", "moose", "moss", "moth",
    "mound", "oak", "oasis", "olive", "orbit", "orchid", "osprey", "otter",
    "owl", "palm", "panda", "path", "peak", "pearl", "pebble", "pine",
    "plum", "pond", "poppy", "prism", "quail", "rain", "raven", "reef",
    "ridge", "river", "robin", "rock", "rose", "sage", "sand", "seed",
    "shade", "shell", "shore", "silk", "slate", "smoke", "snow", "spark",
    "spruce", "star", "stone", "storm", "stream", "summit", "sun", "swan",
    "thorn", "tide", "tiger", "torch", "trail", "tree", "tulip", "vale",
    "vine", "violet", "wand", "wave", "whale", "wheel", "willow", "wind",
    "wolf", "wren", "yarrow", "yew", "zenith",
]


def generate_slug() -> str:
    """Generate a random three-word slug like 'brave-sailing-fox'."""
    return (  # nosec B311 - not used for security, just human-readable identifiers
        f"{random.choice(_ADJECTIVES)}-"  # nosec B311
        f"{random.choice(_VERBS)}-"  # nosec B311
        f"{random.choice(_NOUNS)}"  # nosec B311
    )

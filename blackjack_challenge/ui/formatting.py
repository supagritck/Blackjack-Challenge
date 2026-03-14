"""
ANSI colour helpers and card art rendering.
"""
from typing import List
from blackjack_challenge.models.card import Card


# ── ANSI codes ─────────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"
DIM    = "\033[2m"


def red(text: str) -> str:    return f"{RED}{text}{RESET}"
def green(text: str) -> str:  return f"{GREEN}{text}{RESET}"
def yellow(text: str) -> str: return f"{YELLOW}{text}{RESET}"
def cyan(text: str) -> str:   return f"{CYAN}{text}{RESET}"
def bold(text: str) -> str:   return f"{BOLD}{text}{RESET}"
def dim(text: str) -> str:    return f"{DIM}{text}{RESET}"


# ── Card rendering ─────────────────────────────────────────────────────────────

_CARD_WIDTH = 7  # width of each card block including borders

_BACK = [
    "┌─────┐",
    "│░░░░░│",
    "│░░░░░│",
    "│░░░░░│",
    "└─────┘",
]


def _card_lines(card: Card) -> List[str]:
    """Return 5-line ASCII art for a single card."""
    if not card.face_up:
        return _BACK[:]

    rank = card.rank.value
    suit = card.suit.symbol

    # Pad rank to 2 chars for alignment
    rank_l = rank.ljust(2)   # top-left
    rank_r = rank.rjust(2)   # bottom-right

    lines = [
        f"┌─────┐",
        f"│{rank_l}   │",
        f"│  {suit}  │",
        f"│   {rank_r}│",
        f"└─────┘",
    ]

    if card.colour == "Red":
        lines = [red(line) for line in lines]
    return lines


def render_cards_row(cards: List[Card], active: bool = False) -> str:
    """Render a row of cards side-by-side. Returns multi-line string."""
    if not cards:
        return ""

    all_lines = [_card_lines(c) for c in cards]
    rows = []
    for i in range(5):
        row = "  ".join(line_set[i] for line_set in all_lines)
        rows.append(row)

    prefix = "> " if active else "  "
    return "\n".join(prefix + row for row in rows)


def outcome_label(outcome: str) -> str:
    mapping = {
        "WIN":             green("WIN"),
        "BLACKJACK":       green("BLACKJACK"),
        "FIVE CARD TRICK": green("FIVE CARD TRICK"),
        "21 - AUTO WIN":   green("21 - AUTO WIN"),
        "LOSE":            red("LOSE"),
    }
    return mapping.get(outcome, outcome)

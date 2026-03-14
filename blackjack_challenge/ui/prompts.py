"""
All user input collection with validation loops.
"""
from decimal import Decimal, InvalidOperation
from typing import List

from blackjack_challenge.config import (
    MIN_BET, MAX_BET, MAX_SIDE_BET,
    VALID_DECK_COUNTS,
    BLAZING_7S_ENTRY,
)
from blackjack_challenge.ui.formatting import red, cyan, bold


def _input(prompt: str) -> str:
    return input(f"  {prompt}").strip()


def get_player_name() -> str:
    while True:
        name = _input("Enter your name: ")
        if name:
            return name
        print(red("  Name cannot be empty."))


def get_num_decks() -> int:
    while True:
        val = _input(f"Number of decks {VALID_DECK_COUNTS}: ")
        try:
            n = int(val)
            if n in VALID_DECK_COUNTS:
                return n
        except ValueError:
            pass
        print(red(f"  Please enter {' or '.join(str(d) for d in VALID_DECK_COUNTS)}."))


def get_starting_balance() -> Decimal:
    while True:
        val = _input("Starting balance $: ")
        try:
            amount = Decimal(val)
            if amount > 0:
                return amount
        except InvalidOperation:
            pass
        print(red("  Please enter a valid positive amount."))


def get_wager(balance: Decimal) -> Decimal:
    while True:
        val = _input(f"Place your bet (${MIN_BET}–${MAX_BET}, balance ${balance:,.2f}): $")
        try:
            amount = Decimal(val)
            if amount < MIN_BET:
                print(red(f"  Minimum bet is ${MIN_BET}."))
            elif amount > MAX_BET:
                print(red(f"  Maximum bet is ${MAX_BET}."))
            elif amount > balance:
                print(red("  Insufficient balance."))
            else:
                return amount
        except InvalidOperation:
            print(red("  Please enter a valid amount."))



def get_side_bets(balance: Decimal) -> dict:
    """
    Ask player which side bets they want.
    Returns dict of {bet_name: wager_amount}.
    """
    side_bets = {}
    print(f"\n  {bold('Optional Side Bets:')} (press Enter to skip each)")

    options = [
        ("star_pairs", "Star Pairs (Mixed 5:1 / Same Colour 8:1 / Suited 20:1 / Pair of Aces 30:1)"),
        ("blazing_7s", f"Blazing 7s (fixed ${BLAZING_7S_ENTRY})"),
    ]

    remaining = balance
    for key, label in options:
        if remaining <= 0:
            break

        if key == "blazing_7s":
            if remaining >= BLAZING_7S_ENTRY:
                val = _input(f"  {label} — join? (y/n): ")
                if val.lower() == "y":
                    side_bets[key] = BLAZING_7S_ENTRY
                    remaining -= BLAZING_7S_ENTRY
        else:
            val = _input(f"  {label} — wager $: ")
            if val == "":
                continue
            try:
                amount = Decimal(val)
                if amount <= 0:
                    continue
                if amount > MAX_SIDE_BET:
                    print(red(f"  Max side bet is ${MAX_SIDE_BET}. Skipping."))
                    continue
                if amount > remaining:
                    print(red("  Insufficient balance. Skipping."))
                    continue
                side_bets[key] = amount
                remaining -= amount
            except InvalidOperation:
                continue  # skip on invalid input

    return side_bets


def get_action(available: List[str]) -> str:
    """
    available: subset of ['H', 'S', 'D', 'P']
    Returns the chosen action key.
    """
    labels = {"H": "Hit", "S": "Stand", "D": "Double", "P": "Split"}
    prompt_parts = [f"[{k}]{labels[k]}" for k in available]
    prompt = "  Choose: " + "  ".join(cyan(p) for p in prompt_parts) + "  > "

    valid = {k.upper() for k in available}
    while True:
        raw = input(prompt).strip().upper()
        # Allow shorthand: 'SP' for split
        if raw == "SP":
            raw = "P"
        if raw in valid:
            return raw
        print(red(f"  Invalid choice. Enter one of: {', '.join(available)}"))


def get_play_again() -> bool:
    while True:
        val = _input("Play again? (y/n): ")
        if val.lower() in ("y", "yes"):
            return True
        if val.lower() in ("n", "no"):
            return False
        print(red("  Please enter y or n."))

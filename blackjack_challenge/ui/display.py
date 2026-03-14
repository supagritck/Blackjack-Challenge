"""
Terminal rendering: table state, results, messages.
"""
import os
from decimal import Decimal
from typing import List, Optional

from blackjack_challenge.models.hand import PlayerHand, DealerHand
from blackjack_challenge.models.player import Player, Dealer
from blackjack_challenge.ui.formatting import (
    bold, green, red, yellow, cyan, dim,
    render_cards_row, outcome_label,
    RESET,
)

DIVIDER     = "─" * 58
THICK_DIV   = "═" * 58


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def print_header(player: Player, shoe_remaining: int = 0):
    print(bold(THICK_DIV))
    title = bold("  BLACKJACK CHALLENGE")
    balance = f"Balance: {green(f'${player.balance:,.2f}')}"
    gap = 58 - len("  BLACKJACK CHALLENGE  ") - len(f"Balance: ${player.balance:,.2f}")
    print(f"{title}{' ' * max(gap, 2)}{balance}")
    print(f"  {dim(f'Shoe: {shoe_remaining} cards remaining')}")
    print(bold(THICK_DIV))


def print_dealer(dealer: Dealer, hide_second: bool = True):
    print(f"\n  {bold('DEALER')}")
    cards = dealer.hand.cards
    if hide_second and len(cards) >= 2:
        # Show first card face-up; hide the rest during player's turn
        visible = [cards[0]]
        showing = f"Showing: {cards[0].rank.value}{cards[0].suit.symbol}  |  Hidden: ?"
        print(f"  {dim(showing)}")
        print(render_cards_row(visible))
    else:
        total = dealer.hand.total()
        status = red("BUST") if dealer.hand.is_bust() else str(total)
        bj = bold(green("  ★ BLACKJACK")) if dealer.hand.is_blackjack() else ""
        print(f"  Total: {bold(status)}{bj}")
        print(render_cards_row(cards))


def print_player_hands(player: Player, active_index: Optional[int] = None):
    print(f"\n  {bold(f'PLAYER: {player.name}')}")
    for i, hand in enumerate(player.hands):
        is_active = (i == active_index)
        _print_single_hand(hand, i, is_active, len(player.hands) > 1)


def _print_single_hand(hand: PlayerHand, index: int, active: bool, multi: bool):
    prefix = "> " if active else "  "
    label = f"Hand {index + 1}" if multi else "Hand"

    total = hand.total()
    if hand.is_bust():
        total_str = red(f"{total} BUST")
    elif hand.is_complete and hand.outcome:
        total_str = f"{total}  [{outcome_label(hand.outcome)}]"
    else:
        total_str = bold(str(total))

    wager_str = f"Wager: ${hand.wager:,.2f}"
    if hand.doubled:
        wager_str += cyan("  [DOUBLED]")
    if hand.is_split_hand:
        wager_str += dim("  [SPLIT]")

    print(f"{prefix}{bold(label)}   Total: {total_str}   {wager_str}")
    print(render_cards_row(hand.cards, active=active))


def print_actions(actions: List[str]):
    print(f"\n  {bold('Actions:')}  ", end="")
    labels = {
        "H": "[H]it",
        "S": "[S]tand",
        "D": "[D]ouble",
        "P": "[Sp]lit",
    }
    parts = [cyan(labels[a]) for a in actions if a in labels]
    print("  ".join(parts))


def print_result_summary(player: Player, net_results: List[tuple]):
    """
    net_results: list of (hand_label, outcome_str, net_amount)
    """
    print(f"\n  {bold(DIVIDER)}")
    print(f"  {bold('ROUND RESULTS')}")
    print(f"  {DIVIDER}")
    for label, outcome, net in net_results:
        sign = "+" if net >= 0 else ""
        colour = green if net > 0 else (yellow if net == 0 else red)
        print(f"  {label:<12}  {outcome_label(outcome):<20}  {colour(f'{sign}${net:,.2f}')}")
    print(f"  {DIVIDER}")
    print(f"  Balance: {green(f'${player.balance:,.2f}')}")
    print(f"  {bold(DIVIDER)}\n")


def print_side_bet_results(results: list):
    if not results:
        return
    print(f"  {bold('Side Bets:')}")
    for name, won, wager, amount in results:
        if won:
            print(f"    {cyan(name):<40}  {green(f'+${amount:,.2f}')}")
        else:
            print(f"    {dim(name):<40}  {red(f'-${wager:,.2f}')}")


def print_message(msg: str):
    print(f"\n  {msg}\n")


def print_divider():
    print(f"  {DIVIDER}")


def print_welcome():
    clear()
    print(bold(THICK_DIV))
    print(bold("        WELCOME TO BLACKJACK CHALLENGE        "))
    print(bold("              The Star Sydney                 "))
    print(bold(THICK_DIV))
    print()

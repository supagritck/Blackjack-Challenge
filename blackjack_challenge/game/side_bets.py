"""
Side bet evaluation. All side bets are resolved immediately after the initial
2 cards are dealt to the player (before any player actions).
Each evaluator returns (won: bool, label: str, payout_multiplier: Decimal).
"""
from decimal import Decimal
from typing import Optional

from blackjack_challenge.models.hand import PlayerHand, DealerHand
from blackjack_challenge.models.card import Card
from blackjack_challenge.config import (
    PAYOUT_STAR_MIXED, PAYOUT_STAR_SAME_COLOUR, PAYOUT_STAR_SUITED, PAYOUT_STAR_PAIR_OF_ACES,
    BLAZING_7S_PAYOUTS, BLAZING_7S_JACKPOT_MIN,
)


# ── Star Pairs ─────────────────────────────────────────────────────────────────

def evaluate_star_pairs(hand: PlayerHand) -> tuple[bool, str, Decimal]:
    c1, c2 = hand.cards[0], hand.cards[1]

    # Pair of Aces (highest priority)
    if c1.is_ace and c2.is_ace:
        return True, "Pair of Aces", PAYOUT_STAR_PAIR_OF_ACES

    if c1.rank != c2.rank:
        return False, "No Pair", Decimal("0")

    if c1.suit == c2.suit:
        return True, "Suited Pair", PAYOUT_STAR_SUITED

    if c1.colour == c2.colour:
        return True, "Same Colour Pair", PAYOUT_STAR_SAME_COLOUR

    return True, "Mixed Pair", PAYOUT_STAR_MIXED


# ── Blazing 7s ─────────────────────────────────────────────────────────────────

def evaluate_blazing_7s(
    hand: PlayerHand,
    dealer_hand: DealerHand,
    jackpot_pool: Decimal = BLAZING_7S_JACKPOT_MIN,
) -> tuple[bool, str, Decimal]:
    """
    Evaluates based on player's first two cards and dealer's first face-up card.
    Returns (won, label, cash_payout).
    """
    p1 = hand.cards[0]
    p2 = hand.cards[1]
    dealer_up = _dealer_up_card(dealer_hand)

    p1_is_7 = p1.rank.value == "7"
    p2_is_7 = p2.rank.value == "7"
    d_is_7  = dealer_up is not None and dealer_up.rank.value == "7"

    if p1_is_7 and p2_is_7 and d_is_7:
        # Three 7s — determine tier
        suits = {p1.suit, p2.suit, dealer_up.suit}
        colours = {p1.colour, p2.colour, dealer_up.colour}

        if p1.suit == p2.suit == dealer_up.suit:
            from blackjack_challenge.models.card import Suit
            if p1.suit.value == "Diamonds":
                payout = jackpot_pool * BLAZING_7S_PAYOUTS["three_7s_of_diamonds_jackpot"]
                return True, "Three 7s of Diamonds (JACKPOT!)", payout
            else:
                payout = jackpot_pool * BLAZING_7S_PAYOUTS["three_suited_sevens_jackpot"]
                return True, "Three Suited Sevens (Jackpot)", payout

        if len(colours) == 1:
            return True, "Three Coloured Sevens", BLAZING_7S_PAYOUTS["three_coloured_sevens"]

        return True, "Three Sevens", BLAZING_7S_PAYOUTS["three_sevens"]

    if p1_is_7 and p2_is_7:
        return True, "Two Player Sevens", BLAZING_7S_PAYOUTS["two_player_sevens"]

    if (p1_is_7 or p2_is_7) and d_is_7:
        return True, "One Player Seven & One Dealer 7", BLAZING_7S_PAYOUTS["one_player_seven_one_dealer"]

    return False, "No Sevens", Decimal("0")


def _dealer_up_card(dealer_hand: DealerHand) -> Optional[Card]:
    face_up = [c for c in dealer_hand.cards if c.face_up]
    return face_up[0] if face_up else None


# ── Dispatcher ─────────────────────────────────────────────────────────────────

def evaluate_all_side_bets(
    hand: PlayerHand,
    dealer_hand: DealerHand,
    jackpot_pool: Decimal = BLAZING_7S_JACKPOT_MIN,
) -> list[tuple[str, bool, Decimal, Decimal]]:
    """
    Evaluate all side bets placed on the hand.
    Returns list of (bet_name, won, wager, multiplier_or_cash).
    For Blazing 7s, the multiplier field holds the flat cash payout instead.
    """
    results = []
    bets = hand.side_bets

    if "star_pairs" in bets:
        won, label, mult = evaluate_star_pairs(hand)
        results.append((f"Star Pairs [{label}]", won, bets["star_pairs"], mult))

    if "blazing_7s" in bets:
        won, label, cash = evaluate_blazing_7s(hand, dealer_hand, jackpot_pool)
        # For Blazing 7s we store cash payout directly as multiplier=0, handle separately
        results.append((f"Blazing 7s [{label}]", won, bets["blazing_7s"], cash))

    return results

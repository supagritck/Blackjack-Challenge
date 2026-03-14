"""
Pure adjudication functions — no side effects, no I/O.
All payout multipliers returned are the PROFIT multiplier (not including stake return).
e.g. 2 means player wins 2x their wager as profit, and also gets stake back.
"""
from decimal import Decimal

from blackjack_challenge.models.hand import PlayerHand, DealerHand
from blackjack_challenge.config import (
    PAYOUT_BJ_NO_DEALER_BJ,
    PAYOUT_BJ_VS_BJ_LOWER_RANK,
    PAYOUT_BJ_VS_BJ_SAME_RANK,
    PAYOUT_BJ_VS_BJ_HIGHER_RANK,
    PAYOUT_EVEN_MONEY,
)

# Outcome constants
OUTCOME_WIN_BJ       = "BLACKJACK"
OUTCOME_WIN_FCT      = "FIVE CARD TRICK"
OUTCOME_WIN_21       = "21 - AUTO WIN"
OUTCOME_WIN          = "WIN"
OUTCOME_LOSE         = "LOSE"
# No PUSH — equal totals = player loses per rules


def get_bj_payout(player_hand: PlayerHand, dealer_hand: DealerHand) -> Decimal:
    """
    Returns profit multiplier for a player Blackjack.
    Requires dealer's full hand to be known.
    """
    if not dealer_hand.is_blackjack():
        return PAYOUT_BJ_NO_DEALER_BJ  # 2:1

    # Both have Blackjack — compare 10-value card ranks
    player_ten = _get_ten_card_rank(player_hand)
    dealer_ten = _get_ten_card_rank(dealer_hand)

    if dealer_ten < player_ten:
        return PAYOUT_BJ_VS_BJ_LOWER_RANK   # 5:1
    elif dealer_ten == player_ten:
        return PAYOUT_BJ_VS_BJ_SAME_RANK    # 4:1
    else:
        return PAYOUT_BJ_VS_BJ_HIGHER_RANK  # 3:1


def _get_ten_card_rank(hand) -> int:
    """Find the ten_card_rank of the 10-value card in a BJ hand."""
    for card in hand.cards:
        if card.is_ten_value:
            return card.rank.ten_card_rank
    return 0


def resolve_hand(player_hand: PlayerHand, dealer_hand: DealerHand) -> tuple[str, Decimal]:
    """
    Resolve a completed player hand against the dealer.
    Returns (outcome_label, profit_multiplier).

    Profit multiplier semantics:
      -1 = lose wager
       0 = (not used here; auto-wins handled in engine Phase 3)
       1 = even money (win 1x wager as profit + get stake back)
       n = win n:1
    """
    # Auto-wins are already marked complete by engine; settle them here
    if player_hand.outcome == OUTCOME_WIN_FCT:
        return OUTCOME_WIN_FCT, PAYOUT_EVEN_MONEY

    if player_hand.outcome == OUTCOME_WIN_21:
        return OUTCOME_WIN_21, PAYOUT_EVEN_MONEY

    if player_hand.outcome == OUTCOME_WIN_BJ:
        multiplier = get_bj_payout(player_hand, dealer_hand)
        return OUTCOME_WIN_BJ, multiplier

    # Player busted
    if player_hand.is_bust():
        return OUTCOME_LOSE, Decimal("-1")

    player_total = player_hand.total()
    dealer_total = dealer_hand.total()
    dealer_busted = dealer_hand.is_bust()

    if dealer_busted:
        return OUTCOME_WIN, PAYOUT_EVEN_MONEY

    # Player total <= dealer total → player loses (no push rule)
    if player_total <= dealer_total:
        return OUTCOME_LOSE, Decimal("-1")

    # Player total > dealer total
    return OUTCOME_WIN, PAYOUT_EVEN_MONEY


def dealer_bj_extra_wager_refund(player_hand: PlayerHand) -> Decimal:
    """
    When dealer has Blackjack and player has NOT achieved 21/BJ/FCT,
    only the original wager is collected. Any extra from splits/doubles
    is refunded.
    Returns the refund amount (0 if no extra wagers).
    """
    return max(Decimal("0"), player_hand.wager - player_hand.original_wager)

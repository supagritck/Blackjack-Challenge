"""
Calculates the net balance change for a player hand after settlement.
Positive = player gains chips. Negative = player loses chips.
Wager is deducted at bet placement, so winning returns stake + profit.
"""
from decimal import Decimal

from blackjack_challenge.models.hand import PlayerHand, DealerHand
from blackjack_challenge.models.player import Player
from blackjack_challenge.game.rules import (
    resolve_hand,
    dealer_bj_extra_wager_refund,
    OUTCOME_LOSE,
)


def settle_hand(player: Player, player_hand: PlayerHand, dealer_hand: DealerHand) -> Decimal:
    """
    Determine outcome, calculate net gain/loss, update player balance.
    Returns the net amount added to balance (negative if lost).
    """
    dealer_has_bj = dealer_hand.is_blackjack()
    player_achieved_21 = (
        player_hand.outcome in ("BLACKJACK", "21 - AUTO WIN", "FIVE CARD TRICK")
        or player_hand.total() == 21
    )

    # Dealer Blackjack special case: only original wager collected on split/doubled hands
    if dealer_has_bj and not player_achieved_21:
        refund = dealer_bj_extra_wager_refund(player_hand)
        if refund > 0:
            player.add_winnings(refund)
        # Player loses only original wager (already deducted at bet time)
        player_hand.outcome = "LOSE"
        return -player_hand.original_wager

    outcome, multiplier = resolve_hand(player_hand, dealer_hand)
    player_hand.outcome = outcome

    if multiplier < 0:
        # Lose — wager already deducted, nothing returned
        return -player_hand.wager
    else:
        # Win or auto-win: return stake + profit
        net = player_hand.wager + (player_hand.wager * multiplier)
        player.add_winnings(net)
        return net - player_hand.wager  # net profit shown to user


def settle_side_bets(player: Player, player_hand: PlayerHand, side_bet_results: list) -> Decimal:
    """
    Apply side bet payouts.
    side_bet_results: list of (bet_name, won: bool, wager: Decimal, multiplier: Decimal)
    Returns total net from side bets.
    """
    total = Decimal("0")
    for bet_name, won, wager, multiplier in side_bet_results:
        if won:
            payout = wager + (wager * multiplier)
            player.add_winnings(payout)
            total += wager * multiplier
        else:
            total -= wager
    return total

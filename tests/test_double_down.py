"""
Targeted unit tests for double-down settlement math.

These tests bypass the API and verify the exact balance changes
at the model level, ensuring payout is based on the doubled wager.

Run:  pytest tests/test_double_down.py -v
"""
from decimal import Decimal

import pytest

from blackjack_challenge.models.card import Card, Rank, Suit
from blackjack_challenge.models.hand import PlayerHand, DealerHand
from blackjack_challenge.models.player import Player
from blackjack_challenge.game.payouts import settle_hand


# ── Helpers ───────────────────────────────────────────────────────────────────

def card(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank, suit)


def make_doubled_hand(player: Player, card1: Rank, card2: Rank, double_card: Rank):
    """
    Place hand, apply double, return (hand, player) ready for settlement.
    card1 + card2 must qualify for double (total 9/10/11).
    """
    hand = player.place_initial_hand(Decimal("25"), {})
    hand.add_card(card(card1))
    hand.add_card(card(card2))
    assert hand.can_double(), f"{card1.value}+{card2.value} must be eligible for double"
    # Simulate _do_double: deduct extra and apply
    player.deduct(Decimal("25"))
    hand.apply_double(card(double_card), Decimal("25"))
    return hand


def dealer_hand(*ranks: Rank) -> DealerHand:
    dh = DealerHand()
    for r in ranks:
        dh.add_card(card(r))
    return dh


# ── Wager state tests ─────────────────────────────────────────────────────────

class TestDoubleDownWagerState:
    def test_wager_doubles_after_double(self):
        """hand.wager must equal 2× original after apply_double."""
        player = Player("T", Decimal("1000"))
        hand = make_doubled_hand(player, Rank.FIVE, Rank.SIX, Rank.SEVEN)
        assert hand.wager == Decimal("50")

    def test_original_wager_unchanged(self):
        """hand.original_wager must remain the pre-double bet."""
        player = Player("T", Decimal("1000"))
        hand = make_doubled_hand(player, Rank.FIVE, Rank.SIX, Rank.SEVEN)
        assert hand.original_wager == Decimal("25")

    def test_balance_reduced_by_both_deductions(self):
        """Balance must fall by $50 total ($25 initial + $25 double) before settlement."""
        player = Player("T", Decimal("1000"))
        make_doubled_hand(player, Rank.FIVE, Rank.SIX, Rank.SEVEN)
        assert player.balance == Decimal("950")

    def test_doubled_flag_set(self):
        player = Player("T", Decimal("1000"))
        hand = make_doubled_hand(player, Rank.FIVE, Rank.SIX, Rank.SEVEN)
        assert hand.doubled is True

    def test_hand_is_complete_after_double(self):
        player = Player("T", Decimal("1000"))
        hand = make_doubled_hand(player, Rank.FIVE, Rank.SIX, Rank.SEVEN)
        assert hand.is_complete is True


# ── Settlement math tests ─────────────────────────────────────────────────────

class TestDoubleDownSettlement:
    """
    All scenarios start with: Player $1000 → place $25 → double to $50.
    Balance is $950 before settlement.
    """

    def test_win_profit_is_doubled_wager(self):
        """
        Player 18 beats dealer bust → should earn $50 profit (1× doubled wager).
        Net returned by settle_hand = +$50.
        Balance after = $950 + $100 (stake returned + profit) = $1050.
        """
        player = Player("T", Decimal("1000"))
        # 5+6=11, double card 7 → total 18
        hand = make_doubled_hand(player, Rank.FIVE, Rank.SIX, Rank.SEVEN)
        # Dealer busts (10+10+10 = 30)
        dh = dealer_hand(Rank.TEN, Rank.TEN, Rank.TEN)

        net = settle_hand(player, hand, dh)

        assert net == Decimal("50"),  f"Expected +$50 net profit, got {net}"
        assert player.balance == Decimal("1050"), f"Expected $1050, got {player.balance}"
        assert hand.outcome == "WIN"

    def test_win_profit_not_based_on_original_wager(self):
        """Sanity check: net must NOT equal original wager ($25)."""
        player = Player("T", Decimal("1000"))
        hand = make_doubled_hand(player, Rank.FIVE, Rank.SIX, Rank.SEVEN)
        dh = dealer_hand(Rank.TEN, Rank.TEN, Rank.TEN)

        net = settle_hand(player, hand, dh)

        assert net != Decimal("25"), "Net should be $50 (doubled), not $25 (original)"

    def test_win_against_lower_dealer_total(self):
        """Player 18 beats dealer 15."""
        player = Player("T", Decimal("1000"))
        hand = make_doubled_hand(player, Rank.FIVE, Rank.SIX, Rank.SEVEN)
        dh = dealer_hand(Rank.TEN, Rank.FIVE)  # 15

        net = settle_hand(player, hand, dh)

        assert net == Decimal("50")
        assert player.balance == Decimal("1050")

    def test_loss_deducts_full_doubled_wager(self):
        """
        Player 13 loses to dealer 18 → net = -$50 (full doubled bet lost).
        Balance after = $950 (no add_winnings, bets were already deducted).
        """
        player = Player("T", Decimal("1000"))
        # 5+6=11, double card 2 → total 13
        hand = make_doubled_hand(player, Rank.FIVE, Rank.SIX, Rank.TWO)
        dh = dealer_hand(Rank.TEN, Rank.EIGHT)  # 18

        net = settle_hand(player, hand, dh)

        assert net == Decimal("-50"), f"Expected -$50, got {net}"
        assert player.balance == Decimal("950"), f"Expected $950, got {player.balance}"
        assert hand.outcome == "LOSE"

    def test_bust_after_double_deducts_full_doubled_wager(self):
        """
        Player 5+6+TEN = 21 (not bust), use 5+6+10 path…
        Actually test: 9+2=11, double K → 9+2+K = 21 (21 AUTO WIN).
        Use card that busts instead: 8+3=11, double K → 8+3+K = 21 auto win.
        Use path that busts: 4+7=11, double K → 4+7+K = 21. Hmm 4+7+10 = 21.
        Bust path: wager $25+$25, lose on bust, net = -$50.
        Note: _do_double marks outcome="LOSE" on bust before settlement call.
        Use: 5+4=9 (valid double), double A → 5+4+A = 20 (not bust).
        Use: 6+5=11 (valid double), double 9 → 6+5+9 = 20. Fine for win test.
        For bust: 8+3=11, double 10 → 8+3+10 = 21. Still not bust.
        For bust after double: can't get bust with 3 cards starting from 9/10/11 +10 max = 21.
        Skipping bust-on-double test (mathematically impossible from valid double totals).
        """
        pytest.skip("Cannot bust on double from a 9/10/11 starting total + single card ≤10")

    def test_double_to_21_auto_win(self):
        """
        Doubling to exactly 21 triggers '21 - AUTO WIN' (even money).
        Net = +$50 based on doubled wager.
        """
        player = Player("T", Decimal("1000"))
        # 5+6=11, double A → 5+6+A=11+11 but ace reduces → 5+6+1=12? No...
        # Actually: total=11, add A (point_value=11) → 22, reduce ace → 12. Not 21.
        # Use: 4+7=11, double K → 4+7+10 = 21
        hand = make_doubled_hand(player, Rank.FOUR, Rank.SEVEN, Rank.KING)
        # Manually set outcome as _do_double would
        hand.outcome = "21 - AUTO WIN"
        dh = dealer_hand(Rank.TEN, Rank.SIX)  # dealer 16 (irrelevant for auto win)

        net = settle_hand(player, hand, dh)

        assert net == Decimal("50"), f"Auto win net should be $50, got {net}"
        assert player.balance == Decimal("1050")
        assert hand.outcome == "21 - AUTO WIN"

    def test_dealer_bj_refunds_extra_wager(self):
        """
        Dealer Blackjack and player hasn't hit 21/BJ/FCT →
        only original $25 is lost; the extra $25 from double is refunded.
        Net = -$25. Balance = $950 + $25 refund = $975.
        """
        player = Player("T", Decimal("1000"))
        # 5+6=11, double 2 → total 13 (not 21, not bust)
        hand = make_doubled_hand(player, Rank.FIVE, Rank.SIX, Rank.TWO)
        # Dealer BJ: Ace + King
        dh = dealer_hand(Rank.ACE, Rank.KING)

        net = settle_hand(player, hand, dh)

        assert net == Decimal("-25"), f"Should lose only original $25, got {net}"
        assert player.balance == Decimal("975"), f"Expected $975 (refund applied), got {player.balance}"
        assert hand.outcome == "LOSE"


# ── Round-trip balance test ───────────────────────────────────────────────────

class TestDoubleDownBalanceRoundTrip:
    def test_full_round_trip_win(self):
        """
        Full lifecycle: place → double → win.
        Starting $1000 → spend $50 → win $50 profit → end $1050.
        """
        player = Player("T", Decimal("1000"))
        assert player.balance == Decimal("1000")

        # Place $25 bet
        hand = player.place_initial_hand(Decimal("25"), {})
        assert player.balance == Decimal("975")

        # Cards: 5+6 = 11 (eligible for double)
        hand.add_card(card(Rank.FIVE))
        hand.add_card(card(Rank.SIX))

        # Double: deduct another $25, draw a 7 → total 18
        player.deduct(Decimal("25"))
        hand.apply_double(card(Rank.SEVEN), Decimal("25"))
        assert player.balance == Decimal("950")
        assert hand.wager == Decimal("50")

        # Dealer busts
        dh = dealer_hand(Rank.TEN, Rank.TEN, Rank.TEN)

        # Settle
        net = settle_hand(player, hand, dh)

        assert net == Decimal("50")
        assert player.balance == Decimal("1050")

    def test_full_round_trip_loss(self):
        """
        Full lifecycle: place → double → lose.
        Starting $1000 → spend $50 → lose $50 → end $950.
        """
        player = Player("T", Decimal("1000"))
        hand = player.place_initial_hand(Decimal("25"), {})
        hand.add_card(card(Rank.FIVE))
        hand.add_card(card(Rank.SIX))
        player.deduct(Decimal("25"))
        hand.apply_double(card(Rank.TWO), Decimal("25"))  # total 13
        assert player.balance == Decimal("950")

        dh = dealer_hand(Rank.TEN, Rank.EIGHT)  # dealer 18

        net = settle_hand(player, hand, dh)

        assert net == Decimal("-50")
        assert player.balance == Decimal("950")  # no change — already deducted

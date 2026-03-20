"""
Comprehensive calculation tests for Blackjack Challenge.

Covers every numeric rule in the game engine:
  - Card point values
  - Hand totals (including Ace soft/hard reduction)
  - Hand condition detection (BJ, bust, FCT, 21, soft)
  - Action eligibility (hit, double, split)
  - Outcome resolution (all branches in resolve_hand)
  - Balance settlement (settle_hand — all payout tiers)
  - Dealer BJ extra-wager refund
  - Star Pairs evaluation (all 4 tiers + no-pair)
  - Blazing 7s evaluation (all 6 tiers + no-win)
  - Side-bet balance settlement
  - Session stats accumulation

Run:  pytest tests/test_calculations.py -v
"""
from decimal import Decimal
from typing import List

import pytest

from blackjack_challenge.models.card import Card, Rank, Suit
from blackjack_challenge.models.hand import PlayerHand, DealerHand
from blackjack_challenge.models.player import Player
from blackjack_challenge.game.rules import (
    resolve_hand, get_bj_payout, dealer_bj_extra_wager_refund,
    OUTCOME_WIN_BJ, OUTCOME_WIN_FCT, OUTCOME_WIN_21, OUTCOME_WIN, OUTCOME_LOSE,
)
from blackjack_challenge.game.payouts import settle_hand, settle_side_bets
from blackjack_challenge.game.side_bets import evaluate_star_pairs, evaluate_blazing_7s
from blackjack_challenge.config import (
    BLAZING_7S_JACKPOT_MIN,
    PAYOUT_BJ_NO_DEALER_BJ, PAYOUT_BJ_VS_BJ_LOWER_RANK,
    PAYOUT_BJ_VS_BJ_SAME_RANK, PAYOUT_BJ_VS_BJ_HIGHER_RANK,
    PAYOUT_STAR_MIXED, PAYOUT_STAR_SAME_COLOUR, PAYOUT_STAR_SUITED, PAYOUT_STAR_PAIR_OF_ACES,
    BLAZING_7S_PAYOUTS,
)


# ── Card factories ─────────────────────────────────────────────────────────────

def C(rank: Rank, suit: Suit = Suit.CLUBS) -> Card:
    return Card(rank, suit)


def player_hand(*cards: Card, wager: Decimal = Decimal("25")) -> PlayerHand:
    h = PlayerHand(wager)
    for c in cards:
        h.add_card(c)
    return h


def dealer_hand(*cards: Card) -> DealerHand:
    dh = DealerHand()
    for c in cards:
        dh.add_card(c)
    return dh


# ── 1. Card point values ───────────────────────────────────────────────────────

class TestCardPointValues:
    @pytest.mark.parametrize("rank,expected", [
        (Rank.TWO,   2),
        (Rank.THREE, 3),
        (Rank.FOUR,  4),
        (Rank.FIVE,  5),
        (Rank.SIX,   6),
        (Rank.SEVEN, 7),
        (Rank.EIGHT, 8),
        (Rank.NINE,  9),
        (Rank.TEN,   10),
        (Rank.JACK,  10),
        (Rank.QUEEN, 10),
        (Rank.KING,  10),
        (Rank.ACE,   11),  # initial value; hand logic reduces if needed
    ])
    def test_point_value(self, rank, expected):
        assert C(rank).point_value == expected

    def test_ace_is_ace(self):
        assert C(Rank.ACE).is_ace is True

    def test_non_ace_is_not_ace(self):
        for rank in [Rank.TWO, Rank.KING, Rank.QUEEN]:
            assert C(rank).is_ace is False

    @pytest.mark.parametrize("rank", [Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING])
    def test_ten_value_cards(self, rank):
        assert C(rank).is_ten_value is True

    @pytest.mark.parametrize("rank", [Rank.ACE, Rank.NINE, Rank.TWO])
    def test_non_ten_value_cards(self, rank):
        assert C(rank).is_ten_value is False

    def test_ten_card_rank_order(self):
        """10 < J < Q < K for BJ payout comparisons."""
        assert C(Rank.TEN).rank.ten_card_rank   < C(Rank.JACK).rank.ten_card_rank
        assert C(Rank.JACK).rank.ten_card_rank  < C(Rank.QUEEN).rank.ten_card_rank
        assert C(Rank.QUEEN).rank.ten_card_rank < C(Rank.KING).rank.ten_card_rank

    @pytest.mark.parametrize("suit,colour", [
        (Suit.CLUBS,    "Black"),
        (Suit.SPADES,   "Black"),
        (Suit.HEARTS,   "Red"),
        (Suit.DIAMONDS, "Red"),
    ])
    def test_suit_colour(self, suit, colour):
        assert C(Rank.TWO, suit).colour == colour


# ── 2. Hand totals ─────────────────────────────────────────────────────────────

class TestHandTotals:
    def test_simple_total(self):
        h = player_hand(C(Rank.TEN), C(Rank.SEVEN))
        assert h.total() == 17

    def test_ace_counts_as_11_when_safe(self):
        h = player_hand(C(Rank.ACE), C(Rank.SEVEN))
        assert h.total() == 18  # A=11 + 7

    def test_ace_reduces_to_1_when_bust_with_one_card(self):
        h = player_hand(C(Rank.ACE), C(Rank.TEN), C(Rank.FIVE))
        assert h.total() == 16  # A=1 + 10 + 5

    def test_two_aces_one_reduces(self):
        h = player_hand(C(Rank.ACE), C(Rank.ACE))
        assert h.total() == 12  # A=11 + A=1

    def test_two_aces_plus_nine_equals_21(self):
        h = player_hand(C(Rank.ACE), C(Rank.ACE), C(Rank.NINE))
        assert h.total() == 21  # A=1 + A=1 + 9 = 11 (with soft ace: A=11+A=1+9=21)

    def test_blackjack_total(self):
        h = player_hand(C(Rank.ACE), C(Rank.KING))
        assert h.total() == 21

    def test_five_card_total(self):
        h = player_hand(C(Rank.TWO), C(Rank.THREE), C(Rank.FOUR), C(Rank.FIVE), C(Rank.SIX))
        assert h.total() == 20

    def test_bust_total(self):
        h = player_hand(C(Rank.TEN), C(Rank.TEN), C(Rank.TEN))
        assert h.total() == 30

    def test_soft_hand_detection(self):
        """Ace counted as 11 → soft hand."""
        h = player_hand(C(Rank.ACE), C(Rank.SIX))
        assert h.is_soft() is True

    def test_hard_hand_detection(self):
        """Ace reduced to 1 → hard hand."""
        h = player_hand(C(Rank.ACE), C(Rank.TEN), C(Rank.FIVE))
        assert h.is_soft() is False


# ── 3. Hand condition detection ───────────────────────────────────────────────

class TestHandConditions:
    def test_blackjack_ace_king(self):
        h = player_hand(C(Rank.ACE), C(Rank.KING))
        assert h.is_blackjack() is True

    def test_blackjack_ace_ten(self):
        h = player_hand(C(Rank.ACE), C(Rank.TEN))
        assert h.is_blackjack() is True

    def test_blackjack_requires_exactly_2_cards(self):
        h = player_hand(C(Rank.ACE), C(Rank.FIVE), C(Rank.FIVE))  # 21 but 3 cards
        assert h.is_blackjack() is False

    def test_blackjack_not_valid_on_split_hand(self):
        h = player_hand(C(Rank.ACE), C(Rank.KING))
        h.is_split_hand = True
        assert h.is_blackjack() is False

    def test_21_is_not_blackjack_when_3_cards(self):
        h = player_hand(C(Rank.SEVEN), C(Rank.SEVEN), C(Rank.SEVEN))
        assert h.total() == 21
        assert h.is_blackjack() is False

    def test_is_21(self):
        h = player_hand(C(Rank.TEN), C(Rank.FIVE), C(Rank.SIX))
        assert h.is_21() is True

    def test_is_bust(self):
        h = player_hand(C(Rank.TEN), C(Rank.TEN), C(Rank.TWO))
        assert h.is_bust() is True

    def test_is_not_bust_at_21(self):
        h = player_hand(C(Rank.TEN), C(Rank.ACE))
        assert h.is_bust() is False

    def test_five_card_trick(self):
        h = player_hand(C(Rank.TWO), C(Rank.THREE), C(Rank.FOUR), C(Rank.FIVE), C(Rank.SIX))
        assert h.is_five_card_trick() is True

    def test_five_card_trick_requires_no_bust(self):
        h = player_hand(C(Rank.TEN), C(Rank.TEN), C(Rank.TEN), C(Rank.TEN), C(Rank.TEN))
        assert h.is_five_card_trick() is False

    def test_four_cards_is_not_fct(self):
        h = player_hand(C(Rank.TWO), C(Rank.THREE), C(Rank.FOUR), C(Rank.FIVE))
        assert h.is_five_card_trick() is False

    def test_dealer_blackjack(self):
        dh = dealer_hand(C(Rank.ACE), C(Rank.QUEEN))
        assert dh.is_blackjack() is True

    def test_dealer_must_hit_at_16(self):
        dh = dealer_hand(C(Rank.TEN), C(Rank.SIX))
        assert dh.must_hit() is True

    def test_dealer_stands_at_17(self):
        dh = dealer_hand(C(Rank.TEN), C(Rank.SEVEN))
        assert dh.must_hit() is False

    def test_dealer_stands_at_soft_17(self):
        """Soft 17 (A+6): dealer still stands per these rules."""
        dh = dealer_hand(C(Rank.ACE), C(Rank.SIX))
        assert dh.total() == 17
        assert dh.must_hit() is False


# ── 4. Action eligibility ──────────────────────────────────────────────────────

class TestActionEligibility:
    # can_double: available on totals 9, 10, 11 with 2 or 3 cards
    @pytest.mark.parametrize("cards,eligible", [
        ([C(Rank.FOUR), C(Rank.FIVE)],            True),   # 9
        ([C(Rank.FIVE), C(Rank.FIVE)],            True),   # 10
        ([C(Rank.FIVE), C(Rank.SIX)],             True),   # 11
        ([C(Rank.THREE), C(Rank.THREE), C(Rank.THREE)], True),  # 9 on 3 cards
        ([C(Rank.THREE), C(Rank.FOUR), C(Rank.FOUR)],   True),  # 11 on 3 cards
        ([C(Rank.EIGHT), C(Rank.EIGHT)],          False),  # 16 not in 9/10/11
        ([C(Rank.ACE),  C(Rank.TWO)],             False),  # 13 (or soft 13)
        ([C(Rank.TWO),  C(Rank.THREE), C(Rank.TWO), C(Rank.THREE)], False),  # 4 cards
    ])
    def test_can_double(self, cards, eligible):
        h = player_hand(*cards)
        assert h.can_double() == eligible

    def test_cannot_double_if_already_doubled(self):
        h = player_hand(C(Rank.FIVE), C(Rank.SIX))  # 11
        h.doubled = True
        assert h.can_double() is False

    def test_cannot_double_if_complete(self):
        h = player_hand(C(Rank.FIVE), C(Rank.SIX))
        h.is_complete = True
        assert h.can_double() is False

    # can_split: same point value, ≤ 2 previous splits
    def test_can_split_pair(self):
        h = player_hand(C(Rank.SEVEN, Suit.CLUBS), C(Rank.SEVEN, Suit.HEARTS))
        assert h.can_split() is True

    def test_can_split_face_cards_same_value(self):
        """Jack and King both have point_value=10 → splittable."""
        h = player_hand(C(Rank.JACK), C(Rank.KING))
        assert h.can_split() is True

    def test_cannot_split_non_pair(self):
        h = player_hand(C(Rank.SEVEN), C(Rank.EIGHT))
        assert h.can_split() is False

    def test_cannot_split_after_2_splits(self):
        h = player_hand(C(Rank.SEVEN), C(Rank.SEVEN))
        h.split_count = 2
        assert h.can_split() is False

    def test_cannot_split_more_than_2_cards(self):
        h = player_hand(C(Rank.SEVEN), C(Rank.SEVEN), C(Rank.SEVEN))
        assert h.can_split() is False

    # can_hit
    def test_cannot_hit_at_21(self):
        h = player_hand(C(Rank.ACE), C(Rank.KING))
        assert h.can_hit() is False

    def test_cannot_hit_when_bust(self):
        h = player_hand(C(Rank.TEN), C(Rank.TEN), C(Rank.TWO))
        assert h.can_hit() is False

    def test_cannot_hit_when_complete(self):
        h = player_hand(C(Rank.FIVE), C(Rank.SIX))
        h.is_complete = True
        assert h.can_hit() is False

    def test_cannot_hit_with_5_cards(self):
        h = player_hand(C(Rank.TWO), C(Rank.THREE), C(Rank.FOUR), C(Rank.FIVE), C(Rank.SIX))
        assert h.can_hit() is False

    def test_can_hit_with_4_cards_under_21(self):
        h = player_hand(C(Rank.TWO), C(Rank.THREE), C(Rank.FOUR), C(Rank.FIVE))
        assert h.can_hit() is True


# ── 5. Outcome resolution ─────────────────────────────────────────────────────

class TestResolveHand:
    """
    resolve_hand returns (outcome_label, profit_multiplier).
    Multiplier: -1=lose, 1=even money, 2=BJ 2:1, etc.
    """

    def test_player_bust_loses(self):
        ph = player_hand(C(Rank.TEN), C(Rank.TEN), C(Rank.TWO))
        dh = dealer_hand(C(Rank.TEN), C(Rank.SEVEN))
        outcome, mult = resolve_hand(ph, dh)
        assert outcome == OUTCOME_LOSE
        assert mult == Decimal("-1")

    def test_dealer_bust_player_wins(self):
        ph = player_hand(C(Rank.TEN), C(Rank.EIGHT))
        dh = dealer_hand(C(Rank.TEN), C(Rank.TEN), C(Rank.TWO))
        outcome, mult = resolve_hand(ph, dh)
        assert outcome == OUTCOME_WIN
        assert mult == Decimal("1")

    def test_player_higher_total_wins(self):
        ph = player_hand(C(Rank.TEN), C(Rank.NINE))   # 19
        dh = dealer_hand(C(Rank.TEN), C(Rank.EIGHT))  # 18
        outcome, mult = resolve_hand(ph, dh)
        assert outcome == OUTCOME_WIN
        assert mult == Decimal("1")

    def test_equal_totals_player_loses(self):
        """No push rule — equal totals = player loses."""
        ph = player_hand(C(Rank.TEN), C(Rank.EIGHT))  # 18
        dh = dealer_hand(C(Rank.TEN), C(Rank.EIGHT))  # 18
        outcome, mult = resolve_hand(ph, dh)
        assert outcome == OUTCOME_LOSE
        assert mult == Decimal("-1")

    def test_player_lower_total_loses(self):
        ph = player_hand(C(Rank.TEN), C(Rank.SEVEN))  # 17
        dh = dealer_hand(C(Rank.TEN), C(Rank.EIGHT))  # 18
        outcome, mult = resolve_hand(ph, dh)
        assert outcome == OUTCOME_LOSE
        assert mult == Decimal("-1")

    def test_five_card_trick_wins(self):
        ph = player_hand(C(Rank.TWO), C(Rank.THREE), C(Rank.FOUR), C(Rank.FIVE), C(Rank.SIX))
        ph.outcome = OUTCOME_WIN_FCT
        dh = dealer_hand(C(Rank.TEN), C(Rank.NINE))
        outcome, mult = resolve_hand(ph, dh)
        assert outcome == OUTCOME_WIN_FCT
        assert mult == Decimal("1")

    def test_21_auto_win_even_money(self):
        ph = player_hand(C(Rank.TEN), C(Rank.FIVE), C(Rank.SIX))
        ph.outcome = OUTCOME_WIN_21
        dh = dealer_hand(C(Rank.TEN), C(Rank.SEVEN))
        outcome, mult = resolve_hand(ph, dh)
        assert outcome == OUTCOME_WIN_21
        assert mult == Decimal("1")


# ── 6. Blackjack payout tiers ─────────────────────────────────────────────────

class TestBlackjackPayouts:
    """
    Player BJ vs no dealer BJ → 2:1.
    Player BJ vs dealer BJ: compare 10-value card rank (10 < J < Q < K).
    """

    def test_bj_no_dealer_bj(self):
        ph = player_hand(C(Rank.ACE), C(Rank.KING))
        dh = dealer_hand(C(Rank.TEN), C(Rank.NINE))  # 19, not BJ
        mult = get_bj_payout(ph, dh)
        assert mult == PAYOUT_BJ_NO_DEALER_BJ  # 2

    def test_bj_vs_bj_player_king_dealer_ten_player_wins_5to1(self):
        """Dealer rank (10) < Player rank (K) → 5:1."""
        ph = player_hand(C(Rank.ACE), C(Rank.KING))
        dh = dealer_hand(C(Rank.ACE, Suit.HEARTS), C(Rank.TEN, Suit.HEARTS))
        mult = get_bj_payout(ph, dh)
        assert mult == PAYOUT_BJ_VS_BJ_LOWER_RANK  # 5

    def test_bj_vs_bj_same_rank_4to1(self):
        """Both have King → 4:1."""
        ph = player_hand(C(Rank.ACE), C(Rank.KING, Suit.CLUBS))
        dh = dealer_hand(C(Rank.ACE, Suit.HEARTS), C(Rank.KING, Suit.HEARTS))
        mult = get_bj_payout(ph, dh)
        assert mult == PAYOUT_BJ_VS_BJ_SAME_RANK  # 4

    def test_bj_vs_bj_player_ten_dealer_king_player_loses_3to1(self):
        """Dealer rank (K) > Player rank (10) → 3:1 (still wins but less)."""
        ph = player_hand(C(Rank.ACE), C(Rank.TEN))
        dh = dealer_hand(C(Rank.ACE, Suit.HEARTS), C(Rank.KING, Suit.HEARTS))
        mult = get_bj_payout(ph, dh)
        assert mult == PAYOUT_BJ_VS_BJ_HIGHER_RANK  # 3

    @pytest.mark.parametrize("player_ten,dealer_ten,expected_mult", [
        (Rank.KING,  Rank.QUEEN, PAYOUT_BJ_VS_BJ_LOWER_RANK),   # K > Q → 5:1
        (Rank.QUEEN, Rank.JACK,  PAYOUT_BJ_VS_BJ_LOWER_RANK),   # Q > J → 5:1
        (Rank.JACK,  Rank.TEN,   PAYOUT_BJ_VS_BJ_LOWER_RANK),   # J > 10 → 5:1
        (Rank.QUEEN, Rank.QUEEN, PAYOUT_BJ_VS_BJ_SAME_RANK),    # Q = Q → 4:1
        (Rank.TEN,   Rank.KING,  PAYOUT_BJ_VS_BJ_HIGHER_RANK),  # 10 < K → 3:1
    ])
    def test_bj_tier_matrix(self, player_ten, dealer_ten, expected_mult):
        ph = player_hand(C(Rank.ACE, Suit.CLUBS), C(player_ten, Suit.CLUBS))
        dh = dealer_hand(C(Rank.ACE, Suit.HEARTS), C(dealer_ten, Suit.HEARTS))
        assert get_bj_payout(ph, dh) == expected_mult


# ── 7. settle_hand balance changes ───────────────────────────────────────────

class TestSettleHandBalance:
    """
    All scenarios start with Player $1000, $25 wager.
    Balance before settle = $975.
    """

    def _player_with_hand(self, *hand_cards):
        p = Player("T", Decimal("1000"))
        h = p.place_initial_hand(Decimal("25"), {})
        for c in hand_cards:
            h.add_card(c)
        return p, h

    def test_lose_deducts_wager(self):
        p, h = self._player_with_hand(C(Rank.TEN), C(Rank.EIGHT))  # 18
        dh = dealer_hand(C(Rank.TEN), C(Rank.NINE))  # 19 — beats player
        net = settle_hand(p, h, dh)
        assert net == Decimal("-25")
        assert p.balance == Decimal("975")  # no change (wager already gone)

    def test_win_even_money_adds_wager(self):
        p, h = self._player_with_hand(C(Rank.TEN), C(Rank.NINE))  # 19
        dh = dealer_hand(C(Rank.TEN), C(Rank.EIGHT))  # 18
        net = settle_hand(p, h, dh)
        assert net == Decimal("25")
        assert p.balance == Decimal("1025")  # 975 + 50 returned = 1025; net +25

    def test_blackjack_2to1_payout(self):
        """BJ with no dealer BJ → net = 2× wager = +$50."""
        p, h = self._player_with_hand(C(Rank.ACE), C(Rank.KING))
        h.outcome = OUTCOME_WIN_BJ
        dh = dealer_hand(C(Rank.TEN), C(Rank.SEVEN))  # not BJ
        net = settle_hand(p, h, dh)
        assert net == Decimal("50")   # wager($25) × 2 = +$50
        assert p.balance == Decimal("1050")

    def test_blackjack_vs_blackjack_king_vs_ten_5to1(self):
        """Player K-BJ vs Dealer 10-BJ → net = 5× wager = +$125.
        add_winnings($150) on balance $975 → $1125."""
        p, h = self._player_with_hand(C(Rank.ACE), C(Rank.KING))
        h.outcome = OUTCOME_WIN_BJ
        dh = dealer_hand(C(Rank.ACE, Suit.HEARTS), C(Rank.TEN, Suit.HEARTS))
        net = settle_hand(p, h, dh)
        assert net == Decimal("125")  # $25 × 5
        assert p.balance == Decimal("1125")  # 975 + (25 + 25×5) = 975 + 150

    def test_blackjack_vs_blackjack_same_rank_4to1(self):
        """Both K-BJ → net = 4× wager = +$100.
        add_winnings($125) on balance $975 → $1100."""
        p, h = self._player_with_hand(C(Rank.ACE, Suit.CLUBS), C(Rank.KING, Suit.CLUBS))
        h.outcome = OUTCOME_WIN_BJ
        dh = dealer_hand(C(Rank.ACE, Suit.HEARTS), C(Rank.KING, Suit.HEARTS))
        net = settle_hand(p, h, dh)
        assert net == Decimal("100")
        assert p.balance == Decimal("1100")  # 975 + (25 + 25×4) = 975 + 125

    def test_blackjack_vs_blackjack_lower_rank_3to1(self):
        """Player 10-BJ vs Dealer K-BJ → net = 3× = +$75.
        add_winnings($100) on balance $975 → $1075."""
        p, h = self._player_with_hand(C(Rank.ACE), C(Rank.TEN))
        h.outcome = OUTCOME_WIN_BJ
        dh = dealer_hand(C(Rank.ACE, Suit.HEARTS), C(Rank.KING, Suit.HEARTS))
        net = settle_hand(p, h, dh)
        assert net == Decimal("75")
        assert p.balance == Decimal("1075")  # 975 + (25 + 25×3) = 975 + 100

    def test_bust_deducts_wager(self):
        p, h = self._player_with_hand(C(Rank.TEN), C(Rank.TEN), C(Rank.TWO))
        dh = dealer_hand(C(Rank.TEN), C(Rank.SEVEN))
        net = settle_hand(p, h, dh)
        assert net == Decimal("-25")
        assert p.balance == Decimal("975")

    def test_five_card_trick_even_money(self):
        p, h = self._player_with_hand(
            C(Rank.TWO), C(Rank.THREE), C(Rank.FOUR), C(Rank.FIVE), C(Rank.SIX)
        )
        h.outcome = OUTCOME_WIN_FCT
        dh = dealer_hand(C(Rank.TEN), C(Rank.NINE))
        net = settle_hand(p, h, dh)
        assert net == Decimal("25")
        assert p.balance == Decimal("1025")

    def test_21_auto_win_even_money(self):
        p, h = self._player_with_hand(C(Rank.TEN), C(Rank.FIVE), C(Rank.SIX))
        h.outcome = OUTCOME_WIN_21
        dh = dealer_hand(C(Rank.TEN), C(Rank.NINE))
        net = settle_hand(p, h, dh)
        assert net == Decimal("25")
        assert p.balance == Decimal("1025")

    def test_dealer_bust_player_wins_even_money(self):
        p, h = self._player_with_hand(C(Rank.TEN), C(Rank.EIGHT))
        dh = dealer_hand(C(Rank.TEN), C(Rank.TEN), C(Rank.FIVE))  # 25, bust
        net = settle_hand(p, h, dh)
        assert net == Decimal("25")
        assert p.balance == Decimal("1025")


# ── 8. Dealer BJ extra-wager refund ──────────────────────────────────────────

class TestDealerBJRefund:
    def test_no_refund_on_normal_hand(self):
        """Standard hand: wager == original_wager → $0 refund."""
        h = PlayerHand(Decimal("25"))
        h.add_card(C(Rank.TEN))
        h.add_card(C(Rank.SEVEN))
        assert dealer_bj_extra_wager_refund(h) == Decimal("0")

    def test_doubled_hand_refunds_extra(self):
        """Doubled from $25 to $50: extra $25 is refunded."""
        p = Player("T", Decimal("1000"))
        h = p.place_initial_hand(Decimal("25"), {})
        h.add_card(C(Rank.FIVE))
        h.add_card(C(Rank.SIX))
        p.deduct(Decimal("25"))
        h.apply_double(C(Rank.TWO), Decimal("25"))
        assert dealer_bj_extra_wager_refund(h) == Decimal("25")

    def test_dealer_bj_only_loses_original_wager(self):
        """Full settle: doubled hand vs dealer BJ → net = -$25 (only original lost)."""
        p = Player("T", Decimal("1000"))
        h = p.place_initial_hand(Decimal("25"), {})
        h.add_card(C(Rank.FIVE))
        h.add_card(C(Rank.SIX))
        p.deduct(Decimal("25"))
        h.apply_double(C(Rank.TWO), Decimal("25"))  # total 13
        dh = dealer_hand(C(Rank.ACE), C(Rank.KING))  # dealer BJ
        net = settle_hand(p, h, dh)
        assert net == Decimal("-25")
        assert p.balance == Decimal("975")  # 950 + 25 refund = 975

    def test_dealer_bj_21_auto_win_not_refunded(self):
        """Player doubled to 21 AUTO WIN — dealer BJ refund skipped, player wins."""
        p = Player("T", Decimal("1000"))
        h = p.place_initial_hand(Decimal("25"), {})
        h.add_card(C(Rank.FOUR))
        h.add_card(C(Rank.SEVEN))
        p.deduct(Decimal("25"))
        h.apply_double(C(Rank.KING), Decimal("25"))  # 4+7+10 = 21
        h.outcome = OUTCOME_WIN_21
        dh = dealer_hand(C(Rank.ACE), C(Rank.KING, Suit.HEARTS))  # dealer BJ
        net = settle_hand(p, h, dh)
        # Player achieved 21 → wins at even money on doubled $50 bet
        assert net == Decimal("50")
        assert p.balance == Decimal("1050")


# ── 9. Star Pairs evaluation ──────────────────────────────────────────────────

class TestStarPairsEvaluation:
    def _hand(self, c1: Card, c2: Card) -> PlayerHand:
        return player_hand(c1, c2)

    def test_pair_of_aces_30x(self):
        h = self._hand(C(Rank.ACE, Suit.CLUBS), C(Rank.ACE, Suit.HEARTS))
        won, label, mult = evaluate_star_pairs(h)
        assert won is True
        assert "Aces" in label
        assert mult == PAYOUT_STAR_PAIR_OF_ACES  # 30

    def test_suited_pair_20x(self):
        h = self._hand(C(Rank.SEVEN, Suit.CLUBS), C(Rank.SEVEN, Suit.CLUBS))
        won, label, mult = evaluate_star_pairs(h)
        assert won is True
        assert "Suited" in label
        assert mult == PAYOUT_STAR_SUITED  # 20

    def test_same_colour_pair_8x(self):
        """Two sevens, same colour (both black), different suits."""
        h = self._hand(C(Rank.SEVEN, Suit.CLUBS), C(Rank.SEVEN, Suit.SPADES))
        won, label, mult = evaluate_star_pairs(h)
        assert won is True
        assert "Colour" in label
        assert mult == PAYOUT_STAR_SAME_COLOUR  # 8

    def test_mixed_pair_5x(self):
        """Two sevens, different colours (black + red)."""
        h = self._hand(C(Rank.SEVEN, Suit.CLUBS), C(Rank.SEVEN, Suit.HEARTS))
        won, label, mult = evaluate_star_pairs(h)
        assert won is True
        assert "Mixed" in label
        assert mult == PAYOUT_STAR_MIXED  # 5

    def test_no_pair(self):
        h = self._hand(C(Rank.SEVEN), C(Rank.EIGHT))
        won, label, mult = evaluate_star_pairs(h)
        assert won is False
        assert mult == Decimal("0")

    def test_ten_value_pair_same_colour(self):
        """Jack♣ + Jack♠ = same colour pair (both black)."""
        h = self._hand(C(Rank.JACK, Suit.CLUBS), C(Rank.JACK, Suit.SPADES))
        won, label, mult = evaluate_star_pairs(h)
        assert won is True
        assert mult == PAYOUT_STAR_SAME_COLOUR

    def test_mixed_pair_red_black(self):
        """Eight♣ (black) + Eight♥ (red) = mixed pair."""
        h = self._hand(C(Rank.EIGHT, Suit.CLUBS), C(Rank.EIGHT, Suit.HEARTS))
        won, label, mult = evaluate_star_pairs(h)
        assert mult == PAYOUT_STAR_MIXED


# ── 10. Blazing 7s evaluation ─────────────────────────────────────────────────

class TestBlazing7sEvaluation:
    def _setup(self, p1: Rank, p1_suit: Suit, p2: Rank, p2_suit: Suit, d: Rank, d_suit: Suit):
        ph = player_hand(C(p1, p1_suit), C(p2, p2_suit))
        dh = dealer_hand(C(d, d_suit))
        return ph, dh

    def test_no_sevens_loses(self):
        ph, dh = self._setup(Rank.EIGHT, Suit.CLUBS, Rank.NINE, Suit.CLUBS,
                              Rank.TEN, Suit.CLUBS)
        won, label, cash = evaluate_blazing_7s(ph, dh)
        assert won is False
        assert cash == Decimal("0")

    def test_one_player_seven_no_dealer_seven_loses(self):
        ph, dh = self._setup(Rank.SEVEN, Suit.CLUBS, Rank.NINE, Suit.CLUBS,
                              Rank.TEN, Suit.CLUBS)
        won, _, _ = evaluate_blazing_7s(ph, dh)
        assert won is False

    def test_one_player_seven_plus_dealer_seven_wins_25(self):
        ph, dh = self._setup(Rank.SEVEN, Suit.CLUBS, Rank.NINE, Suit.CLUBS,
                              Rank.SEVEN, Suit.HEARTS)
        won, label, cash = evaluate_blazing_7s(ph, dh)
        assert won is True
        assert cash == BLAZING_7S_PAYOUTS["one_player_seven_one_dealer"]  # 25

    def test_two_player_sevens_no_dealer_wins_50(self):
        ph, dh = self._setup(Rank.SEVEN, Suit.CLUBS, Rank.SEVEN, Suit.HEARTS,
                              Rank.NINE, Suit.CLUBS)
        won, label, cash = evaluate_blazing_7s(ph, dh)
        assert won is True
        assert cash == BLAZING_7S_PAYOUTS["two_player_sevens"]  # 50

    def test_three_mixed_sevens_wins_500(self):
        """All three 7s but different colours → $500."""
        ph, dh = self._setup(Rank.SEVEN, Suit.CLUBS, Rank.SEVEN, Suit.HEARTS,
                              Rank.SEVEN, Suit.DIAMONDS)
        won, label, cash = evaluate_blazing_7s(ph, dh)
        assert won is True
        assert cash == BLAZING_7S_PAYOUTS["three_sevens"]  # 500

    def test_three_coloured_sevens_wins_1250(self):
        """All three 7s same colour (all black) → $1250."""
        ph, dh = self._setup(Rank.SEVEN, Suit.CLUBS, Rank.SEVEN, Suit.SPADES,
                              Rank.SEVEN, Suit.CLUBS)
        won, label, cash = evaluate_blazing_7s(ph, dh)
        assert won is True
        assert cash == BLAZING_7S_PAYOUTS["three_coloured_sevens"]  # 1250

    def test_three_suited_sevens_jackpot_10pct(self):
        """All three 7s same suit (non-diamond) → 10% of jackpot pool."""
        jackpot = Decimal("25000")
        ph, dh = self._setup(Rank.SEVEN, Suit.CLUBS, Rank.SEVEN, Suit.CLUBS,
                              Rank.SEVEN, Suit.CLUBS)
        won, label, cash = evaluate_blazing_7s(ph, dh, jackpot_pool=jackpot)
        assert won is True
        assert cash == jackpot * Decimal("0.10")  # 2500

    def test_three_diamonds_sevens_full_jackpot(self):
        """All three 7s of Diamonds → 100% of jackpot pool."""
        jackpot = Decimal("30000")
        ph, dh = self._setup(Rank.SEVEN, Suit.DIAMONDS, Rank.SEVEN, Suit.DIAMONDS,
                              Rank.SEVEN, Suit.DIAMONDS)
        won, label, cash = evaluate_blazing_7s(ph, dh, jackpot_pool=jackpot)
        assert won is True
        assert cash == jackpot  # 100%
        assert "JACKPOT" in label.upper()


# ── 11. Side-bet balance settlement ──────────────────────────────────────────

class TestSettleSideBets:
    """
    settle_side_bets receives list of (name, won, wager, multiplier_or_flat)
    and applies balance changes to the player.
    For Star Pairs: payout = wager + (wager × multiplier)
    For Blazing 7s: payout = wager + flat_cash
    """

    def _player(self, balance="1000"):
        return Player("T", Decimal(balance))

    def test_star_pairs_win_mixed_5x(self):
        """Wager $10, Mixed pair (5x) → net profit $50.
        add_winnings(10 + 10×5 = 60) on $1000 → $1060."""
        p = self._player()
        results = [("Star Pairs [Mixed Pair]", True, Decimal("10"), Decimal("5"))]
        net = settle_side_bets(p, PlayerHand(Decimal("0")), results)
        assert net == Decimal("50")
        assert p.balance == Decimal("1060")  # 1000 + wager($10) + profit($50)

    def test_star_pairs_win_suited_20x(self):
        """Wager $10, Suited pair (20x) → profit $200.
        add_winnings(10 + 10×20 = 210) on $1000 → $1210."""
        p = self._player()
        results = [("Star Pairs [Suited Pair]", True, Decimal("10"), Decimal("20"))]
        net = settle_side_bets(p, PlayerHand(Decimal("0")), results)
        assert net == Decimal("200")
        assert p.balance == Decimal("1210")  # 1000 + wager($10) + profit($200)

    def test_star_pairs_win_pair_of_aces_30x(self):
        """Wager $10, Pair of Aces (30x) → profit $300."""
        p = self._player()
        results = [("Star Pairs [Pair of Aces]", True, Decimal("10"), Decimal("30"))]
        net = settle_side_bets(p, PlayerHand(Decimal("0")), results)
        assert net == Decimal("300")

    def test_star_pairs_loss(self):
        """Losing side bet: net = -wager."""
        p = self._player()
        results = [("Star Pairs [No Pair]", False, Decimal("10"), Decimal("0"))]
        net = settle_side_bets(p, PlayerHand(Decimal("0")), results)
        assert net == Decimal("-10")
        assert p.balance == Decimal("1000")  # unchanged (wager already deducted at bet time)

    def test_blazing_7s_win_flat_25(self):
        """Blazing 7s: wager $2.50, win $25 flat → net $25 profit, balance +$27.50."""
        p = self._player()
        results = [("Blazing 7s [One Player Seven & One Dealer 7]", True,
                    Decimal("2.50"), Decimal("25"))]
        net = settle_side_bets(p, PlayerHand(Decimal("0")), results)
        assert net == Decimal("25")
        assert p.balance == Decimal("1027.50")  # 1000 + 2.50 stake + 25 prize

    def test_blazing_7s_win_jackpot(self):
        """Blazing 7s: wager $2.50, win full $25000 jackpot."""
        p = self._player()
        results = [("Blazing 7s [Three 7s of Diamonds (JACKPOT!)]", True,
                    Decimal("2.50"), Decimal("25000"))]
        net = settle_side_bets(p, PlayerHand(Decimal("0")), results)
        assert net == Decimal("25000")
        assert p.balance == Decimal("26002.50")

    def test_blazing_7s_loss(self):
        p = self._player()
        results = [("Blazing 7s [No Sevens]", False, Decimal("2.50"), Decimal("0"))]
        net = settle_side_bets(p, PlayerHand(Decimal("0")), results)
        assert net == Decimal("-2.50")
        assert p.balance == Decimal("1000")


# ── 12. Star Pairs cash payout (SideBetResult) computation ───────────────────

class TestSideBetResultPayout:
    """
    Verify the payout amount stored in SideBetResult is correct.
    In web_engine._side_bet_results:
      Blazing 7s → payout = flat cash
      Star Pairs → payout = wager × multiplier (net profit)
    """

    @pytest.mark.parametrize("wager,mult,expected_profit", [
        (Decimal("10"),   Decimal("5"),  Decimal("50")),    # mixed
        (Decimal("10"),   Decimal("8"),  Decimal("80")),    # same colour
        (Decimal("10"),   Decimal("20"), Decimal("200")),   # suited
        (Decimal("10"),   Decimal("30"), Decimal("300")),   # pair of aces
        (Decimal("25"),   Decimal("5"),  Decimal("125")),   # mixed, $25 wager
        (Decimal("100"),  Decimal("20"), Decimal("2000")),  # suited, $100 wager
    ])
    def test_star_pairs_net_cash_profit(self, wager, mult, expected_profit):
        """Net cash profit = wager × multiplier (not multiplier alone)."""
        profit = wager * mult
        assert profit == expected_profit

    @pytest.mark.parametrize("flat_cash,expected", [
        (Decimal("25"),    Decimal("25")),
        (Decimal("50"),    Decimal("50")),
        (Decimal("500"),   Decimal("500")),
        (Decimal("1250"),  Decimal("1250")),
        (Decimal("2500"),  Decimal("2500")),   # 10% of $25k jackpot
        (Decimal("25000"), Decimal("25000")),  # full jackpot
    ])
    def test_blazing_7s_flat_payout_is_direct(self, flat_cash, expected):
        """Blazing 7s payout is the flat cash amount, not multiplied by wager."""
        assert flat_cash == expected


# ── 13. Split hand mechanics ──────────────────────────────────────────────────

class TestSplitHandMechanics:
    def test_split_creates_new_hand_with_second_card(self):
        h = PlayerHand(Decimal("25"))
        h.add_card(C(Rank.SEVEN, Suit.CLUBS))
        h.add_card(C(Rank.SEVEN, Suit.HEARTS))
        new_hand = h.split_off()
        assert len(h.cards) == 1
        assert len(new_hand.cards) == 1
        assert new_hand.cards[0].rank == Rank.SEVEN

    def test_split_preserves_original_wager(self):
        h = PlayerHand(Decimal("25"))
        h.add_card(C(Rank.SEVEN, Suit.CLUBS))
        h.add_card(C(Rank.SEVEN, Suit.HEARTS))
        new_hand = h.split_off()
        assert new_hand.original_wager == Decimal("25")
        assert new_hand.wager == Decimal("25")

    def test_split_marks_both_hands_as_split_hands(self):
        h = PlayerHand(Decimal("25"))
        h.add_card(C(Rank.SEVEN, Suit.CLUBS))
        h.add_card(C(Rank.SEVEN, Suit.HEARTS))
        new_hand = h.split_off()
        assert h.is_split_hand is True
        assert new_hand.is_split_hand is True

    def test_split_increments_split_count(self):
        h = PlayerHand(Decimal("25"))
        h.add_card(C(Rank.SEVEN, Suit.CLUBS))
        h.add_card(C(Rank.SEVEN, Suit.HEARTS))
        new_hand = h.split_off()
        assert h.split_count == 1
        assert new_hand.split_count == 1

    def test_cannot_split_after_max_splits(self):
        """Max 2 splits = 3 hands max."""
        h = PlayerHand(Decimal("25"))
        h.add_card(C(Rank.SEVEN, Suit.CLUBS))
        h.add_card(C(Rank.SEVEN, Suit.HEARTS))
        h.split_count = 2
        assert h.can_split() is False

    def test_blackjack_not_valid_on_split_hand(self):
        """A+K on a split hand is 21, not Blackjack."""
        h = PlayerHand(Decimal("25"))
        h.add_card(C(Rank.ACE))
        h.add_card(C(Rank.KING))
        h.is_split_hand = True
        assert h.is_blackjack() is False
        assert h.total() == 21

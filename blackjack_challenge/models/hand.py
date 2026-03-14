from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING

from blackjack_challenge.models.card import Card

if TYPE_CHECKING:
    pass


class Hand:
    def __init__(self):
        self.cards: List[Card] = []

    def add_card(self, card: Card):
        self.cards.append(card)

    def total(self) -> int:
        """Optimal total: counts Aces as 11, reduces to 1 while bust."""
        total = sum(c.point_value for c in self.cards)
        aces = sum(1 for c in self.cards if c.is_ace)
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total

    def is_soft(self) -> bool:
        """True if at least one Ace is being counted as 11."""
        total = sum(c.point_value for c in self.cards)
        aces = sum(1 for c in self.cards if c.is_ace)
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return aces > 0

    def is_bust(self) -> bool:
        return self.total() > 21

    def card_count(self) -> int:
        return len(self.cards)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({[str(c) for c in self.cards]}, total={self.total()})"


class PlayerHand(Hand):
    def __init__(self, wager: Decimal, original_wager: Optional[Decimal] = None):
        super().__init__()
        self.wager = wager
        self.original_wager = original_wager if original_wager is not None else wager
        self.doubled = False
        self.split_count: int = 0        # how many times this lineage has been split
        self.is_split_hand: bool = False  # was this hand created from a split?
        self.is_complete: bool = False
        self.outcome: Optional[str] = None  # set during settlement

        # Side bet wagers: {bet_name: amount}
        self.side_bets: dict = {}

    # ── Immediate win conditions ──────────────────────────────────────────────

    def is_blackjack(self) -> bool:
        """Ace + 10-value card on initial 2 cards. Not valid on split hands."""
        if self.is_split_hand:
            return False
        if len(self.cards) != 2:
            return False
        has_ace = any(c.is_ace for c in self.cards)
        has_ten = any(c.is_ten_value for c in self.cards)
        return has_ace and has_ten

    def is_five_card_trick(self) -> bool:
        """5 cards without busting — auto-win."""
        return len(self.cards) == 5 and not self.is_bust()

    def is_21(self) -> bool:
        return self.total() == 21

    # ── Action eligibility ────────────────────────────────────────────────────

    def can_hit(self) -> bool:
        if self.is_complete:
            return False
        if self.is_bust():
            return False
        if self.is_21():
            return False
        if self.is_five_card_trick():
            return False
        if len(self.cards) >= 5:
            return False
        return True

    def can_split(self) -> bool:
        if len(self.cards) != 2:
            return False
        if self.split_count >= 2:
            return False
        return self.cards[0].point_value == self.cards[1].point_value

    def can_double(self) -> bool:
        if self.doubled:
            return False
        if self.is_complete:
            return False
        if len(self.cards) not in (2, 3):
            return False
        return self.total() in (9, 10, 11)

    # ── Actions ───────────────────────────────────────────────────────────────

    def apply_double(self, card: Card, extra_wager: Decimal):
        self.add_card(card)
        self.wager += extra_wager
        self.doubled = True
        self.is_complete = True  # only one card drawn, then hand is done

    def split_off(self) -> "PlayerHand":
        """
        Remove the second card from this hand and return a new PlayerHand
        containing that card. Both hands share the same original_wager.
        """
        second_card = self.cards.pop()
        new_hand = PlayerHand(wager=self.original_wager, original_wager=self.original_wager)
        new_hand.add_card(second_card)
        new_hand.is_split_hand = True
        new_hand.split_count = self.split_count + 1

        self.is_split_hand = True
        self.split_count += 1
        return new_hand

    def mark_complete(self, outcome: str):
        self.is_complete = True
        self.outcome = outcome


class DealerHand(Hand):
    def must_hit(self) -> bool:
        return self.total() <= 16

    def is_blackjack(self) -> bool:
        if len(self.cards) != 2:
            return False
        has_ace = any(c.is_ace for c in self.cards)
        has_ten = any(c.is_ten_value for c in self.cards)
        return has_ace and has_ten

    def visible_cards(self) -> List[Card]:
        return [c for c in self.cards if c.face_up]

    def visible_total(self) -> int:
        """Total using only face-up cards."""
        total = sum(c.point_value for c in self.visible_cards())
        aces = sum(1 for c in self.visible_cards() if c.is_ace)
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total

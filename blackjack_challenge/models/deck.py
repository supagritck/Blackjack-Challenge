import random
from collections import deque
from typing import List

from blackjack_challenge.models.card import Card, Rank, Suit
from blackjack_challenge.config import SHUFFLE_THRESHOLD


def _build_deck() -> List[Card]:
    return [Card(rank, suit) for suit in Suit for rank in Rank]


class Shoe:
    def __init__(self, num_decks: int = 6):
        self.num_decks = num_decks
        self._total_cards = num_decks * 52
        self._cards: deque[Card] = deque()
        self._dealt_count = 0
        self.build()

    def build(self):
        cards = []
        for _ in range(self.num_decks):
            cards.extend(_build_deck())
        random.shuffle(cards)
        self._cards = deque(cards)
        self._dealt_count = 0

    def deal(self) -> Card:
        if not self._cards:
            self.build()
        card = self._cards.popleft()
        card.face_up = True
        self._dealt_count += 1
        return card

    def deal_face_down(self) -> Card:
        card = self.deal()
        card.face_up = False
        return card

    def needs_shuffle(self) -> bool:
        remaining = len(self._cards)
        return remaining / self._total_cards < SHUFFLE_THRESHOLD

    def reshuffle(self):
        self.build()

    @property
    def cards_remaining(self) -> int:
        return len(self._cards)

from decimal import Decimal
from typing import List

from blackjack_challenge.models.hand import PlayerHand, DealerHand
from blackjack_challenge.models.deck import Shoe


class Player:
    def __init__(self, name: str, balance: Decimal):
        self.name = name
        self.balance = balance
        self.hands: List[PlayerHand] = []

    def can_afford(self, amount: Decimal) -> bool:
        return self.balance >= amount

    def deduct(self, amount: Decimal):
        self.balance -= amount

    def add_winnings(self, amount: Decimal):
        self.balance += amount

    def place_initial_hand(self, wager: Decimal, side_bets: dict) -> PlayerHand:
        self.deduct(wager)
        hand = PlayerHand(wager=wager)
        hand.side_bets = side_bets
        self.hands.append(hand)
        return hand

    def reset_hands(self):
        self.hands = []

    def __repr__(self) -> str:
        return f"Player({self.name}, balance=${self.balance:.2f}, hands={len(self.hands)})"


class Dealer:
    def __init__(self):
        self.hand = DealerHand()

    def reset(self):
        self.hand = DealerHand()

    def play_hand(self, shoe: Shoe):
        """Dealer draws until total >= 17."""
        while self.hand.must_hit():
            self.hand.add_card(shoe.deal())

    def is_blackjack(self) -> bool:
        return self.hand.is_blackjack()

    def __repr__(self) -> str:
        return f"Dealer(total={self.hand.total()})"

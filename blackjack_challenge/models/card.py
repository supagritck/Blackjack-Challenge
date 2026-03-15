from enum import Enum


class Suit(Enum):
    CLUBS    = "Clubs"
    DIAMONDS = "Diamonds"
    HEARTS   = "Hearts"
    SPADES   = "Spades"

    @property
    def colour(self) -> str:
        return "Red" if self in (Suit.HEARTS, Suit.DIAMONDS) else "Black"

    @property
    def symbol(self) -> str:
        return {"Clubs": "♣", "Diamonds": "♦", "Hearts": "♥", "Spades": "♠"}[self.value]


class Rank(Enum):
    TWO   = "2"
    THREE = "3"
    FOUR  = "4"
    FIVE  = "5"
    SIX   = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE  = "9"
    TEN   = "10"
    JACK  = "J"
    QUEEN = "Q"
    KING  = "K"
    ACE   = "A"

    @property
    def point_value(self) -> int:
        if self == Rank.ACE:
            return 11  # treated as 11 initially; hand logic reduces when needed
        if self in (Rank.JACK, Rank.QUEEN, Rank.KING):
            return 10
        return int(self.value)

    @property
    def is_ten_value(self) -> bool:
        return self in (Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING)

    @property
    def ten_card_rank(self) -> int:
        """Rank order for Blackjack payout comparison. Only meaningful for 10-value cards."""
        order = {Rank.TEN: 1, Rank.JACK: 2, Rank.QUEEN: 3, Rank.KING: 4}
        return order.get(self, 0)

    @property
    def is_ace(self) -> bool:
        return self == Rank.ACE


class Card:
    def __init__(self, rank: Rank, suit: Suit, face_up: bool = True):
        self.rank = rank
        self.suit = suit
        self.face_up = face_up

    @property
    def point_value(self) -> int:
        return self.rank.point_value

    @property
    def colour(self) -> str:
        return self.suit.colour

    @property
    def is_ace(self) -> bool:
        return self.rank.is_ace

    @property
    def is_ten_value(self) -> bool:
        return self.rank.is_ten_value

    def __eq__(self, other) -> bool:
        if not isinstance(other, Card):
            return False
        return self.rank == other.rank and self.suit == other.suit

    def __hash__(self):
        return hash((self.rank, self.suit))

    def __repr__(self) -> str:
        return f"Card({self.rank.value}{self.suit.symbol})"

    def __str__(self) -> str:
        if not self.face_up:
            return "[####]"
        return f"[{self.rank.value}{self.suit.symbol}]"

    def to_dict(self) -> dict:
        return {
            "rank":        self.rank.value,
            "suit":        self.suit.value,
            "suit_symbol": self.suit.symbol,
            "colour":      self.colour,
            "face_up":     self.face_up,
            "point_value": self.point_value,
        }

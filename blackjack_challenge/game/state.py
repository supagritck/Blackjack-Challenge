"""
Serializable game state schema for the web engine.
GameState is the single data contract between the FastAPI backend and the frontend.
Every public method on WebGameEngine returns a GameState.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class GamePhase(Enum):
    WAITING_FOR_BET = "WAITING_FOR_BET"
    PLAYER_TURN     = "PLAYER_TURN"
    DEALER_TURN     = "DEALER_TURN"
    ROUND_OVER      = "ROUND_OVER"
    GAME_OVER       = "GAME_OVER"


@dataclass
class CardState:
    """Snapshot of a single card. rank/suit/etc. are None when face_up is False."""
    rank:        Optional[str]   # e.g. "A", "K", "10"
    suit:        Optional[str]   # e.g. "Spades"
    suit_symbol: Optional[str]   # e.g. "♠"
    colour:      Optional[str]   # "Red" or "Black"
    face_up:     bool
    point_value: Optional[int]   # None when face-down

    def to_dict(self) -> dict:
        return {
            "rank":        self.rank,
            "suit":        self.suit,
            "suit_symbol": self.suit_symbol,
            "colour":      self.colour,
            "face_up":     self.face_up,
            "point_value": self.point_value,
        }


@dataclass
class HandState:
    """Snapshot of one player hand."""
    cards:          list[CardState]
    total:          int
    wager:          str             # Decimal as string
    doubled:        bool
    is_split_hand:  bool
    is_complete:    bool
    outcome:        Optional[str]   # e.g. "WIN_BJ", "LOSE", "STAND" — None mid-round
    side_bets:      dict            # {bet_name: amount_string}

    def to_dict(self) -> dict:
        return {
            "cards":         [c.to_dict() for c in self.cards],
            "total":         self.total,
            "wager":         self.wager,
            "doubled":       self.doubled,
            "is_split_hand": self.is_split_hand,
            "is_complete":   self.is_complete,
            "outcome":       self.outcome,
            "side_bets":     self.side_bets,
        }


@dataclass
class SideBetResult:
    """Result of one evaluated side bet."""
    name:   str   # e.g. "Star Pairs [Suited Pair]"
    won:    bool
    wager:  str   # Decimal as string
    payout: str   # Decimal as string — net cash profit (wager × multiplier for Star Pairs, flat prize for Blazing 7s)

    def to_dict(self) -> dict:
        return {
            "name":   self.name,
            "won":    self.won,
            "wager":  self.wager,
            "payout": self.payout,
        }


@dataclass
class RoundResult:
    """Settlement result for one hand, shown in ROUND_OVER phase."""
    label:   str   # e.g. "Hand 1" or "Hand"
    outcome: str   # e.g. "WIN_BJ", "LOSE", "WIN_FCT"
    net:     str   # Decimal as string — net change to balance (positive = profit)

    def to_dict(self) -> dict:
        return {
            "label":   self.label,
            "outcome": self.outcome,
            "net":     self.net,
        }


@dataclass
class SessionStats:
    """Running statistics for the current session (persists across rounds)."""
    hands_played:     int
    hands_won:        int
    hands_lost:       int
    blackjacks:       int
    five_card_tricks: int
    best_hand:        str   # Decimal as string — highest single-hand net profit
    net_pnl:          str   # Decimal as string — current balance minus starting balance
    current_streak:   int   # +N = win streak, -N = loss streak, 0 = neutral

    def to_dict(self) -> dict:
        return {
            "hands_played":     self.hands_played,
            "hands_won":        self.hands_won,
            "hands_lost":       self.hands_lost,
            "blackjacks":       self.blackjacks,
            "five_card_tricks": self.five_card_tricks,
            "best_hand":        self.best_hand,
            "net_pnl":          self.net_pnl,
            "current_streak":   self.current_streak,
        }


@dataclass
class GameState:
    """
    Complete serializable snapshot of the game at any point.
    Every field the frontend needs to render the UI is present here.
    Monetary values (balance, wager, jackpot_pool, net) are Decimal-as-string.
    """
    session_id:         str
    phase:              GamePhase
    player_name:        str
    balance:            str                         # Decimal as string
    dealer_cards:       list[CardState]
    dealer_total:       int                         # visible total only during player turn
    hands:              list[HandState]
    active_hand_index:  Optional[int]               # None outside PLAYER_TURN
    available_actions:  list[str]                   # subset of ["H","S","D","P"]
    side_bet_results:   Optional[list[SideBetResult]]  # set after deal; None before
    round_results:      Optional[list[RoundResult]]    # set in ROUND_OVER; None before
    shoe_remaining:     int
    jackpot_pool:       str                         # Decimal as string
    shuffle_notice:     bool                        # True for the first state after a reshuffle
    session_stats:      SessionStats

    def to_dict(self) -> dict:
        return {
            "session_id":        self.session_id,
            "phase":             self.phase.value,
            "player_name":       self.player_name,
            "balance":           self.balance,
            "dealer_cards":      [c.to_dict() for c in self.dealer_cards],
            "dealer_total":      self.dealer_total,
            "hands":             [h.to_dict() for h in self.hands],
            "active_hand_index": self.active_hand_index,
            "available_actions": self.available_actions,
            "side_bet_results":  [r.to_dict() for r in self.side_bet_results] if self.side_bet_results is not None else None,
            "round_results":     [r.to_dict() for r in self.round_results] if self.round_results is not None else None,
            "shoe_remaining":    self.shoe_remaining,
            "jackpot_pool":      self.jackpot_pool,
            "shuffle_notice":    self.shuffle_notice,
            "session_stats":     self.session_stats.to_dict(),
        }

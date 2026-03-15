"""
Pydantic request and response models for the Blackjack Challenge API.

Every endpoint returns GameStateResponse — a uniform contract the frontend
reads to render the entire UI. Monetary fields (balance, wager, net, etc.)
are strings to preserve Decimal precision across the JSON boundary.
"""
from typing import Literal, Optional

from pydantic import BaseModel


# ── Request models ─────────────────────────────────────────────────────────────

class NewGameRequest(BaseModel):
    player_name:      str
    starting_balance: str        # Decimal as string, e.g. "1000"
    num_decks:        int = 6    # must be 6 or 8


class PlaceBetRequest(BaseModel):
    session_id:       str
    wager:            str                   # main wager as Decimal string
    star_pairs_wager: Optional[str] = None  # omit or null = no Star Pairs bet
    blazing_7s:       bool = False          # True = place $2.50 Blazing 7s entry


class ActionRequest(BaseModel):
    session_id: str
    action:     Literal["H", "S", "D", "P"]


# ── Response models ────────────────────────────────────────────────────────────

class CardStateResponse(BaseModel):
    rank:        Optional[str]
    suit:        Optional[str]
    suit_symbol: Optional[str]
    colour:      Optional[str]
    face_up:     bool
    point_value: Optional[int]


class HandStateResponse(BaseModel):
    cards:         list[CardStateResponse]
    total:         int
    wager:         str
    doubled:       bool
    is_split_hand: bool
    is_complete:   bool
    outcome:       Optional[str]
    side_bets:     dict


class SideBetResultResponse(BaseModel):
    name:   str
    won:    bool
    wager:  str
    payout: str


class RoundResultResponse(BaseModel):
    label:   str
    outcome: str
    net:     str   # net change to balance (positive = profit)


class GameStateResponse(BaseModel):
    session_id:        str
    phase:             str   # GamePhase.value string
    player_name:       str
    balance:           str
    dealer_cards:      list[CardStateResponse]
    dealer_total:      int
    hands:             list[HandStateResponse]
    active_hand_index: Optional[int]
    available_actions: list[str]
    side_bet_results:  Optional[list[SideBetResultResponse]]
    round_results:     Optional[list[RoundResultResponse]]
    shoe_remaining:    int
    jackpot_pool:      str
    shuffle_notice:    bool

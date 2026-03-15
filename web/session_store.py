"""
In-memory session store. Maps session_id (UUID) → WebGameEngine instance.
One engine per browser session; the engine holds the shoe and jackpot pool
across rounds so they persist throughout the game.

For the initial MVP this is a plain module-level dict (single process, no TTL).
A future upgrade would replace _sessions with a Redis-backed store with expiry.
"""
import uuid
from decimal import Decimal
from typing import Optional

from blackjack_challenge.models.player import Player
from blackjack_challenge.game.web_engine import WebGameEngine

_sessions: dict[str, WebGameEngine] = {}


def create(player_name: str, starting_balance: Decimal, num_decks: int) -> WebGameEngine:
    """Create a new session and return its engine."""
    session_id = str(uuid.uuid4())
    player = Player(player_name, starting_balance)
    engine = WebGameEngine(session_id, player, num_decks)
    _sessions[session_id] = engine
    return engine


def get(session_id: str) -> Optional[WebGameEngine]:
    """Return the engine for session_id, or None if not found."""
    return _sessions.get(session_id)


def delete(session_id: str) -> None:
    """Remove a session (e.g. after GAME_OVER)."""
    _sessions.pop(session_id, None)

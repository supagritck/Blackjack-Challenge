"""
FastAPI server for Blackjack Challenge.

Run from the project root:
    uvicorn web.server:app --reload

All game endpoints return a uniform GameStateResponse. The frontend reads
this single shape to render every UI state — no other data contract needed.
"""
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from blackjack_challenge.config import (
    BLAZING_7S_ENTRY, MIN_BET, MAX_BET, MAX_SIDE_BET, VALID_DECK_COUNTS,
)
from blackjack_challenge.game.state import GameState
from web import session_store
from web.schemas import (
    ActionRequest, GameStateResponse, NewGameRequest, PlaceBetRequest,
)

# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI(title="Blackjack Challenge", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Static entry point ─────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


# ── Config endpoint (table limits for frontend validation) ─────────────────────

@app.get("/api/config")
def get_config():
    return {
        "min_bet":          str(MIN_BET),
        "max_bet":          str(MAX_BET),
        "max_side_bet":     str(MAX_SIDE_BET),
        "blazing_7s_entry": str(BLAZING_7S_ENTRY),
        "valid_deck_counts": list(VALID_DECK_COUNTS),
    }


# ── Game endpoints ─────────────────────────────────────────────────────────────

@app.post("/api/new-game", response_model=GameStateResponse)
def new_game(req: NewGameRequest):
    """
    Create a new session. Returns an initial GameState with phase=WAITING_FOR_BET.
    The session_id in the response must be sent with every subsequent request.
    """
    name = req.player_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="player_name must not be empty.")
    if len(name) > 30:
        raise HTTPException(status_code=400, detail="player_name must be 30 characters or fewer.")

    balance = _parse_decimal(req.starting_balance, "starting_balance")
    if balance <= 0:
        raise HTTPException(status_code=400, detail="starting_balance must be positive.")

    if req.num_decks not in VALID_DECK_COUNTS:
        raise HTTPException(
            status_code=400,
            detail=f"num_decks must be one of {list(VALID_DECK_COUNTS)}.",
        )

    engine = session_store.create(name, balance, req.num_decks)
    return _to_response(engine.get_state())


@app.post("/api/place-bet", response_model=GameStateResponse)
def place_bet(req: PlaceBetRequest):
    """
    Start a new round. Validates the wager, builds the side_bets dict,
    calls engine.start_round(), and returns the post-deal GameState.
    """
    engine = _get_engine_or_404(req.session_id)

    wager = _parse_decimal(req.wager, "wager")
    if wager < MIN_BET:
        raise HTTPException(status_code=400, detail=f"Minimum bet is ${MIN_BET}.")
    if wager > MAX_BET:
        raise HTTPException(status_code=400, detail=f"Maximum bet is ${MAX_BET}.")

    side_bets: dict = {}
    if req.star_pairs_wager is not None:
        sp = _parse_decimal(req.star_pairs_wager, "star_pairs_wager")
        if sp <= 0:
            raise HTTPException(status_code=400, detail="star_pairs_wager must be positive.")
        if sp > MAX_SIDE_BET:
            raise HTTPException(status_code=400, detail=f"Maximum side bet is ${MAX_SIDE_BET}.")
        side_bets["star_pairs"] = sp
    if req.blazing_7s:
        side_bets["blazing_7s"] = BLAZING_7S_ENTRY

    try:
        state = engine.start_round(wager, side_bets)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return _to_response(state)


@app.post("/api/action", response_model=GameStateResponse)
def player_action(req: ActionRequest):
    """
    Apply one player action (H/S/D/P) to the active hand.
    Returns the updated GameState.
    """
    engine = _get_engine_or_404(req.session_id)

    try:
        state = engine.take_action(req.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return _to_response(state)


@app.get("/api/state/{session_id}", response_model=GameStateResponse)
def get_state(session_id: str):
    """
    Return the current GameState without advancing the game.
    Used by the frontend on page load to reconnect to an active session.
    """
    engine = _get_engine_or_404(session_id)
    return _to_response(engine.get_state())


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_engine_or_404(session_id: str):
    engine = session_store.get(session_id)
    if engine is None:
        raise HTTPException(status_code=404, detail="Session not found or expired.")
    return engine


def _parse_decimal(value: str, field: str) -> Decimal:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail=f"Invalid amount for '{field}': '{value}'.")


def _to_response(state: GameState) -> GameStateResponse:
    return GameStateResponse.model_validate(state.to_dict())

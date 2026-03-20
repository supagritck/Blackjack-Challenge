# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Game

**Terminal (original):**
```bash
python main.py
```
Requires Python 3.10+. No external dependencies — pure stdlib only.

**Web server:**
```bash
pip install -r requirements.txt
uvicorn web.server:app --reload
```
Then open `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

## Architecture Overview

The project is a terminal-based Blackjack game with a clean three-layer architecture:

### Layers

- **`blackjack_challenge/models/`** — Pure data structures: `Card`/`Rank`/`Suit` enums, `Hand`/`PlayerHand`/`DealerHand`, `Player`/`Dealer`. No game logic here.
- **`blackjack_challenge/game/`** — All business logic:
  - `engine.py` — Round orchestration state machine (the central coordinator)
  - `rules.py` — Pure adjudication functions (win/loss/bust conditions)
  - `payouts.py` — Balance settlement and payout multipliers
  - `side_bets.py` — Star Pairs and Blazing 7s evaluation
- **`blackjack_challenge/ui/`** — All user interaction:
  - `display.py` — Terminal rendering (clears screen, draws hands, results)
  - `formatting.py` — ANSI color codes and ASCII card art
  - `prompts.py` — Input validation loops (name, bets, actions)
- **`blackjack_challenge/config.py`** — Centralized constants: payout multipliers, table limits, shuffle threshold, 10-card ranking for BJ comparisons.

### Game Flow (engine.py)

Each round runs through these phases:
1. Shoe integrity check — reshuffle if <25% remaining
2. Betting — main wager + optional side bets
3. Initial deal — 2 cards to player, 1 to dealer
4. Side bet settlement — evaluated and displayed immediately
5. Blackjack check — settle instantly if player has BJ
6. Player turn — Hit / Stand / Double / Split (up to 3 splits)
7. Dealer turn — auto-plays until ≥17
8. Final settlement — payouts applied, balance updated

### Custom Rules (not standard casino Blackjack)

- **No push on ties** — equal totals = player loses
- **Blackjack vs Blackjack** — tiered payout based on 10-card rank (10 < J < Q < K)
- **Five Card Trick** — 5 cards without bust = auto-win
- **21 Auto-Win** — hitting exactly 21 ends the hand immediately as a win
- **Double Down** — available on totals of 9, 10, or 11 (on 2 or 3 cards)

### Monetary Precision

All balance and payout values use Python's `Decimal` type to avoid floating-point errors. Maintain this convention when adding any monetary logic.

---

## Web Migration (Branch: BJ-0.2)

The game is being migrated to a FastAPI backend + HTML/CSS/JS frontend. The terminal game is untouched throughout — both coexist.

### New files

| File | Purpose |
|---|---|
| `blackjack_challenge/game/state.py` | `GamePhase` enum + `GameState`, `CardState`, `HandState`, `SideBetResult`, `RoundResult` dataclasses. The single JSON contract between backend and frontend. All monetary fields are Decimal-as-string. |
| `blackjack_challenge/game/web_engine.py` | `WebGameEngine` — request-driven state machine. Three public methods: `start_round(wager, side_bets)`, `take_action("H"/"S"/"D"/"P")`, `get_state()`. Each returns a `GameState`. Shares `rules.py`, `payouts.py`, `side_bets.py` with the terminal engine. |
| `web/session_store.py` | In-memory `session_id (UUID) → WebGameEngine` dict. One engine per browser session persists shoe + jackpot across rounds. |
| `web/schemas.py` | Pydantic request (`NewGameRequest`, `PlaceBetRequest`, `ActionRequest`) and response (`GameStateResponse`) models. |
| `web/server.py` | FastAPI app. Every endpoint returns `GameStateResponse`. |
| `web/static/index.html` | Single-page app — setup screen + game table. |
| `web/static/css/style.css` | Green felt table, CSS-only card rendering, responsive. |
| `web/static/js/game.js` | Pure renderer — JS holds no game state, only re-renders from API response. |

### API routes

```
GET  /                        serves index.html
GET  /api/config              table limits (min_bet, max_bet, blazing_7s_entry, …)
POST /api/new-game            create session → WAITING_FOR_BET state
POST /api/place-bet           start round → post-deal state
POST /api/action              H/S/D/P action → updated state
GET  /api/state/{session_id}  read-only snapshot for page-refresh reconnection
```

### WebGameEngine phase flow

```
WAITING_FOR_BET  →  start_round()  →  PLAYER_TURN  (or ROUND_OVER if BJ)
PLAYER_TURN      →  take_action()  →  PLAYER_TURN  (more hands)
                                   →  ROUND_OVER   (all hands settled)
                                   →  GAME_OVER    (balance = 0)
ROUND_OVER       →  start_round()  →  (next round)
```

### Dealer hole card hiding

During `PLAYER_TURN` the dealer has only 1 card (hole card is not dealt until `_run_dealer_phase`). `_build_game_state(hide_hole=True)` would hide a second card if one existed, but in normal play there is only ever 1 dealer card during PLAYER_TURN.

### Frontend design

`game.js` is a pure renderer. The server is the sole source of truth — JS holds no game state. `render(state)` is called after every API response and redraws the entire UI from scratch. `localStorage` stores `bjSessionId` so the page can reconnect on refresh via `GET /api/state/{id}`.

### SVG card deck (Phase 5)

Card images are served from `/static/cards/`. Run the download script once to populate them:

```bash
python scripts/download_cards.py
```

Source: `htdebeer/SVGcards` (MIT licence) — `ace_of_spades.svg`, `2_of_clubs.svg`, etc.
`game.js:createCard()` tries the SVG image first; `onerror` falls back to CSS-only rendering so the game is always playable.

### Integration tests (Phase 6)

```bash
pip install -r requirements-dev.txt
pytest tests/test_api.py -v
```

49 tests covering: all API endpoints, all error/validation cases, full round flow, GAME_OVER, reconnection, shoe depletion, side bets. Uses `fastapi.testclient.TestClient` (no server required).

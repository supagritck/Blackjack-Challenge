# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Game

```bash
python main.py
```

Requires Python 3.10+. No external dependencies — pure stdlib only.

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

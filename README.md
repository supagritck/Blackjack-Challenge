# Blackjack Challenge

Hello friends! I have created this project just for fun because I would like to play Blackjack when I have travelled to Australia. I remember the rules of that and I found that they have pdf file that show how to play.

Anyway, this is my first version of BJ game and I use Claude Code to create the prototype. I use python to create the game and it is look playable now.

In the future, I will improve this project for more detail :D

Project Details
A feature-rich, terminal-based Blackjack game written in Python with custom casino rules, side bets, and special win conditions.

## Features

- **Custom Blackjack rules** — no push on ties (equal totals = player loses)
- **Blackjack vs Blackjack** — tiered payouts based on 10-value card rank (10 < J < Q < K)
- **Five Card Trick** — 5 cards without busting is an automatic win
- **21 Auto-Win** — hitting exactly 21 triggers an immediate win
- **Split up to 3 hands** — split pairs up to 2 times (max 3 hands)
- **Double Down** — available on totals of 9, 10, or 11 (on 2 or 3 cards)
- **Side Bets** — Star Pairs and Blazing 7s with jackpot pools
- **6 or 8 deck shoe** — reshuffles automatically when 25% remains

## Payouts

### Base Game
| Result | Payout |
|---|---|
| Blackjack (no dealer BJ) | 2:1 |
| BJ vs BJ — player 10-card ranks higher | 5:1 |
| BJ vs BJ — same rank | 4:1 |
| BJ vs BJ — dealer 10-card ranks higher | 3:1 |
| Win / Five Card Trick / 21 Auto-Win | 1:1 |
| Loss / Bust / Tie | Lose wager |

### Side Bets — Star Pairs
| Hand | Payout |
|---|---|
| Pair of Aces | 30:1 |
| Suited Pair | 20:1 |
| Same Colour Pair | 8:1 |
| Mixed Pair | 5:1 |

### Side Bets — Blazing 7s
| Hand | Payout |
|---|---|
| Three 7s of Diamonds | 100% of jackpot |
| Three Suited Sevens | 10% of jackpot |
| Three Coloured Sevens | 1,250 |
| Three Sevens | 500 |
| Two Player Sevens | 50 |
| One Player Seven + Dealer 7 | 25 |

## Installation

**Requirements:** Python 3.10+

```bash
git clone https://github.com/supagritck/Blackjack-Challenge.git
cd Blackjack-Challenge
python main.py
```

No external dependencies required — uses only the Python standard library.

## Project Structure

```
Blackjack-Challenge/
├── main.py                         # Entry point
├── blackjack_challenge/
│   ├── config.py                   # Table limits, payouts, constants
│   ├── game/
│   │   ├── engine.py               # Core game loop and round orchestration
│   │   ├── rules.py                # Hand adjudication logic
│   │   ├── payouts.py              # Settlement and payout calculations
│   │   └── side_bets.py            # Star Pairs and Blazing 7s evaluation
│   ├── models/
│   │   ├── card.py                 # Card and Rank/Suit enums
│   │   ├── deck.py                 # Deck and Shoe (multi-deck)
│   │   ├── hand.py                 # PlayerHand and DealerHand
│   │   └── player.py               # Player and Dealer models
│   └── ui/
│       ├── display.py              # Screen rendering
│       ├── formatting.py           # Text formatting helpers
│       └── prompts.py              # User input prompts
└── game_guide_blackjack_challenge.pdf
```

## How to Play

1. Enter your name and starting balance when prompted
2. Choose 6 or 8 deck shoe
3. Each round: place your main wager and optional side bets
4. Choose actions: **H**it, **S**tand, **D**ouble Down, s**P**lit
5. Side bets (Star Pairs, Blazing 7s) are resolved immediately after the initial deal

## Table Limits

| | Amount |
|---|---|
| Minimum bet | $5 |
| Maximum bet | $10,000 |
| Maximum side bet | $500 |
| Blazing 7s entry fee | $2.50 |
| Blazing 7s jackpot minimum | $25,000 |

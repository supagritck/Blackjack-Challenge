"""
Web-friendly game engine. Replaces the blocking terminal loop with a
request-driven state machine. Each public method accepts one action,
advances the game as far as possible without player input, and returns
a GameState snapshot.

The terminal GameEngine (engine.py) is completely untouched and continues
to work. Both engines share the same rules.py, payouts.py, and side_bets.py.
"""
from decimal import Decimal
from typing import List, Optional

from blackjack_challenge.models.deck import Shoe
from blackjack_challenge.models.hand import PlayerHand
from blackjack_challenge.models.player import Player, Dealer
from blackjack_challenge.game.rules import (
    OUTCOME_WIN_BJ, OUTCOME_WIN_FCT, OUTCOME_WIN_21,
)
from blackjack_challenge.game.payouts import settle_hand, settle_side_bets
from blackjack_challenge.game.side_bets import evaluate_all_side_bets
from blackjack_challenge.game.state import (
    GameState, GamePhase, CardState, HandState, SideBetResult, RoundResult,
    SessionStats,
)
from blackjack_challenge.config import BLAZING_7S_JACKPOT_MIN


class WebGameEngine:
    """
    Pausable Blackjack game engine for the web API.

    Lifecycle per session:
        1. __init__        — created once per HTTP session; holds shoe + jackpot across rounds
        2. start_round()   — begin a new round; returns GameState after initial deal
        3. take_action()   — one player action per request; returns updated GameState
        4. get_state()     — read-only snapshot for reconnection / page refresh
        5. Repeat from 2 when phase returns to ROUND_OVER.
    """

    def __init__(self, session_id: str, player: Player, num_decks: int = 6):
        self._session_id = session_id
        self.player = player
        self.dealer = Dealer()
        self.shoe = Shoe(num_decks)
        self.jackpot_pool: Decimal = BLAZING_7S_JACKPOT_MIN

        self.phase: GamePhase = GamePhase.WAITING_FOR_BET
        self.active_hand_index: Optional[int] = None
        self._side_bet_results: Optional[List[SideBetResult]] = None
        self._round_results: Optional[List[RoundResult]] = None
        self._shuffle_notice: bool = False

        # Session stats — persists across all rounds
        self._starting_balance: Decimal = player.balance
        self._hands_played:     int = 0
        self._hands_won:        int = 0
        self._hands_lost:       int = 0
        self._blackjacks:       int = 0
        self._five_card_tricks: int = 0
        self._best_hand:        Decimal = Decimal("0")
        self._current_streak:   int = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def get_state(self) -> GameState:
        """Return the current GameState snapshot without advancing the game."""
        return self._build_game_state()

    def start_round(self, wager: Decimal, side_bets: dict) -> GameState:
        """
        Begin a new round.

        side_bets: {bet_name: Decimal} for bets actually placed, e.g.
            {"star_pairs": Decimal("25"), "blazing_7s": Decimal("2.50")}
        Pass an empty dict for no side bets.

        Returned GameState phase:
            PLAYER_TURN  — normal deal, player acts next
            ROUND_OVER   — player had immediate Blackjack
            GAME_OVER    — balance hit zero after BJ settlement
        """
        if self.phase not in (GamePhase.WAITING_FOR_BET, GamePhase.ROUND_OVER):
            raise ValueError("Cannot start a new round while one is in progress.")
        if self.player.balance <= 0:
            self.phase = GamePhase.GAME_OVER
            return self._build_game_state()

        # ── Reset round state ─────────────────────────────────────────────────
        self.player.reset_hands()
        self.dealer.reset()
        self._side_bet_results = None
        self._round_results = None
        self._shuffle_notice = False

        # ── Validate funds ────────────────────────────────────────────────────
        side_bet_total = sum(side_bets.values(), Decimal("0"))
        if wager > self.player.balance:
            raise ValueError("Insufficient balance for wager.")
        if side_bet_total > self.player.balance - wager:
            raise ValueError("Insufficient balance for side bets.")

        # Side bet amounts deducted upfront; wager deducted inside place_initial_hand
        for amount in side_bets.values():
            self.player.deduct(amount)

        # ── Phase 1: Initial deal ─────────────────────────────────────────────
        hand = self.player.place_initial_hand(wager, side_bets)
        hand.add_card(self.shoe.deal())              # player card 1
        self.dealer.hand.add_card(self.shoe.deal())  # dealer card 1 (face up)
        hand.add_card(self.shoe.deal())              # player card 2

        # ── Phase 2: Evaluate & settle side bets immediately ─────────────────
        raw = evaluate_all_side_bets(hand, self.dealer.hand, self.jackpot_pool)
        settle_side_bets(self.player, hand, raw)
        self._side_bet_results = [
            SideBetResult(
                name=n, won=w, wager=str(wr),
                payout=str(
                    # Blazing 7s: p is a flat cash prize (net profit = p)
                    # Star Pairs: p is a multiplier (net profit = wager × multiplier)
                    p if n.startswith("Blazing 7s") else wr * p
                ),
            )
            for n, w, wr, p in raw
        ]

        # ── Phase 2b: Player Blackjack check ─────────────────────────────────
        if hand.is_blackjack():
            # Deal dealer's hole card now so BJ payout can be calculated
            self.dealer.hand.add_card(self.shoe.deal())
            hand.mark_complete(OUTCOME_WIN_BJ)
            self._settle_all()
            self._check_reshuffle()
            self.active_hand_index = None
            self.phase = (
                GamePhase.GAME_OVER if self.player.balance <= 0
                else GamePhase.ROUND_OVER
            )
            return self._build_game_state()

        # ── Ready for player actions ──────────────────────────────────────────
        self.phase = GamePhase.PLAYER_TURN
        self.active_hand_index = 0
        return self._build_game_state()

    def take_action(self, action: str) -> GameState:
        """
        Apply one player action to the currently active hand.

        action: "H" (hit) | "S" (stand) | "D" (double) | "P" (split)

        Returned GameState phase:
            PLAYER_TURN  — more actions required
            ROUND_OVER   — round complete (dealer played, all hands settled)
            GAME_OVER    — balance hit zero after settlement
        """
        if self.phase != GamePhase.PLAYER_TURN:
            raise ValueError("Not currently in player turn phase.")

        hand = self.player.hands[self.active_hand_index]
        available = self._available_actions(hand)

        if action not in available:
            raise ValueError(
                f"Action '{action}' is not available. Available: {available}"
            )

        # ── Apply action ──────────────────────────────────────────────────────

        if action == "H":
            self._do_hit(hand)

        elif action == "S":
            hand.mark_complete("STAND")

        elif action == "D":
            self._do_double(hand)

        elif action == "P":
            self._do_split(hand, self.active_hand_index)
            # After split both hands have 2 cards. Check for immediate completion
            # on the current hand (21 from split is settled normally, not WIN_21).
            if hand.is_21() and not hand.is_complete:
                hand.mark_complete("STAND")
            elif hand.is_bust() and not hand.is_complete:
                hand.mark_complete("LOSE")
            # If current hand is still playable, return and wait for next action
            if not hand.is_complete:
                return self._build_game_state()
            # Otherwise fall through to advance logic

        # ── Check immediate win / bust conditions after H or D ────────────────
        if action in ("H", "D") and not hand.is_complete:
            if hand.is_five_card_trick():
                hand.mark_complete(OUTCOME_WIN_FCT)
            elif hand.is_21():
                hand.mark_complete(OUTCOME_WIN_21)
            elif hand.is_bust():
                hand.mark_complete("LOSE")

        # ── Advance to next hand or dealer phase ──────────────────────────────
        if hand.is_complete:
            self._advance_to_next_playable_hand()

        return self._build_game_state()

    # ── Internal phase helpers ────────────────────────────────────────────────

    def _advance_to_next_playable_hand(self):
        """
        Move active_hand_index forward to the next incomplete hand.
        If none remain, trigger the dealer phase and settlement.
        """
        for i in range(self.active_hand_index + 1, len(self.player.hands)):
            if not self.player.hands[i].is_complete:
                self.active_hand_index = i
                return
        # No playable hands left — run dealer, then settle
        self._run_dealer_phase()

    def _run_dealer_phase(self):
        """
        Deal dealer's hole card, auto-play dealer if needed, settle all hands.
        Always deals the 2nd card even when all player hands are bust
        (mirrors terminal engine behaviour for display consistency).
        """
        self.dealer.hand.add_card(self.shoe.deal())

        # Dealer only plays if at least one non-busted, non-auto-win hand survives
        surviving = [
            h for h in self.player.hands
            if not h.is_bust()
            and h.outcome not in (OUTCOME_WIN_FCT, OUTCOME_WIN_21)
        ]
        if surviving:
            self.dealer.play_hand(self.shoe)

        self._settle_all()
        self._check_reshuffle()
        self.active_hand_index = None
        self.phase = (
            GamePhase.GAME_OVER if self.player.balance <= 0
            else GamePhase.ROUND_OVER
        )

    def _check_reshuffle(self):
        """Reshuffle the shoe if the threshold is reached. Called at round end."""
        if self.shoe.needs_shuffle():
            self.shoe.reshuffle()
            self._shuffle_notice = True

    def _settle_all(self):
        """Settle every player hand and store the RoundResult list."""
        results = []
        for i, hand in enumerate(self.player.hands):
            label = f"Hand {i + 1}" if len(self.player.hands) > 1 else "Hand"
            net = settle_hand(self.player, hand, self.dealer.hand)
            results.append(RoundResult(
                label=label,
                outcome=hand.outcome or "LOSE",
                net=str(net),
            ))
        self._round_results = results
        self._update_stats()

    def _update_stats(self):
        """Update running session stats from the just-completed round results."""
        if not self._round_results:
            return

        win_outcomes = {"WIN", "BLACKJACK", "FIVE CARD TRICK", "21 - AUTO WIN"}
        round_net = Decimal("0")

        for result in self._round_results:
            net = Decimal(result.net)
            round_net += net
            self._hands_played += 1

            if result.outcome in win_outcomes:
                self._hands_won += 1
            elif result.outcome == "LOSE":
                self._hands_lost += 1

            if result.outcome == "BLACKJACK":
                self._blackjacks += 1
            elif result.outcome == "FIVE CARD TRICK":
                self._five_card_tricks += 1

            if net > self._best_hand:
                self._best_hand = net

        # Streak is per round (aggregate net), not per individual hand
        if round_net > 0:
            self._current_streak = self._current_streak + 1 if self._current_streak > 0 else 1
        elif round_net < 0:
            self._current_streak = self._current_streak - 1 if self._current_streak < 0 else -1
        # round_net == 0: leave streak unchanged

    # ── Player action helpers (mirrors engine.py exactly) ─────────────────────

    def _do_hit(self, hand: PlayerHand):
        hand.add_card(self.shoe.deal())
        if hand.is_bust():
            hand.mark_complete("LOSE")

    def _do_double(self, hand: PlayerHand):
        extra = hand.original_wager
        self.player.deduct(extra)
        card = self.shoe.deal()
        hand.apply_double(card, extra)
        if hand.is_21():
            hand.outcome = OUTCOME_WIN_21
        elif hand.is_bust():
            hand.outcome = "LOSE"

    def _do_split(self, hand: PlayerHand, index: int):
        self.player.deduct(hand.original_wager)
        new_hand = hand.split_off()
        new_hand.wager = hand.original_wager
        self.player.hands.insert(index + 1, new_hand)
        hand.add_card(self.shoe.deal())
        new_hand.add_card(self.shoe.deal())

    def _available_actions(self, hand: PlayerHand) -> List[str]:
        actions = ["H", "S"]
        if hand.can_double() and self.player.can_afford(hand.original_wager):
            actions.append("D")
        if hand.can_split() and self.player.can_afford(hand.original_wager):
            actions.append("P")
        return actions

    # ── State builder ─────────────────────────────────────────────────────────

    def _build_game_state(self) -> GameState:
        """
        Construct a full GameState from current in-memory objects.
        Called at the end of every public method.
        The dealer hole card is hidden during PLAYER_TURN phase.
        shuffle_notice is a one-shot flag; it clears itself after the first read.
        """
        hide_hole = (self.phase == GamePhase.PLAYER_TURN)

        # ── Dealer cards ──────────────────────────────────────────────────────
        dealer_cards: List[CardState] = []
        for i, card in enumerate(self.dealer.hand.cards):
            if hide_hole and i == 1:
                dealer_cards.append(CardState(
                    rank=None, suit=None, suit_symbol=None,
                    colour=None, face_up=False, point_value=None,
                ))
            else:
                dealer_cards.append(CardState(
                    rank=card.rank.value,
                    suit=card.suit.value,
                    suit_symbol=card.suit.symbol,
                    colour=card.colour,
                    face_up=card.face_up,
                    point_value=card.point_value,
                ))

        # Dealer total — exclude hole card during player turn
        if hide_hole and len(self.dealer.hand.cards) >= 2:
            visible = [self.dealer.hand.cards[0]] + self.dealer.hand.cards[2:]
            total = sum(c.point_value for c in visible)
            aces = sum(1 for c in visible if c.is_ace)
            while total > 21 and aces:
                total -= 10
                aces -= 1
            dealer_total = total
        else:
            dealer_total = self.dealer.hand.total()

        # ── Player hands ──────────────────────────────────────────────────────
        hands: List[HandState] = []
        for hand in self.player.hands:
            cards = [
                CardState(
                    rank=c.rank.value,
                    suit=c.suit.value,
                    suit_symbol=c.suit.symbol,
                    colour=c.colour,
                    face_up=c.face_up,
                    point_value=c.point_value,
                )
                for c in hand.cards
            ]
            hands.append(HandState(
                cards=cards,
                total=hand.total(),
                wager=str(hand.wager),
                doubled=hand.doubled,
                is_split_hand=hand.is_split_hand,
                is_complete=hand.is_complete,
                outcome=hand.outcome,
                side_bets={k: str(v) for k, v in hand.side_bets.items()},
            ))

        # ── Available actions for the active hand ─────────────────────────────
        available_actions: List[str] = []
        if self.phase == GamePhase.PLAYER_TURN and self.active_hand_index is not None:
            available_actions = self._available_actions(
                self.player.hands[self.active_hand_index]
            )

        net_pnl = self.player.balance - self._starting_balance

        state = GameState(
            session_id=self._session_id,
            phase=self.phase,
            player_name=self.player.name,
            balance=str(self.player.balance),
            dealer_cards=dealer_cards,
            dealer_total=dealer_total,
            hands=hands,
            active_hand_index=self.active_hand_index,
            available_actions=available_actions,
            side_bet_results=self._side_bet_results,
            round_results=self._round_results,
            shoe_remaining=self.shoe.cards_remaining,
            jackpot_pool=str(self.jackpot_pool),
            shuffle_notice=self._shuffle_notice,
            session_stats=SessionStats(
                hands_played=self._hands_played,
                hands_won=self._hands_won,
                hands_lost=self._hands_lost,
                blackjacks=self._blackjacks,
                five_card_tricks=self._five_card_tricks,
                best_hand=str(self._best_hand),
                net_pnl=str(net_pnl),
                current_streak=self._current_streak,
            ),
        )

        # One-shot: clear after the first state read so it doesn't repeat
        self._shuffle_notice = False
        return state

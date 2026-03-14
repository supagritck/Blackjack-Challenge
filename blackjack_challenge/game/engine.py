"""
Core game loop and round orchestration.
"""
from decimal import Decimal
from typing import List

from blackjack_challenge.models.deck import Shoe
from blackjack_challenge.models.hand import PlayerHand, DealerHand
from blackjack_challenge.models.player import Player, Dealer
from blackjack_challenge.game.rules import (
    OUTCOME_WIN_BJ, OUTCOME_WIN_FCT, OUTCOME_WIN_21,
)
from blackjack_challenge.game.payouts import settle_hand, settle_side_bets
from blackjack_challenge.game.side_bets import evaluate_all_side_bets
from blackjack_challenge.ui import display, prompts
from blackjack_challenge.config import BLAZING_7S_JACKPOT_MIN


class GameEngine:
    def __init__(self, player: Player, num_decks: int = 6):
        self.player = player
        self.dealer = Dealer()
        self.shoe = Shoe(num_decks)
        self.jackpot_pool: Decimal = BLAZING_7S_JACKPOT_MIN
        self.current_side_bet_results: list = []

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self):
        while True:
            self._play_round()
            if self.player.balance <= 0:
                display.print_message("You have run out of chips. Game over!")
                break
            if not prompts.get_play_again():
                display.print_message("Thanks for playing Blackjack Challenge!")
                break

    # ── Round orchestration ───────────────────────────────────────────────────

    def _play_round(self):
        display.clear()

        # Phase 0 — Reshuffle check
        if self.shoe.needs_shuffle():
            display.print_message("Reshuffling the shoe...")
            self.shoe.reshuffle()

        # Phase 0 — Betting
        self.player.reset_hands()
        self.dealer.reset()
        self.current_side_bet_results = []

        display.print_header(self.player, self.shoe.cards_remaining)
        wager = prompts.get_wager(self.player.balance)

        # Side bets are deducted separately from balance
        side_bet_dict = prompts.get_side_bets(self.player.balance - wager)
        side_bet_total = sum(side_bet_dict.values())
        for amount in side_bet_dict.values():
            self.player.deduct(amount)

        # Phase 1 — Initial deal
        hand = self.player.place_initial_hand(wager, side_bet_dict)
        hand.add_card(self.shoe.deal())           # player card 1
        self.dealer.hand.add_card(self.shoe.deal())  # dealer card 1 (face up)
        hand.add_card(self.shoe.deal())           # player card 2

        # Render initial state
        display.clear()
        display.print_header(self.player, self.shoe.cards_remaining)
        display.print_dealer(self.dealer, hide_second=True)
        display.print_player_hands(self.player)

        # Phase 2 — Evaluate side bets immediately
        side_bet_results = evaluate_all_side_bets(hand, self.dealer.hand, self.jackpot_pool)
        if side_bet_results:
            settle_side_bets(self.player, hand, side_bet_results)
            self.current_side_bet_results = side_bet_results
            display.print_side_bet_results(side_bet_results)

        # Phase 2 — Check player Blackjack (deal dealer 2nd card to verify)
        if hand.is_blackjack():
            self.dealer.hand.add_card(self.shoe.deal())
            display.clear()
            display.print_header(self.player, self.shoe.cards_remaining)
            display.print_dealer(self.dealer, hide_second=False)
            display.print_player_hands(self.player)
            display.print_side_bet_results(self.current_side_bet_results)
            hand.mark_complete(OUTCOME_WIN_BJ)
            self._settle_and_show([hand])
            return

        # Phase 3 — Player actions
        self._player_phase()

        # Phase 4 — Dealer plays (only if at least one non-busted hand remains)
        surviving = [h for h in self.player.hands if not h.is_bust() and h.outcome != OUTCOME_WIN_FCT and h.outcome != OUTCOME_WIN_21]
        if surviving:
            self.dealer.hand.add_card(self.shoe.deal())  # deal dealer 2nd card
            self.dealer.play_hand(self.shoe)
        else:
            # Still deal dealer's 2nd card for display
            self.dealer.hand.add_card(self.shoe.deal())

        # Final display before settlement
        display.clear()
        display.print_header(self.player, self.shoe.cards_remaining)
        display.print_dealer(self.dealer, hide_second=False)
        display.print_player_hands(self.player)
        display.print_side_bet_results(self.current_side_bet_results)

        # Phase 5 — Settlement
        self._settle_and_show(self.player.hands)

    # ── Phase 3: Player actions ───────────────────────────────────────────────

    def _player_phase(self):
        i = 0
        while i < len(self.player.hands):
            hand = self.player.hands[i]
            self._play_hand(hand, i)
            i += 1

    def _play_hand(self, hand: PlayerHand, index: int):
        while hand.can_hit():
            display.clear()
            display.print_header(self.player, self.shoe.cards_remaining)
            display.print_dealer(self.dealer, hide_second=True)
            display.print_player_hands(self.player, active_index=index)
            display.print_side_bet_results(self.current_side_bet_results)

            actions = self._available_actions(hand)
            display.print_actions(actions)
            choice = prompts.get_action(actions)

            if choice == "H":
                self._do_hit(hand)
            elif choice == "S":
                hand.mark_complete("STAND")
                break
            elif choice == "D":
                self._do_double(hand)
            elif choice == "P":
                self._do_split(hand, index)
                # After split, re-play the current hand (now has 1 card + new card)
                continue

            # Check immediate win conditions after every hit/double
            if hand.is_five_card_trick():
                hand.mark_complete(OUTCOME_WIN_FCT)
                break
            if hand.is_21() and not hand.is_complete:
                hand.mark_complete(OUTCOME_WIN_21)
                break

        # If loop exited due to bust or 5-card or 21, ensure complete is set
        if hand.is_bust() and not hand.is_complete:
            hand.mark_complete("LOSE")

    def _available_actions(self, hand: PlayerHand) -> List[str]:
        actions = ["H", "S"]
        if hand.can_double() and self.player.can_afford(hand.original_wager):
            actions.append("D")
        if hand.can_split() and self.player.can_afford(hand.original_wager):
            actions.append("P")
        return actions

    def _do_hit(self, hand: PlayerHand):
        hand.add_card(self.shoe.deal())
        if hand.is_bust():
            hand.mark_complete("LOSE")

    def _do_double(self, hand: PlayerHand):
        extra = hand.original_wager  # double down is always exactly the original wager
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

        # Insert new hand right after current
        self.player.hands.insert(index + 1, new_hand)

        # Deal one new card to each hand
        hand.add_card(self.shoe.deal())
        new_hand.add_card(self.shoe.deal())

    # ── Phase 5: Settlement ───────────────────────────────────────────────────

    def _settle_and_show(self, hands: List[PlayerHand]):
        net_results = []
        for i, hand in enumerate(hands):
            label = f"Hand {i+1}" if len(hands) > 1 else "Hand"
            net = settle_hand(self.player, hand, self.dealer.hand)
            net_results.append((label, hand.outcome or "LOSE", net))

        display.print_result_summary(self.player, net_results)

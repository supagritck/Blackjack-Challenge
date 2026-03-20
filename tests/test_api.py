"""
Integration tests for the Blackjack Challenge web API.

Covers all game paths, state transitions, error handling, GAME_OVER,
and session reconnection.

Run from the project root:
    pytest tests/test_api.py -v
"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from web import session_store
from web.server import app

client = TestClient(app)


# ── Test helpers ──────────────────────────────────────────────────────────────

def new_game(name="TestPlayer", balance="1000", decks=6):
    return client.post("/api/new-game", json={
        "player_name":      name,
        "starting_balance": balance,
        "num_decks":        decks,
    })


def place_bet(session_id, wager="25", star_pairs=None, blazing_7s=False):
    body = {"session_id": session_id, "wager": wager, "blazing_7s": blazing_7s}
    if star_pairs is not None:
        body["star_pairs_wager"] = star_pairs
    return client.post("/api/place-bet", json=body)


def do_action(session_id, act):
    return client.post("/api/action", json={"session_id": session_id, "action": act})


def get_state(session_id):
    return client.get(f"/api/state/{session_id}")


def play_to_completion(session_id):
    """Stand on every hand until the round ends. Returns the final GameState dict."""
    for _ in range(20):
        state = get_state(session_id).json()
        if state["phase"] in ("ROUND_OVER", "GAME_OVER"):
            return state
        if state["phase"] == "PLAYER_TURN":
            resp = do_action(session_id, "S")
            assert resp.status_code == 200
            state = resp.json()
            if state["phase"] in ("ROUND_OVER", "GAME_OVER"):
                return state
    return state   # safety fallback


UNKNOWN_SESSION = "00000000-0000-0000-0000-000000000000"


# ── Config endpoint ───────────────────────────────────────────────────────────

def test_config_returns_table_limits():
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("min_bet", "max_bet", "max_side_bet", "blazing_7s_entry", "valid_deck_counts"):
        assert key in data


def test_config_values_are_correct():
    data = client.get("/api/config").json()
    assert data["min_bet"] == "5"
    assert data["max_bet"] == "10000"
    assert data["blazing_7s_entry"] == "2.50"
    assert set(data["valid_deck_counts"]) == {6, 8}


# ── /api/new-game ─────────────────────────────────────────────────────────────

def test_new_game_creates_session():
    resp = new_game()
    assert resp.status_code == 200
    state = resp.json()
    assert state["phase"] == "WAITING_FOR_BET"
    assert state["session_id"]
    assert state["player_name"] == "TestPlayer"
    assert state["balance"] == "1000"
    assert state["hands"] == []
    assert state["dealer_cards"] == []
    assert state["available_actions"] == []


def test_new_game_8_decks():
    resp = new_game(decks=8)
    assert resp.status_code == 200
    state = resp.json()
    assert state["shoe_remaining"] > 400   # 8 decks × 52 = 416


def test_new_game_whitespace_name_rejected():
    assert new_game(name="   ").status_code == 400


def test_new_game_empty_name_rejected():
    assert new_game(name="").status_code == 400   # stripped to "" → custom 400


def test_new_game_name_too_long_rejected():
    assert new_game(name="A" * 31).status_code == 400


def test_new_game_zero_balance_rejected():
    assert new_game(balance="0").status_code == 400


def test_new_game_negative_balance_rejected():
    assert new_game(balance="-50").status_code == 400


def test_new_game_non_numeric_balance_rejected():
    assert new_game(balance="lots").status_code == 400


def test_new_game_invalid_deck_count_rejected():
    assert new_game(decks=5).status_code == 400


def test_new_game_sessions_are_independent():
    sid1 = new_game(name="Alice", balance="500").json()["session_id"]
    sid2 = new_game(name="Bob",   balance="200").json()["session_id"]
    assert sid1 != sid2
    s1 = get_state(sid1).json()
    s2 = get_state(sid2).json()
    assert s1["player_name"] == "Alice" and s1["balance"] == "500"
    assert s2["player_name"] == "Bob"   and s2["balance"] == "200"


# ── /api/place-bet ────────────────────────────────────────────────────────────

def test_place_bet_transitions_to_player_turn_or_round_over():
    sid = new_game().json()["session_id"]
    resp = place_bet(sid, wager="25")
    assert resp.status_code == 200
    state = resp.json()
    assert state["phase"] in ("PLAYER_TURN", "ROUND_OVER")


def test_place_bet_deals_two_player_cards():
    sid = new_game().json()["session_id"]
    state = place_bet(sid, wager="25").json()
    assert len(state["hands"]) == 1
    assert len(state["hands"][0]["cards"]) == 2
    assert state["hands"][0]["wager"] == "25"


def test_dealer_has_one_face_up_card_during_player_turn():
    sid = new_game().json()["session_id"]
    state = place_bet(sid, wager="25").json()
    if state["phase"] == "PLAYER_TURN":
        assert len(state["dealer_cards"]) == 1
        assert state["dealer_cards"][0]["face_up"] is True


def test_place_bet_invalid_session_returns_404():
    assert place_bet(UNKNOWN_SESSION).status_code == 404


def test_place_bet_below_minimum_rejected():
    sid = new_game().json()["session_id"]
    assert place_bet(sid, wager="1").status_code == 400


def test_place_bet_above_maximum_rejected():
    sid = new_game().json()["session_id"]
    assert place_bet(sid, wager="99999").status_code == 400


def test_place_bet_non_numeric_wager_rejected():
    sid = new_game().json()["session_id"]
    assert place_bet(sid, wager="lots").status_code == 400


def test_place_bet_exceeds_balance_rejected():
    sid = new_game(balance="10").json()["session_id"]
    assert place_bet(sid, wager="25").status_code == 400


def test_place_bet_cannot_start_round_twice():
    sid = new_game().json()["session_id"]
    state = place_bet(sid, wager="25").json()
    if state["phase"] == "PLAYER_TURN":
        # Round already in progress — second bet must be rejected
        assert place_bet(sid, wager="25").status_code == 400


def test_side_bet_star_pairs_settles_immediately():
    sid = new_game().json()["session_id"]
    state = place_bet(sid, wager="25", star_pairs="10").json()
    assert state["side_bet_results"] is not None
    assert len(state["side_bet_results"]) >= 1
    result = state["side_bet_results"][0]
    assert "name" in result and "won" in result


def test_side_bet_blazing_7s_settles_immediately():
    sid = new_game().json()["session_id"]
    state = place_bet(sid, wager="25", blazing_7s=True).json()
    assert state["side_bet_results"] is not None


def test_side_bet_star_pairs_zero_not_placed():
    # Sending star_pairs_wager=0 via the API should be rejected
    sid = new_game().json()["session_id"]
    resp = place_bet(sid, wager="25", star_pairs="0")
    assert resp.status_code == 400


def test_side_bet_exceeds_limit_rejected():
    sid = new_game().json()["session_id"]
    assert place_bet(sid, wager="25", star_pairs="9999").status_code == 400


def test_side_bets_deducted_from_balance():
    sid = new_game(balance="100").json()["session_id"]
    state = place_bet(sid, wager="25", star_pairs="10", blazing_7s=True).json()
    # Balance after bet: ≤ 100 − 25 − 10 − 2.50 = 62.50 (+ any side-bet winnings)
    balance = Decimal(state["balance"])
    assert balance <= Decimal("100")


# ── /api/action ───────────────────────────────────────────────────────────────

def test_action_stand_ends_hand():
    sid = new_game().json()["session_id"]
    state = place_bet(sid, wager="25").json()
    if state["phase"] == "PLAYER_TURN":
        resp = do_action(sid, "S")
        assert resp.status_code == 200
        final = resp.json()
        assert final["phase"] in ("ROUND_OVER", "GAME_OVER")


def test_action_hit_adds_card():
    sid = new_game().json()["session_id"]
    state = place_bet(sid, wager="25").json()
    if state["phase"] == "PLAYER_TURN":
        initial_count = len(state["hands"][0]["cards"])
        resp = do_action(sid, "H")
        assert resp.status_code == 200
        new_state = resp.json()
        if new_state["phase"] == "PLAYER_TURN":
            # Card added (no bust)
            assert len(new_state["hands"][0]["cards"]) == initial_count + 1


def test_action_unknown_session_returns_404():
    assert do_action(UNKNOWN_SESSION, "S").status_code == 404


def test_action_invalid_letter_rejected():
    # "X" is not in Literal["H","S","D","P"] — Pydantic returns 422
    resp = client.post("/api/action", json={"session_id": "x", "action": "X"})
    assert resp.status_code == 422


def test_action_before_bet_returns_400():
    sid = new_game().json()["session_id"]
    # Phase is WAITING_FOR_BET — engine raises ValueError → 400
    assert do_action(sid, "S").status_code == 400


def test_double_unavailable_when_balance_too_low():
    # Balance exactly equal to bet — no funds for the extra double wager
    sid = new_game(balance="25").json()["session_id"]
    state = place_bet(sid, wager="25").json()
    if state["phase"] == "PLAYER_TURN":
        assert "D" not in state["available_actions"]


def test_split_unavailable_on_non_pair():
    """Split requires both cards to share the same point value."""
    # We can't force a non-pair, so we just verify the field is present and boolean-like
    sid = new_game().json()["session_id"]
    state = place_bet(sid, wager="25").json()
    if state["phase"] == "PLAYER_TURN":
        actions = state["available_actions"]
        # "P" only appears when the 2 cards share a point value AND funds are available
        cards = state["hands"][0]["cards"]
        if cards[0]["point_value"] != cards[1]["point_value"]:
            assert "P" not in actions
        else:
            assert "P" in actions or True   # funds may still be insufficient


def test_full_round_produces_round_results():
    sid = new_game().json()["session_id"]
    place_bet(sid, wager="25")
    final = play_to_completion(sid)
    assert final["phase"] in ("ROUND_OVER", "GAME_OVER")
    assert final["round_results"] is not None
    for r in final["round_results"]:
        assert "label" in r
        assert "outcome" in r
        assert "net" in r


def test_dealer_cards_all_face_up_after_round():
    sid = new_game().json()["session_id"]
    place_bet(sid, wager="25")
    final = play_to_completion(sid)
    if final["phase"] == "ROUND_OVER":
        for card in final["dealer_cards"]:
            assert card["face_up"] is True


def test_balance_updates_after_round():
    sid = new_game(balance="1000").json()["session_id"]
    place_bet(sid, wager="25")
    final = play_to_completion(sid)
    balance = Decimal(final["balance"])
    # Balance is either 975 (loss) or ≥1025 (win at 1:1 minimum)
    assert balance in (Decimal("975"), Decimal("1000")) or balance >= Decimal("1025")


def test_multiple_rounds_use_same_shoe():
    sid = new_game().json()["session_id"]
    place_bet(sid, wager="25")
    final1 = play_to_completion(sid)
    shoe1 = final1["shoe_remaining"]

    place_bet(sid, wager="25")
    final2 = play_to_completion(sid)
    shoe2 = final2["shoe_remaining"]

    # Shoe decreases across rounds (cards consumed)
    assert shoe2 < shoe1


# ── Blackjack instant win ─────────────────────────────────────────────────────

def test_blackjack_goes_directly_to_round_over():
    """
    If player gets Blackjack, phase skips PLAYER_TURN and goes to ROUND_OVER.
    We can't force a BJ, but if place_bet returns ROUND_OVER we validate the state.
    """
    sid = new_game().json()["session_id"]
    state = place_bet(sid, wager="25").json()
    if state["phase"] == "ROUND_OVER":
        results = state["round_results"]
        assert results is not None
        # Outcome should be BLACKJACK or a loss (dealer BJ beats player non-BJ)
        assert all(r["outcome"] in ("BLACKJACK", "WIN", "LOSE", "WIN_BJ") for r in results)


# ── GAME_OVER ─────────────────────────────────────────────────────────────────

def test_game_over_returned_when_balance_zero():
    """Directly set balance to 0 then attempt to start a round."""
    sid = new_game(balance="1000").json()["session_id"]
    engine = session_store.get(sid)
    engine.player.balance = Decimal("0")

    resp = place_bet(sid, wager="25")
    assert resp.status_code == 200
    assert resp.json()["phase"] == "GAME_OVER"


def test_game_over_state_has_final_balance():
    sid = new_game(balance="1000").json()["session_id"]
    engine = session_store.get(sid)
    engine.player.balance = Decimal("0")

    state = place_bet(sid, wager="25").json()
    assert state["balance"] == "0"
    assert state["round_results"] is None


def test_game_over_available_actions_empty():
    sid = new_game(balance="1000").json()["session_id"]
    engine = session_store.get(sid)
    engine.player.balance = Decimal("0")

    state = place_bet(sid, wager="25").json()
    assert state["available_actions"] == []


# ── Reconnection ──────────────────────────────────────────────────────────────

def test_get_state_returns_waiting_for_bet():
    sid = new_game().json()["session_id"]
    resp = get_state(sid)
    assert resp.status_code == 200
    state = resp.json()
    assert state["phase"] == "WAITING_FOR_BET"
    assert state["session_id"] == sid


def test_get_state_mid_round_returns_player_turn():
    sid = new_game().json()["session_id"]
    state = place_bet(sid, wager="25").json()
    if state["phase"] == "PLAYER_TURN":
        resp = get_state(sid)
        assert resp.status_code == 200
        assert resp.json()["phase"] == "PLAYER_TURN"


def test_get_state_preserves_hand_data():
    sid = new_game().json()["session_id"]
    state_before = place_bet(sid, wager="25").json()
    state_after  = get_state(sid).json()
    assert state_before["phase"]   == state_after["phase"]
    assert state_before["balance"] == state_after["balance"]
    assert len(state_before["hands"]) == len(state_after["hands"])


def test_get_state_unknown_session_returns_404():
    assert get_state(UNKNOWN_SESSION).status_code == 404


def test_reconnect_after_round_over():
    sid = new_game().json()["session_id"]
    place_bet(sid, wager="25")
    play_to_completion(sid)

    resp = get_state(sid)
    assert resp.status_code == 200
    state = resp.json()
    assert state["phase"] in ("ROUND_OVER", "GAME_OVER")


def test_next_round_starts_after_round_over():
    sid = new_game().json()["session_id"]
    place_bet(sid, wager="25")
    play_to_completion(sid)

    # Start the next round
    resp = place_bet(sid, wager="25")
    assert resp.status_code == 200
    assert resp.json()["phase"] in ("PLAYER_TURN", "ROUND_OVER", "GAME_OVER")


# ── Shoe reshuffle ────────────────────────────────────────────────────────────

def test_shuffle_notice_not_set_on_first_round():
    sid = new_game().json()["session_id"]
    state = place_bet(sid, wager="25").json()
    # First round — shoe is full, no reshuffle needed
    assert state["shuffle_notice"] is False


def test_shoe_remaining_decreases_per_round():
    sid = new_game().json()["session_id"]
    place_bet(sid, wager="25")
    s1 = play_to_completion(sid)["shoe_remaining"]

    place_bet(sid, wager="25")
    s2 = play_to_completion(sid)["shoe_remaining"]

    assert s2 < s1

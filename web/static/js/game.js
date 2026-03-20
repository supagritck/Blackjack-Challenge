/**
 * Blackjack Challenge — frontend renderer.
 *
 * Design principle: the server is the sole source of truth.
 * JS holds no game state — only the last GameStateResponse from the API.
 * Every button click sends a request and calls render(state) on the response.
 */

// ── Module-level state ────────────────────────────────────────────────────────
let sessionId = null;
let config    = {};

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  // Fetch table config (bet limits) for form validation
  try {
    config = await api('/api/config', 'GET');
    applyConfigToForm();
  } catch { /* ignore — defaults are fine */ }

  // Try to reconnect to an in-progress session
  const saved = localStorage.getItem('bjSessionId');
  if (saved) {
    try {
      const state = await api(`/api/state/${saved}`, 'GET');
      showSection('game-table');
      render(state);
      return;
    } catch {
      localStorage.removeItem('bjSessionId');
    }
  }

  showSection('setup-screen');
});

// ── API helper ────────────────────────────────────────────────────────────────
async function api(url, method, body) {
  const opts = { method };
  if (body) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

// ── Event handlers ────────────────────────────────────────────────────────────

// New game (setup form)
document.getElementById('setup-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = e.target.querySelector('button[type=submit]');
  btn.disabled = true;
  try {
    const state = await api('/api/new-game', 'POST', {
      player_name:      document.getElementById('player-name').value.trim(),
      starting_balance: document.getElementById('starting-balance').value,
      num_decks:        parseInt(document.getElementById('num-decks').value, 10),
    });
    showSection('game-table');
    render(state);
  } catch (err) {
    showError(err.message);
  } finally {
    btn.disabled = false;
  }
});

// Deal button
document.getElementById('deal-btn').addEventListener('click', async () => {
  const btn = document.getElementById('deal-btn');
  btn.disabled = true;
  try {
    const wager = document.getElementById('wager-input').value;
    const sp    = document.getElementById('star-pairs-input').value;
    const b7    = document.getElementById('blazing-7s-check').checked;

    const body = { session_id: sessionId, wager };
    if (sp && parseFloat(sp) > 0) body.star_pairs_wager = sp;
    body.blazing_7s = b7;

    const state = await api('/api/place-bet', 'POST', body);
    render(state);
  } catch (err) {
    showError(err.message);
  } finally {
    btn.disabled = false;
  }
});

// Action buttons (Hit / Stand / Double / Split)
document.getElementById('action-buttons').addEventListener('click', async (e) => {
  const btn = e.target.closest('.btn-action');
  if (!btn || btn.disabled) return;

  // Disable all action buttons while request is in flight
  document.querySelectorAll('.btn-action').forEach(b => { b.disabled = true; });
  try {
    const state = await api('/api/action', 'POST', {
      session_id: sessionId,
      action:     btn.dataset.action,
    });
    render(state);
  } catch (err) {
    showError(err.message);
    // Re-enable on error so player can retry
    document.querySelectorAll('.btn-action').forEach(b => { b.disabled = false; });
  }
});

// Chip preset buttons
document.getElementById('bet-controls').addEventListener('click', (e) => {
  const chip = e.target.closest('.chip-btn');
  if (chip) document.getElementById('wager-input').value = chip.dataset.amount;
});

// Next round — clear table and show bet controls
document.getElementById('play-again-btn').addEventListener('click', () => {
  clearTable();
  showControls('bet-controls');
});

// New game — go back to setup screen
document.getElementById('new-game-btn').addEventListener('click', () => {
  localStorage.removeItem('bjSessionId');
  sessionId = null;
  clearTable();
  showSection('setup-screen');
});

// ── Master render ─────────────────────────────────────────────────────────────
function render(state) {
  sessionId = state.session_id;
  localStorage.setItem('bjSessionId', sessionId);

  renderHeader(state);
  renderShuffleNotice(state);
  renderDealer(state);
  renderSideBetResults(state);
  renderHands(state);

  switch (state.phase) {
    case 'WAITING_FOR_BET':
      showControls('bet-controls');
      break;
    case 'PLAYER_TURN':
      renderActionButtons(state.available_actions);
      showControls('action-buttons');
      break;
    case 'ROUND_OVER':
      renderRoundResults(state.round_results);
      showControls('round-results');
      break;
    case 'GAME_OVER':
      document.getElementById('game-over-balance').textContent = `$${state.balance}`;
      showControls('game-over');
      break;
  }
}

// ── Render helpers ────────────────────────────────────────────────────────────

function renderHeader(state) {
  document.getElementById('player-val').textContent  = state.player_name;
  document.getElementById('balance-val').textContent = `$${state.balance}`;
  document.getElementById('shoe-val').textContent    = state.shoe_remaining;
  document.getElementById('jackpot-val').textContent = `$${state.jackpot_pool}`;
}

function renderShuffleNotice(state) {
  const el = document.getElementById('shuffle-notice');
  if (state.shuffle_notice) {
    el.classList.remove('hidden');
    setTimeout(() => el.classList.add('hidden'), 4000);
  }
}

function renderDealer(state) {
  const row   = document.getElementById('dealer-cards');
  const badge = document.getElementById('dealer-total');
  row.innerHTML = '';
  state.dealer_cards.forEach(c => row.appendChild(createCard(c)));

  if (state.dealer_cards.length > 0) {
    badge.textContent = `Total: ${state.dealer_total}`;
    badge.classList.remove('hidden');
  } else {
    badge.classList.add('hidden');
  }
}

function renderHands(state) {
  const container = document.getElementById('player-hands');
  container.innerHTML = '';

  state.hands.forEach((hand, i) => {
    const slot = document.createElement('div');
    slot.className = 'hand-slot';
    if (i === state.active_hand_index) slot.classList.add('active');
    if (hand.total > 21) slot.classList.add('bust');
    if (['WIN', 'BLACKJACK', 'FIVE CARD TRICK', '21 - AUTO WIN'].includes(hand.outcome)) {
      slot.classList.add('winner');
    }

    const cardRow = document.createElement('div');
    cardRow.className = 'card-row';
    hand.cards.forEach(c => cardRow.appendChild(createCard(c)));

    const info = document.createElement('div');
    info.className = 'hand-info';
    const outcomeHtml = hand.outcome
      ? `<span class="hand-outcome ${outcomeClass(hand.outcome)}">${formatOutcome(hand.outcome)}</span>`
      : '';
    info.innerHTML = `
      <span class="hand-total">Total: ${hand.total}</span>
      <span class="hand-wager">Bet: $${hand.wager}</span>
      ${outcomeHtml}
    `;

    slot.appendChild(cardRow);
    slot.appendChild(info);
    container.appendChild(slot);
  });
}

function renderActionButtons(available) {
  document.querySelectorAll('.btn-action').forEach(btn => {
    btn.disabled = !available.includes(btn.dataset.action);
  });
}

function renderSideBetResults(state) {
  const panel = document.getElementById('side-bet-panel');
  if (!state.side_bet_results || state.side_bet_results.length === 0) {
    panel.classList.add('hidden');
    return;
  }
  panel.innerHTML = state.side_bet_results.map(r => `
    <div class="side-bet-result ${r.won ? 'won' : 'lost'}">
      ${r.name}: ${r.won ? `+$${r.payout}` : `-$${r.wager}`}
    </div>
  `).join('');
  panel.classList.remove('hidden');
}

function renderRoundResults(results) {
  if (!results) return;
  const list = document.getElementById('results-list');
  list.innerHTML = results.map(r => {
    const cls  = outcomeClass(r.outcome);
    const sign = parseFloat(r.net) >= 0 ? '+' : '';
    return `
      <div class="result-row ${cls}">
        <span>${r.label}: ${formatOutcome(r.outcome)}</span>
        <span>${sign}$${r.net}</span>
      </div>
    `;
  }).join('');
}

// ── Card rendering ────────────────────────────────────────────────────────────

/**
 * Build a card element. Tries to load an SVG image from /static/cards/;
 * if the file is missing (404) the onerror handler injects the CSS-only
 * fallback so the game always renders correctly.
 */
function createCard(card) {
  const div = document.createElement('div');

  if (!card.face_up) {
    div.className = 'card face-down';
    _tryCardImage(div, '/static/cards/back.svg', null);
    return div;
  }

  const colour = card.colour === 'Red' ? 'red' : 'black';
  div.className = `card ${colour}`;

  _tryCardImage(div, cardImageSrc(card.rank, card.suit), () => {
    // CSS fallback — rendered when SVG file is not present
    div.innerHTML = `
      <div class="card-corner top-left">
        <div class="card-rank">${card.rank}</div>
        <div class="card-suit-sm">${card.suit_symbol}</div>
      </div>
      <div class="card-suit-center">${card.suit_symbol}</div>
      <div class="card-corner bottom-right">
        <div class="card-rank">${card.rank}</div>
        <div class="card-suit-sm">${card.suit_symbol}</div>
      </div>
    `;
  });

  return div;
}

/** Append an <img> to container; call onFallback() if the image fails to load. */
function _tryCardImage(container, src, onFallback) {
  const img = document.createElement('img');
  img.className = 'card-img';
  img.src = src;
  img.onerror = () => {
    img.remove();
    if (onFallback) onFallback();
  };
  container.appendChild(img);
}

/**
 * Map backend rank/suit strings to the SVG filename convention used by
 * htdebeer/SVGcards:  ace_of_spades.svg, 2_of_clubs.svg, jack_of_hearts.svg …
 */
function cardImageSrc(rank, suit) {
  const rankMap = { 'A': 'ace', 'J': 'jack', 'Q': 'queen', 'K': 'king' };
  const r = rankMap[rank] || rank;   // '2'–'10' pass through unchanged
  const s = suit.toLowerCase();
  return `/static/cards/${r}_of_${s}.svg`;
}

// ── Utility helpers ───────────────────────────────────────────────────────────

function showSection(id) {
  ['setup-screen', 'game-table'].forEach(s => {
    document.getElementById(s).classList.toggle('hidden', s !== id);
  });
}

function showControls(id) {
  ['bet-controls', 'action-buttons', 'round-results', 'game-over'].forEach(s => {
    document.getElementById(s).classList.toggle('hidden', s !== id);
  });
}

function clearTable() {
  document.getElementById('dealer-cards').innerHTML   = '';
  document.getElementById('dealer-total').classList.add('hidden');
  document.getElementById('player-hands').innerHTML   = '';
  document.getElementById('side-bet-panel').classList.add('hidden');
}

function outcomeClass(outcome) {
  if (['WIN', 'BLACKJACK', 'FIVE CARD TRICK', '21 - AUTO WIN'].includes(outcome)) return 'win';
  if (outcome === 'LOSE') return 'lose';
  return '';
}

function formatOutcome(outcome) {
  const map = {
    'BLACKJACK':       'Blackjack!',
    'WIN':             'Win',
    'FIVE CARD TRICK': 'Five Card Trick!',
    '21 - AUTO WIN':   '21 Auto Win!',
    'LOSE':            'Bust / Lose',
    'STAND':           'Stand',
  };
  return map[outcome] || outcome;
}

function showError(msg) {
  const el = document.getElementById('error-toast');
  el.textContent = msg;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 3500);
}

function applyConfigToForm() {
  const minBet = config.min_bet || '5';
  const wagerEl = document.getElementById('wager-input');
  wagerEl.min   = minBet;
  wagerEl.value = minBet;
}

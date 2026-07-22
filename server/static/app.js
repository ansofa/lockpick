/**
 * Lockpick Simulator — Client-side SocketIO State Machine (v1.1)
 *
 * State transitions:
 *   idle ──(form submit)──────────────────────► challenge
 *   challenge ──(confirm)──────────────────────► ready  (via prepare_session)
 *   ready ──(start_session)────────────────────► running
 *   running ──(door unlock / sensor)───────────► stopped
 *   running ──(reset)──────────────────────────► idle
 *   stopped ──(reset)──────────────────────────► idle
 */

'use strict';

// ─── SocketIO Connection ─────────────────────────────────────
const socket = io({ reconnectionDelayMax: 3000 });

// ─── DOM References ──────────────────────────────────────────
const panels = {
  idle:      document.getElementById('state-idle'),
  challenge: document.getElementById('state-challenge'),
  ready:     document.getElementById('state-ready'),
  running:   document.getElementById('state-running'),
  stopped:   document.getElementById('state-stopped'),
};

const $timerDisplay    = document.getElementById('timer-display');
const $readyPlayer     = document.getElementById('ready-player-name');
const $runningPlayer   = document.getElementById('running-player-name');
const $stoppedPlayer   = document.getElementById('stopped-player-name');
const $startForm       = document.getElementById('start-form');
const $playerInput     = document.getElementById('player-name-input');
const $formError       = document.getElementById('form-error');

// Door status elements
const $idleDot  = document.getElementById('idle-door-dot');
const $idleText = document.getElementById('idle-door-text');
const $readyDot = document.getElementById('ready-door-dot');
const $readyText= document.getElementById('ready-door-text');
const $runDot   = document.getElementById('running-door-dot');
const $runText  = document.getElementById('running-door-text');

// VU Meter elements
const $vuWrap      = document.getElementById('vu-wrap');
const $vuBar       = document.getElementById('vu-bar-fill');
const $vuDbValue   = document.getElementById('vu-db-value');
const $vuThreshLine= document.getElementById('vu-threshold-line');
const $vuThreshLbl = document.getElementById('vu-threshold-label');

// Violations
const $violationBadge = document.getElementById('violation-badge');
const $violationCount = document.getElementById('violation-count');

// Countdown
const $countdownWrap  = document.getElementById('countdown-wrap');
const $countdownValue = document.getElementById('countdown-value');

// Calibration overlay
const $calibOverlay = document.getElementById('calibration-overlay');

// Result elements
const $resTime        = document.getElementById('res-time');
const $resScore       = document.getElementById('res-score');
const $resViolations  = document.getElementById('res-violations');
const $resMaxDb       = document.getElementById('res-max-db');
const $resChallenge   = document.getElementById('res-challenge');
const $resStatusBadge = document.getElementById('result-status-badge');
const $resTrophy      = document.getElementById('result-trophy');
const $readyChalLabel = document.getElementById('ready-challenge-label');
const $readyMortLabel = document.getElementById('ready-mortise-label');

// Challenge select elements
const $mortiseSelect  = document.getElementById('mortise-select');

// ─── App State ───────────────────────────────────────────────
let currentPanel      = 'idle';
let doorIsLocked      = true;
let timerRafId        = null;
let sessionStartTime  = null;
let currentPlayerName = '';
let selectedChallenge = null;   // challenge object dari CHALLENGES array
let selectedMortise   = null;   // mortise id string
let timeLimitMs       = 0;
let showDbMeter       = true;
let serverTimeLimitMs = 0;      // dari server untuk countdown
let lastRemainingMs   = null;

// ─── Challenge Selection ─────────────────────────────────────
function selectChallenge(el) {
  document.querySelectorAll('.challenge-card').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  const ct = el.dataset.challenge;
  selectedChallenge = (typeof CHALLENGES !== 'undefined')
    ? CHALLENGES.find(c => c.challenge_type === ct) || { challenge_type: ct }
    : { challenge_type: ct };
}

// Inisialisasi: pilih card pertama dan mortise pertama
(function initSelections() {
  const first = document.querySelector('.challenge-card');
  if (first) selectChallenge(first);
  if ($mortiseSelect && $mortiseSelect.options.length > 0) {
    selectedMortise = $mortiseSelect.value;
  }
  if ($mortiseSelect) {
    $mortiseSelect.addEventListener('change', () => {
      selectedMortise = $mortiseSelect.value;
    });
  }
})();

function confirmChallenge() {
  if (!selectedChallenge) return;
  selectedMortise = $mortiseSelect ? $mortiseSelect.value : 'basic_3pin';

  // Cari label mortise
  const mortiseLbl = getMortiseLabel(selectedMortise);

  socket.emit('prepare_session', {
    player_name:    currentPlayerName,
    challenge_type: selectedChallenge.challenge_type,
    mortise_id:     selectedMortise,
  });
}

function goToIdle() {
  showPanel('idle');
}

function getMortiseLabel(id) {
  if (typeof MORTISES === 'undefined') return id;
  const m = MORTISES.find(x => x.id === id);
  return m ? m.label : id;
}

function getChallengeLabel(type) {
  if (typeof CHALLENGES === 'undefined') return type;
  const c = CHALLENGES.find(x => x.challenge_type === type);
  return c ? c.label : type;
}

// ─── Local Timer (rAF) ───────────────────────────────────────
function startLocalTimer(elapsedOffset = 0) {
  stopLocalTimer();
  sessionStartTime = performance.now() - elapsedOffset;

  function update() {
    if (currentPanel !== 'running') return;
    const elapsed = Math.max(0, performance.now() - sessionStartTime);
    if ($timerDisplay) $timerDisplay.textContent = formatMs(elapsed);
    timerRafId = requestAnimationFrame(update);
  }
  timerRafId = requestAnimationFrame(update);
}

function stopLocalTimer() {
  if (timerRafId) {
    cancelAnimationFrame(timerRafId);
    timerRafId = null;
  }
}

// ─── State Machine ───────────────────────────────────────────
function showPanel(name) {
  if (!panels[name]) return;
  Object.values(panels).forEach(el => { if (el) el.classList.remove('active'); });
  panels[name].classList.add('active');
  currentPanel = name;
}

// ─── Door Status ─────────────────────────────────────────────
function updateDoor(locked) {
  doorIsLocked = locked;
  const dotClass  = locked ? 'locked' : 'unlocked';
  const labelText = locked ? '🔒 DEADBOLT AKTIF' : '🔓 DEADBOLT TERBUKA';
  if ($idleDot)  $idleDot.className  = 'door-dot ' + dotClass;
  if ($idleText) $idleText.textContent = labelText;
  if ($readyDot) $readyDot.className = 'door-dot ' + dotClass;
  if ($readyText)$readyText.textContent = labelText;
  if ($runDot)   $runDot.className   = 'door-dot ' + dotClass + (locked ? ' pulse' : '');
  if ($runText)  $runText.textContent  = labelText;
}

// ─── VU Meter ────────────────────────────────────────────────
const VU_MAX_DB = 30; // tampilkan 0..30 dB relative

function updateVuMeter(dbRelative, threshold, show) {
  if (!show) {
    if ($vuWrap) $vuWrap.style.display = 'none';
    return;
  }
  if ($vuWrap) $vuWrap.style.display = '';

  const pct       = Math.min(100, (dbRelative / VU_MAX_DB) * 100);
  const threshPct = Math.min(100, (threshold  / VU_MAX_DB) * 100);
  const isDanger  = dbRelative >= threshold;

  if ($vuBar)        $vuBar.style.width        = pct + '%';
  if ($vuThreshLine) $vuThreshLine.style.left  = threshPct + '%';
  if ($vuThreshLbl)  $vuThreshLbl.textContent  = threshold + ' dB';

  if ($vuDbValue) {
    $vuDbValue.textContent = dbRelative.toFixed(1) + ' dB';
    $vuDbValue.classList.toggle('danger', isDanger);
  }
}

// ─── Violations ──────────────────────────────────────────────
function updateViolations(count) {
  if ($violationCount) $violationCount.textContent = count;
  if ($violationBadge) {
    $violationBadge.classList.add('flash');
    setTimeout(() => $violationBadge && $violationBadge.classList.remove('flash'), 400);
  }
}

// ─── Countdown ───────────────────────────────────────────────
function updateCountdown(remainingMs) {
  if (!$countdownWrap || !$countdownValue) return;

  if (!timeLimitMs || timeLimitMs <= 0) {
    $countdownWrap.style.display = 'none';
    return;
  }

  $countdownWrap.style.display = 'flex';
  const sec    = Math.ceil(remainingMs / 1000);
  const min    = Math.floor(sec / 60);
  const s      = sec % 60;
  $countdownValue.textContent  = `${pad2(min)}:${pad2(s)}`;
  $countdownValue.classList.toggle('urgent', remainingMs < 30000);
}

// ─── Calibration Overlay ─────────────────────────────────────
function showCalibration(show) {
  if ($calibOverlay) $calibOverlay.classList.toggle('show', show);
}

// ─── SocketIO Events ─────────────────────────────────────────
socket.on('connect', () => console.log('[WS] Connected'));

socket.on('disconnect', () => showToast('Koneksi terputus — mencoba reconnect…', 'error'));

socket.on('state_sync', (data) => {
  updateDoor(data.door_locked);
  timeLimitMs  = data.time_limit_ms || 0;
  showDbMeter  = data.show_db_meter !== false;

  if (data.mode === 'running') {
    showPanel('running');
    setPlayerChip($runningPlayer, data.player_name);
    startLocalTimer(data.elapsed_ms || 0);
    if (!timeLimitMs) { if ($countdownWrap) $countdownWrap.style.display = 'none'; }
  } else if (data.mode === 'ready') {
    showPanel('ready');
    setPlayerChip($readyPlayer, data.player_name);
  } else if (data.mode === 'stopped') {
    showPanel('stopped');
    setPlayerChip($stoppedPlayer, data.player_name);
    if ($resTime && data.duration_ms != null) $resTime.textContent = formatMs(data.duration_ms);
    if ($resScore && data.score != null) $resScore.textContent = data.score;
  } else {
    showPanel('idle');
  }
});

socket.on('door_status', (data) => updateDoor(data.locked));

socket.on('session_ready', (data) => {
  timeLimitMs = data.time_limit_ms || 0;
  showDbMeter = data.show_db_meter !== false;
  showPanel('ready');
  setPlayerChip($readyPlayer, data.player_name);
  if ($readyChalLabel) $readyChalLabel.textContent = data.challenge_label || data.challenge_type;
  if ($readyMortLabel) $readyMortLabel.textContent = getMortiseLabel(data.mortise_id || '');
  clearError();
  showCalibration(false);
});

socket.on('session_start', (data) => {
  timeLimitMs = data.time_limit_ms || 0;
  showDbMeter = data.show_db_meter !== false;
  showPanel('running');
  setPlayerChip($runningPlayer, data.player_name);
  clearError();
  // Reset violations counter
  if ($violationCount) $violationCount.textContent = '0';
  // Reset VU meter
  updateVuMeter(0, 15, showDbMeter);
  // Reset countdown
  if ($countdownWrap) $countdownWrap.style.display = timeLimitMs > 0 ? 'flex' : 'none';
  // Show calibration overlay briefly
  showCalibration(true);
  setTimeout(() => showCalibration(false), 2500);
  startLocalTimer(0);
});

socket.on('session_complete', (data) => {
  stopLocalTimer();
  showPanel('stopped');
  setPlayerChip($stoppedPlayer, data.player_name);

  if ($resTime)        $resTime.textContent       = data.display_time || formatMs(data.duration_ms);
  if ($resScore)       $resScore.textContent       = data.score != null ? data.score : '—';
  if ($resViolations)  $resViolations.textContent  = data.violations || 0;
  if ($resMaxDb)       $resMaxDb.textContent       = (data.max_db || 0).toFixed(1);
  if ($resChallenge)   $resChallenge.textContent   = getChallengeLabel(data.challenge_type || 'free_practice');

  const isTimeout = data.status === 'timeout';
  if ($resStatusBadge) {
    $resStatusBadge.textContent = isTimeout ? 'TIMEOUT' : 'SELESAI';
    $resStatusBadge.className   = 'status-badge ' + (isTimeout ? 'status-timeout' : 'status-completed');
  }
  if ($resTrophy) $resTrophy.textContent = isTimeout ? '⏰' : '✅';

  const scoreStr = data.score != null ? ` | Skor: ${data.score}` : '';
  showToast(`${isTimeout ? '⏰ Timeout!' : '✅ Selesai!'} ${data.display_time}${scoreStr}`, 'success');
});

socket.on('session_reset', () => {
  stopLocalTimer();
  showPanel('idle');
  if ($timerDisplay)   $timerDisplay.textContent   = '00:00.000';
  if ($playerInput)    $playerInput.value           = '';
  if ($violationCount) $violationCount.textContent  = '0';
  if ($vuBar)          $vuBar.style.width            = '0%';
  if ($countdownWrap)  $countdownWrap.style.display  = 'none';
  showCalibration(false);
  clearError();
});

socket.on('decibel_update', (data) => {
  if (currentPanel !== 'running') return;
  updateVuMeter(data.db || 0, data.threshold || 15, data.show !== false && showDbMeter);
});

socket.on('violation_alert', (data) => {
  if (currentPanel !== 'running') return;
  updateViolations(data.violations || 0);
  showToast(`🔊 Violation! ${data.db?.toFixed(1)} dB`, 'error', 2000);
});

socket.on('time_remaining', (data) => {
  if (currentPanel !== 'running') return;
  updateCountdown(data.remaining_ms || 0);
});

// ─── User Actions ─────────────────────────────────────────────
if ($startForm) {
  $startForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const name = ($playerInput?.value || '').trim();
    if (!name) {
      showError('ID Peserta tidak boleh kosong.');
      $playerInput?.focus();
      return;
    }
    currentPlayerName = name;
    clearError();
    showPanel('challenge');
  });
}

function startReadySession() {
  if (!doorIsLocked) {
    showToast('🔒 Kunci deadbolt terlebih dahulu', 'error');
    return;
  }
  socket.emit('start_session', {});
}

function resetSession() {
  socket.emit('reset_session');
}

// ─── Helpers ──────────────────────────────────────────────────
function formatMs(ms) {
  if (ms == null || isNaN(ms)) return '--:---.---';
  const min  = Math.floor(ms / 60000);
  const sec  = Math.floor((ms % 60000) / 1000);
  const mill = ms % 1000;
  return `${pad2(min)}:${pad2(sec)}.${pad3(mill)}`;
}

function pad2(n) { return String(Math.floor(n)).padStart(2, '0'); }
function pad3(n) { return String(Math.floor(n)).padStart(3, '0'); }

function setPlayerChip(el, name) {
  if (el) el.innerHTML = `<span aria-hidden="true">👤</span> ${escHtml(name || '—')}`;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function showError(msg) { if ($formError) $formError.textContent = msg; }
function clearError()   { if ($formError) $formError.textContent = ''; }

// ─── Toast ────────────────────────────────────────────────────
const $toastContainer = document.getElementById('toast-container');

function showToast(message, type = 'info', durationMs = 3500) {
  if (!$toastContainer) return;
  const el = document.createElement('div');
  el.className  = `toast toast-${type}`;
  el.textContent = message;
  $toastContainer.appendChild(el);
  requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add('show')));
  setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 350);
  }, durationMs);
}

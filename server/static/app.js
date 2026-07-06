/**
 * Lockpick Simulator — Client-side SocketIO State Machine
 *
 * State transitions:
 *   idle ──(start_session)──► running ──(door unlock / sensor)──► stopped
 *   running ──(reset)───────────────────────────────────────────► idle
 *   stopped ──(reset / main lagi)───────────────────────────────► idle
 */

'use strict';

// ─── SocketIO Connection ─────────────────────────────────────
const socket = io({ reconnectionDelayMax: 3000 });

// ─── DOM References ──────────────────────────────────────────
const panels = {
  idle:    document.getElementById('state-idle'),
  running: document.getElementById('state-running'),
  stopped: document.getElementById('state-stopped'),
};

const $timerDisplay     = document.getElementById('timer-display');
const $resultTime       = document.getElementById('result-time-display');
const $runningPlayer    = document.getElementById('running-player-name');
const $stoppedPlayer    = document.getElementById('stopped-player-name');
const $startForm        = document.getElementById('start-form');
const $playerInput      = document.getElementById('player-name-input');
const $formError        = document.getElementById('form-error');

// Door status elements (idle panel)
const $idleDot   = document.getElementById('idle-door-dot');
const $idleText  = document.getElementById('idle-door-text');
// Door status elements (running panel)
const $runDot    = document.getElementById('running-door-dot');
const $runText   = document.getElementById('running-door-text');

// ─── App State ───────────────────────────────────────────────
let currentPanel  = 'idle';
let doorIsLocked  = true;

// ─── State Machine ───────────────────────────────────────────
function showPanel(name) {
  if (!panels[name]) return;
  Object.values(panels).forEach(el => el.classList.remove('active'));
  panels[name].classList.add('active');
  currentPanel = name;
}

// ─── Door Status Updater ─────────────────────────────────────
function updateDoor(locked) {
  doorIsLocked = locked;

  const dotClass  = locked ? 'locked' : 'unlocked';
  const labelText = locked ? '🔒 DEADBOLT AKTIF' : '🔓 DEADBOLT TERBUKA';

  // Idle panel
  if ($idleDot) {
    $idleDot.className = 'door-dot ' + dotClass;
  }
  if ($idleText) $idleText.textContent = labelText;

  // Running panel
  if ($runDot) {
    $runDot.className = 'door-dot ' + dotClass + (locked ? ' pulse' : '');
  }
  if ($runText) $runText.textContent = labelText;
}

// ─── SocketIO Events ─────────────────────────────────────────
socket.on('connect', () => {
  console.log('[WS] Connected to Lockpick Server');
});

socket.on('disconnect', () => {
  showToast('Koneksi terputus — mencoba reconnect…', 'error');
});

/**
 * state_sync — diterima saat pertama connect.
 * Sinkronisasi UI ke state server yang sedang berjalan.
 */
socket.on('state_sync', (data) => {
  updateDoor(data.door_locked);

  if (data.mode === 'running') {
    showPanel('running');
    setPlayerChip($runningPlayer, data.player_name);
    if ($timerDisplay && data.elapsed_ms > 0) {
      $timerDisplay.textContent = data.display || formatMs(data.elapsed_ms);
    }
  } else if (data.mode === 'stopped') {
    showPanel('stopped');
    setPlayerChip($stoppedPlayer, data.player_name);
    if ($resultTime && data.duration_ms != null) {
      $resultTime.textContent = formatMs(data.duration_ms);
    }
  } else {
    showPanel('idle');
  }
});

/** door_status — real-time update dari sensor. */
socket.on('door_status', (data) => {
  updateDoor(data.locked);
});

/** timer_update — emit setiap 50ms dari server saat running. */
socket.on('timer_update', (data) => {
  if (currentPanel === 'running' && $timerDisplay) {
    $timerDisplay.textContent = data.display || formatMs(data.elapsed_ms);
  }
});

/** session_start — sesi dimulai (bisa dari client lain). */
socket.on('session_start', (data) => {
  showPanel('running');
  setPlayerChip($runningPlayer, data.player_name);
  if ($timerDisplay) $timerDisplay.textContent = '00:00.000';
  clearError();
});

/** session_complete — sesi selesai otomatis (sensor unlock). */
socket.on('session_complete', (data) => {
  showPanel('stopped');
  setPlayerChip($stoppedPlayer, data.player_name);
  if ($resultTime) $resultTime.textContent = data.display_time || formatMs(data.duration_ms);
  showToast(`✅ Selesai! Waktu: ${data.display_time}`, 'success');
});

/** session_reset — semua client kembali ke idle. */
socket.on('session_reset', () => {
  showPanel('idle');
  if ($timerDisplay) $timerDisplay.textContent = '00:00.000';
  if ($playerInput) $playerInput.value = '';
  clearError();
});

// ─── User Actions ─────────────────────────────────────────────
if ($startForm) {
  $startForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const name = ($playerInput?.value || '').trim();

    if (!name) {
      showError('Nama pemain tidak boleh kosong.');
      $playerInput?.focus();
      return;
    }

    if (!doorIsLocked) {
      showError('Pastikan deadbolt terkunci sebelum memulai!');
      showToast('🔒 Kunci deadbolt terlebih dahulu', 'error');
      return;
    }

    clearError();
    socket.emit('start_session', { player_name: name });
  });
}

/** Dipanggil oleh tombol RESET dan MAIN LAGI (via onclick di HTML). */
function resetSession() {
  socket.emit('reset_session');
}

// ─── Helpers ──────────────────────────────────────────────────
function formatMs(ms) {
  if (ms == null || isNaN(ms)) return '--:---.---';
  const totalSec = ms / 1000;
  const min      = Math.floor(totalSec / 60);
  const sec      = Math.floor(totalSec % 60);
  const mill     = ms % 1000;
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

function showError(msg) {
  if ($formError) $formError.textContent = msg;
}

function clearError() {
  if ($formError) $formError.textContent = '';
}

// ─── Toast ────────────────────────────────────────────────────
const $toastContainer = document.getElementById('toast-container');

function showToast(message, type = 'info', durationMs = 3500) {
  if (!$toastContainer) return;

  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = message;
  $toastContainer.appendChild(el);

  // Trigger transition
  requestAnimationFrame(() => {
    requestAnimationFrame(() => el.classList.add('show'));
  });

  setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 350);
  }, durationMs);
}

"""
Lockpick Simulator — GPIO Proximity Switch Handler

Sensor: NPN NO Inductive Proximity Switch
Wiring: Pin 24, internal pull-up aktif

Logika:
  Metal detected (deadbolt keluar) → pin LOW  → is_pressed = True  → LOCKED
  Metal away   (deadbolt masuk)   → pin HIGH → is_pressed = False  → UNLOCKED

Simulation mode aktif otomatis jika GPIO tidak tersedia (development di PC/Mac).
"""

import threading
import time
from typing import Callable, Optional

try:
    from gpiozero import Button
    _GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    _GPIO_AVAILABLE = False


class ProximitySwitch:
    """
    Handler untuk proximity switch NPN NO.
    Polling setiap 10ms dengan debounce 2 sample untuk menghindari false trigger.
    """

    DEBOUNCE_SAMPLES = 2   # Jumlah sample berturut-turut yang konsisten sebelum trigger
    POLL_INTERVAL    = 0.01 # 10ms

    def __init__(
        self,
        pin: int = 24,
        pull_up: bool = True,
        on_lock:   Optional[Callable] = None,
        on_unlock: Optional[Callable] = None,
    ):
        self.pin       = pin
        self.on_lock   = on_lock    # Callback: deadbolt keluar (locked)
        self.on_unlock = on_unlock  # Callback: deadbolt masuk (unlocked)

        self._last_state:    Optional[bool] = None  # State yang sudah dikonfirmasi
        self._pending_state: Optional[bool] = None  # State kandidat (belum debounce)
        self._pending_count: int = 0

        self._running = False
        self._thread:  Optional[threading.Thread] = None

        if _GPIO_AVAILABLE:
            self._sensor = Button(pin, pull_up=pull_up)
            print(f"[SENSOR] GPIO aktif → Pin {pin}, pull_up={pull_up}")
        else:
            self._sensor = None
            print("[SENSOR] ⚠️  Simulation mode — GPIO tidak tersedia (running di PC/Mac)")
            print("[SENSOR] Gunakan API POST /api/v1/simulate/lock|unlock untuk test.")

    # ─── Public ──────────────────────────────────────────────────

    @property
    def is_locked(self) -> bool:
        """True jika deadbolt sedang terkunci (metal terdeteksi)."""
        if self._sensor:
            return self._sensor.is_pressed
        return self._last_state if self._last_state is not None else True

    def start(self) -> None:
        """Mulai background polling thread."""
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="sensor-poll")
        self._thread.start()
        print("[SENSOR] Polling thread dimulai.")

    def stop(self) -> None:
        """Hentikan polling thread."""
        self._running = False
        print("[SENSOR] Polling thread dihentikan.")

    def simulate_lock(self) -> None:
        """(Simulation) Simulasikan deadbolt keluar (locked)."""
        self._trigger(True)

    def simulate_unlock(self) -> None:
        """(Simulation) Simulasikan deadbolt masuk (unlocked)."""
        self._trigger(False)

    # ─── Private ─────────────────────────────────────────────────

    def _poll_loop(self) -> None:
        while self._running:
            raw = self.is_locked
            self._debounce(raw)
            time.sleep(self.POLL_INTERVAL)

    def _debounce(self, raw: bool) -> None:
        """Debounce: hanya trigger callback setelah N sample konsisten."""
        if raw != self._pending_state:
            self._pending_state = raw
            self._pending_count = 1
        else:
            self._pending_count += 1

        if self._pending_count >= self.DEBOUNCE_SAMPLES and raw != self._last_state:
            self._trigger(raw)

    def _trigger(self, locked: bool) -> None:
        """Jalankan callback setelah state berubah."""
        self._last_state    = locked
        self._pending_state = locked
        self._pending_count = self.DEBOUNCE_SAMPLES

        if locked:
            print("[SENSOR] → LOCKED  (deadbolt keluar)")
            if self.on_lock:
                self.on_lock()
        else:
            print("[SENSOR] → UNLOCKED (deadbolt masuk)")
            if self.on_unlock:
                self.on_unlock()

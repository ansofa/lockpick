"""
Lockpick Simulator — Sensor Stubs untuk Hardware Masa Depan

Stub ini menyediakan interface yang sama dengan sensor nyata,
namun berjalan dalam simulation mode.

Tujuan:
  - Mempersiapkan arsitektur kode untuk Fase 2 (reed switch, accelerometer)
  - Server dapat mengintegrasikan sensor ini tanpa hardware fisik
  - Tidak mempengaruhi fungsional sensor yang sudah ada (proximity, mic)

Gunakan POST endpoint /api/v1/simulate/* untuk trigger event.
"""

import threading
import time
import random
from typing import Callable, Optional


class ReedSwitchStub:
    """
    Stub untuk reed switch / magnetic door sensor.

    Fungsi nyata (Fase 2):
      - Memastikan pintu benar-benar terbuka (bukan hanya bolt tertarik)
      - Mencegah kecurangan siswa menarik bolt tanpa membuka pintu

    Logika:
      door_open=False → pintu tertutup
      door_open=True  → pintu terbuka (dikombinasikan dengan proximity untuk validasi ganda)
    """

    def __init__(
        self,
        on_door_open:  Optional[Callable] = None,
        on_door_close: Optional[Callable] = None,
    ):
        self.on_door_open  = on_door_open
        self.on_door_close = on_door_close
        self._door_open    = False
        self._running      = False
        self._thread: Optional[threading.Thread] = None

        print("[REED] ⚠️  Stub mode — hardware reed switch tidak tersedia")
        print("[REED] Gunakan simulate_open() / simulate_close() untuk test.")

    @property
    def is_door_open(self) -> bool:
        return self._door_open

    def start(self) -> None:
        """Stub: tidak ada background loop, state dimanipulasi manual."""
        self._running = True
        print("[REED] Stub started (no-op).")

    def stop(self) -> None:
        self._running = False

    def simulate_open(self) -> None:
        """Simulasikan pintu terbuka."""
        if not self._door_open:
            self._door_open = True
            print("[REED] [SIM] → DOOR OPEN")
            if self.on_door_open:
                self.on_door_open()

    def simulate_close(self) -> None:
        """Simulasikan pintu tertutup."""
        if self._door_open:
            self._door_open = False
            print("[REED] [SIM] → DOOR CLOSED")
            if self.on_door_close:
                self.on_door_close()


class AccelerometerStub:
    """
    Stub untuk Accelerometer/IMU (misal MPU6050).

    Fungsi nyata (Fase 2):
      - Deteksi getaran berlebih dari tension wrench yang terlalu kasar
      - Dasar metrik 'finesse score' (teknik halus vs. kasar)

    Logika:
      vibration_level: float 0.0–1.0 (0 = tenang, 1 = getaran sangat keras)
      Threshold default: 0.6 (di atas ini dianggap kasar)
    """

    POLL_INTERVAL  = 0.05   # 50ms
    THRESHOLD      = 0.6    # normalized vibration level

    def __init__(
        self,
        threshold: float = 0.6,
        on_excessive_vibration: Optional[Callable[[float], None]] = None,
        on_vibration_update:    Optional[Callable[[float], None]] = None,
    ):
        self.threshold              = threshold
        self.on_excessive_vibration = on_excessive_vibration
        self.on_vibration_update    = on_vibration_update
        self._current_level         = 0.0
        self._running               = False
        self._thread: Optional[threading.Thread] = None

        print("[ACCEL] ⚠️  Stub mode — hardware accelerometer tidak tersedia")
        print("[ACCEL] Gunakan simulate_vibration() untuk test.")

    @property
    def current_level(self) -> float:
        return self._current_level

    def start(self) -> None:
        """Stub: tidak ada background loop aktif, hanya simulation."""
        self._running = True
        print("[ACCEL] Stub started (no-op).")

    def stop(self) -> None:
        self._running = False

    def simulate_vibration(self, level: float = 0.8) -> None:
        """
        Simulasikan level getaran.
        level: 0.0 (tenang) – 1.0 (sangat kasar)
        """
        self._current_level = max(0.0, min(1.0, level))
        print(f"[ACCEL] [SIM] → Vibration level: {self._current_level:.2f}")
        if self.on_vibration_update:
            self.on_vibration_update(self._current_level)
        if self._current_level >= self.threshold and self.on_excessive_vibration:
            self.on_excessive_vibration(self._current_level)

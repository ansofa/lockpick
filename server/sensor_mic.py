"""
Lockpick Simulator — Microphone Monitoring Handler

Fungsi:
  - Auto-detect USB microphone (prioritas atas default audio device)
  - Kalibrasi baseline noise ruangan di awal sesi
  - Monitor level desibel (dB) secara real-time setiap ~100ms
  - Deteksi pelanggaran threshold (relatif terhadap baseline)
  - Simulation mode aktif otomatis jika sounddevice tidak tersedia

Catatan hardware:
  Mic USB (condenser/USB microphone) dicolok ke port USB Raspberry Pi.
  Pada RPi, default ALSA device sering HDMI bukan USB mic.
  Kelas ini otomatis mencari device USB audio input pertama yang ditemukan.

Dependency: sounddevice, numpy
  pip install sounddevice numpy
"""

import threading
import time
import math
import random
from typing import Callable, Optional

try:
    import sounddevice as sd
    import numpy as np
    _AUDIO_AVAILABLE = True
except (ImportError, OSError):
    _AUDIO_AVAILABLE = False


def _rms_to_db(rms: float) -> float:
    """Konversi nilai RMS ke desibel (dBFS). Hindari log(0)."""
    if rms < 1e-9:
        return -90.0
    return 20 * math.log10(rms)


def find_usb_mic_index() -> Optional[int]:
    """
    Cari device audio input USB secara otomatis.

    Pada Raspberry Pi, USB mic biasanya terdaftar dengan nama mengandung
    kata 'USB', 'usb', 'Microphone', atau 'Audio'. Fungsi ini mengembalikan
    index device pertama yang cocok, atau None jika tidak ditemukan.

    Return:
        int — device index sounddevice, atau None (gunakan default system)
    """
    if not _AUDIO_AVAILABLE:
        return None
    try:
        devices = sd.query_devices()
        for idx, dev in enumerate(devices):
            # Hanya pertimbangkan device yang punya input channel
            if dev.get('max_input_channels', 0) < 1:
                continue
            name_lower = dev.get('name', '').lower()
            # Keyword yang biasanya ada di nama USB mic / USB audio adapter
            usb_keywords = ['usb', 'microphone', 'condenser', 'audio adapter',
                            'webcam', 'headset', 'capture']
            if any(kw in name_lower for kw in usb_keywords):
                print(f"[MIC] USB mic ditemukan → idx={idx} name='{dev['name']}'")
                return idx
        print("[MIC] ⚠️  Tidak ada USB mic terdeteksi — menggunakan default input device")
        return None
    except Exception as e:
        print(f"[MIC] ⚠️  Gagal query devices: {e}")
        return None


def list_audio_inputs() -> list[dict]:
    """
    List semua device audio input yang tersedia (untuk debug/admin).
    Return: list of dict {'index', 'name', 'channels', 'sample_rate'}
    """
    if not _AUDIO_AVAILABLE:
        return []
    try:
        devices = sd.query_devices()
        result  = []
        for idx, dev in enumerate(devices):
            if dev.get('max_input_channels', 0) >= 1:
                result.append({
                    'index':       idx,
                    'name':        dev.get('name', ''),
                    'channels':    dev.get('max_input_channels', 0),
                    'sample_rate': int(dev.get('default_samplerate', 44100)),
                })
        return result
    except Exception:
        return []


class MicMonitor:
    """
    Handler untuk monitoring desibel via USB microphone.

    Level dB yang dilaporkan adalah RELATIF terhadap baseline noise ruangan
    (dikalibrasi di awal sesi), bukan nilai absolut. Ini memastikan threshold
    konsisten di berbagai lingkungan dengan tingkat kebisingan berbeda.

    Pada Raspberry Pi dengan USB mic:
      - Otomatis mencari USB mic via find_usb_mic_index()
      - Jika device_index=None → auto-detect USB mic → fallback ke system default

    Contoh penggunaan:
        mic = MicMonitor(threshold_db=15)
        mic.calibrate()  # Rekam baseline 2 detik
        mic.start()      # Mulai monitoring
        # ... sesi berjalan ...
        mic.stop()
    """

    SAMPLE_RATE        = 44100
    BLOCK_SIZE         = 4096    # ~93ms per block @ 44100 Hz
    CHANNELS           = 1
    UPDATE_INTERVAL_MS = 100     # emit setiap ~100ms (sim mode)

    def __init__(
        self,
        device_index:    Optional[int]               = None,
        threshold_db:    float                        = 15.0,
        calibration_sec: float                        = 2.0,
        on_db_update:    Optional[Callable[[float], None]] = None,
        on_violation:    Optional[Callable[[float], None]] = None,
    ):
        self.threshold_db    = threshold_db
        self.calibration_sec = calibration_sec
        self.on_db_update    = on_db_update
        self.on_violation    = on_violation

        # Jika device_index tidak di-set, auto-detect USB mic
        if device_index is None and _AUDIO_AVAILABLE:
            self.device_index = find_usb_mic_index()
        else:
            self.device_index = device_index

        self._baseline_db:   float = -90.0
        self._current_db:    float = -90.0
        self._relative_db:   float = 0.0
        self._is_calibrated: bool  = False
        self._running:       bool  = False
        self._thread:  Optional[threading.Thread] = None
        self._lock                 = threading.Lock()

        # Simulation mode
        self._sim_mode = not _AUDIO_AVAILABLE
        if self._sim_mode:
            print("[MIC] ⚠️  Simulation mode — sounddevice/numpy tidak tersedia")
            print("[MIC] Install: pip install sounddevice numpy")
            print("[MIC] Gunakan POST /api/v1/simulate/noise untuk trigger violation.")
        else:
            dev_info = ""
            if self.device_index is not None:
                try:
                    dev_info = f" — '{sd.query_devices(self.device_index)['name']}'"
                except Exception:
                    pass
            print(f"[MIC] Audio siap → device_index={self.device_index}{dev_info}")

    # ─── Public ─────────────────────────────────────────────────

    @property
    def is_calibrated(self) -> bool:
        return self._is_calibrated

    @property
    def current_db_relative(self) -> float:
        """Level dB relatif terhadap baseline (0=baseline, positif=lebih keras)."""
        with self._lock:
            return self._relative_db

    @property
    def current_db_absolute(self) -> float:
        with self._lock:
            return self._current_db

    @property
    def baseline_db(self) -> float:
        with self._lock:
            return self._baseline_db

    def calibrate(self) -> float:
        """
        Rekam audio selama calibration_sec detik untuk baseline noise ruangan.
        Harus dipanggil sebelum start(). Blokir thread pemanggil.
        Return: baseline dBFS yang ditetapkan.
        """
        if self._sim_mode:
            baseline = random.uniform(-50.0, -40.0)
            with self._lock:
                self._baseline_db   = baseline
                self._is_calibrated = True
            print(f"[MIC] [SIM] Kalibrasi selesai — baseline={baseline:.1f} dBFS")
            return baseline

        try:
            print(f"[MIC] Kalibrasi baseline {self.calibration_sec:.1f}s "
                  f"(device_index={self.device_index}) …")
            recording = sd.rec(
                frames=int(self.SAMPLE_RATE * self.calibration_sec),
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype='float32',
                device=self.device_index,
            )
            sd.wait()
            rms      = float(np.sqrt(np.mean(recording ** 2)))
            baseline = _rms_to_db(rms)
            with self._lock:
                self._baseline_db   = baseline
                self._is_calibrated = True
            print(f"[MIC] Kalibrasi selesai — baseline={baseline:.1f} dBFS")
            return baseline
        except Exception as e:
            print(f"[MIC] ⚠️  Kalibrasi gagal: {e} → fallback ke simulation mode")
            self._sim_mode = True
            return self.calibrate()

    def start(self) -> None:
        """Mulai monitoring. Kalibrasi otomatis jika belum dilakukan."""
        if not self._is_calibrated:
            print("[MIC] Belum dikalibrasi — kalibrasi otomatis …")
            self.calibrate()

        self._running = True
        target = self._sim_loop if self._sim_mode else self._audio_loop
        self._thread  = threading.Thread(target=target, daemon=True, name="mic-monitor")
        self._thread.start()
        print("[MIC] Monitoring thread dimulai.")

    def stop(self) -> None:
        """Hentikan monitoring thread."""
        self._running = False
        print("[MIC] Monitoring thread dihentikan.")

    def simulate_noise(self, db_relative: float = 20.0) -> None:
        """(Test/Simulation) Trigger satu event desibel tinggi."""
        with self._lock:
            self._relative_db = db_relative
            self._current_db  = self._baseline_db + db_relative
        self._emit_update(db_relative)
        if db_relative > self.threshold_db and self.on_violation:
            self.on_violation(db_relative)

    # ─── Private ─────────────────────────────────────────────────

    def _emit_update(self, relative_db: float) -> None:
        if self.on_db_update:
            try:
                self.on_db_update(relative_db)
            except Exception:
                pass

    def _check_violation(self, relative_db: float) -> None:
        if relative_db > self.threshold_db and self.on_violation:
            try:
                self.on_violation(relative_db)
            except Exception:
                pass

    def _audio_loop(self) -> None:
        """Loop monitoring audio real via sounddevice blocking stream."""
        try:
            with sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype='float32',
                blocksize=self.BLOCK_SIZE,
                device=self.device_index,
                callback=self._audio_callback,
            ):
                while self._running:
                    time.sleep(0.05)
        except Exception as e:
            print(f"[MIC] ⚠️  Stream error: {e} → fallback simulation mode")
            self._sim_mode = True
            self._sim_loop()

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        """Dipanggil oleh sounddevice setiap BLOCK_SIZE sample (non-blocking)."""
        if status:
            print(f"[MIC] Stream status: {status}")

        rms         = float(np.sqrt(np.mean(indata ** 2)))
        current_db  = _rms_to_db(rms)
        relative_db = max(0.0, current_db - self._baseline_db)

        with self._lock:
            self._current_db  = current_db
            self._relative_db = relative_db

        self._emit_update(relative_db)
        self._check_violation(relative_db)

    def _sim_loop(self) -> None:
        """Simulation loop: noise acak untuk testing tanpa hardware."""
        print("[MIC] [SIM] Simulation loop berjalan …")
        interval = self.UPDATE_INTERVAL_MS / 1000.0
        while self._running:
            # Sebagian besar rendah, ~3% chance ada spike tinggi
            base  = random.gauss(3.0, 2.0)
            spike = random.uniform(25, 35) if random.random() < 0.03 else 0
            relative_db = max(0.0, base + spike)

            with self._lock:
                self._relative_db = relative_db
                self._current_db  = self._baseline_db + relative_db

            self._emit_update(relative_db)
            self._check_violation(relative_db)
            time.sleep(interval)

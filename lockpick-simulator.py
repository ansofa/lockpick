import tkinter as tk
from gpiozero import Button
from time import time
import sys

# --- KONFIGURASI GPIO ---
# NPN NO dengan internal pull-up: 
# Logam ada = pin LOW (is_pressed = True) -> Pintu Terkunci
# Logam jauh = pin HIGH (is_pressed = False) -> Pintu Terbuka
sensor = Button(24, pull_up=True)

class LockpickSimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("Lockpick Simulator")
        self.root.attributes('-fullscreen', True) # Fullscreen untuk Touchscreen
        self.root.configure(bg='#1e1e1e')
        
        # Variabel Stopwatch
        self.running = False
        self.start_time = 0.0
        self.elapsed_time = 0.0
        
        # --- UI ELEMENTS ---
        self.title_label = tk.Label(root, text="LOCKPICK SIMULATOR", font=("Arial", 28, "bold"), fg="#ffffff", bg="#1e1e1e")
        self.title_label.pack(pady=20)
        
        # 1. INDIKATOR STATUS FISIK PINTU (Real-time dari Sensor)
        self.door_label = tk.Label(root, text="STATUS PINTU: MENGECEK...", font=("Arial", 22, "bold"), fg="#ffffff", bg="#1e1e1e")
        self.door_label.pack(pady=10)
        
        # 2. STOPWATCH DISPLAY (Menggunakan font 'Courier' agar aman dari error)
        self.time_label = tk.Label(root, text="00:00.00", font=("Courier", 64, "bold"), fg="#ffcc00", bg="#1e1e1e")
        self.time_label.pack(pady=15)
        
        # 3. STATUS MISI SIMULATOR
        self.status_label = tk.Label(root, text="READY TO LOCKPICK", font=("Arial", 18), fg="#00ffcc", bg="#1e1e1e")
        self.status_label.pack(pady=15)
        
        # Tombol Kontrol
        self.btn_start = tk.Button(root, text="START MISSION", font=("Arial", 16, "bold"), bg="#28a745", fg="white", 
                                   command=self.start_simulator, width=15, height=2, activebackground="#218838")
        self.btn_start.pack(pady=10)
        
        self.btn_reset = tk.Button(root, text="RESET", font=("Arial", 16, "bold"), bg="#dc3545", fg="white", 
                                   command=self.reset_simulator, width=15, height=2, activebackground="#c82333")
        self.btn_reset.pack(pady=10)
        
        self.btn_exit = tk.Button(root, text="EXIT", font=("Arial", 12), bg="#6c757d", fg="white", 
                                  command=self.exit_app, width=10)
        self.btn_exit.place(x=20, y=20)
        
        # Jalankan loop update waktu dan sensor
        self.update_system()

    def start_simulator(self):
        if not self.running:
            self.running = True
            self.start_time = time() - self.elapsed_time
            self.status_label.config(text="LOCKPICKING IN PROGRESS...", fg="#ff5555")

    def stop_simulator(self):
        if self.running:
            self.running = False
            self.status_label.config(text="SUCCESS! DOOR UNLOCKED!", fg="#00ff00")

    def reset_simulator(self):
        self.running = False
        self.start_time = 0.0
        self.elapsed_time = 0.0
        self.time_label.config(text="00:00.00")
        self.status_label.config(text="READY TO LOCKPICK", fg="#00ffcc")

    def update_system(self):
        # A. UPDATE INDIKATOR PINTU REAL-TIME BERDASARKAN SENSOR
        if sensor.is_pressed:
            # Jika sensor mendeteksi logam (Deadbolt sedang keluar / mengunci)
            self.door_label.config(text="PINTU: TERKUNCI (Deadbolt Aktif)", fg="#ff4444")
        else:
            # Jika logam menjauh (Deadbolt masuk ke dalam / terbuka)
            self.door_label.config(text="PINTU: TERBUKA (Deadbolt Masuk)", fg="#00ff00")
            
            # B. LOGIKA PEMBERHENTIAN STOPWATCH
            # Jika misi sedang berjalan dan tiba-tiba logam menjauh, hentikan stopwatch!
            if self.running:
                self.stop_simulator()

        # C. UPDATE STOPWATCH (Jika misi berjalan)
        if self.running:
            self.elapsed_time = time() - self.start_time
            minutes = int(self.elapsed_time // 60)
            seconds = int(self.elapsed_time % 60)
            milliseconds = int((self.elapsed_time % 1) * 100)
            self.time_label.config(text=f"{minutes:02d}:{seconds:02d}.{milliseconds:02d}")
        
        # Ulangi fungsi pemantauan ini setiap 10ms (sangat sensitif dan real-time)
        self.root.after(10, self.update_system)
        
    def exit_app(self):
        self.root.destroy()
        sys.exit()

if __name__ == "__main__":
    root = tk.Tk()
    app = LockpickSimulator(root)
    root.mainloop()
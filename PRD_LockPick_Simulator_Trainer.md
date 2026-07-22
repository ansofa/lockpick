# PRODUCT REQUIREMENTS DOCUMENT (PRD)
**LockPick Simulator Trainer (LPST)**

**Deskripsi:** Perangkat Simulasi & Asesmen Keterampilan Lock Picking Berbasis Sensor untuk Instansi Pelatihan Keamanan/Intelijen
**Versi Dokumen:** 0.1 (Draft PoC)
**Tanggal:** 17 Juli 2026
**Status:** Konsep / Internal Review

---

## 1. Ringkasan Eksekutif
LockPick Simulator Trainer (LPST) adalah perangkat pelatihan fisik berbasis miniatur pintu yang dilengkapi mortise asli yang dapat diganti (changeable), diintegrasikan dengan Raspberry Pi, sensor proximity, mikrofon eksternal, dan layar sentuh kapasitif. Produk ini dirancang untuk melatih dan menilai keterampilan lock picking secara terukur, konsisten, dan terdokumentasi ditujukan untuk instansi dengan divisi intelijen, keamanan, atau penegakan hukum yang membutuhkan program pelatihan bertingkat dengan pencatatan nilai per siswa.

Produk terdiri dari dua komponen utama: 
1. **Device LPST:** unit fisik miniatur pintu dengan sensor dan layar interaktif tempat siswa berlatih.
2. **Dashboard Pusat:** sistem manajemen terpusat berbasis web untuk mengelola perangkat, siswa, challenge, dan hasil penilaian di seluruh unit yang terpasang.

Dokumen ini mencakup kebutuhan fungsional dan teknis, desain challenge berbasis sensor yang tersedia, estimasi komponen (BOM), roadmap pengembangan lanjutan, serta metrik keberhasilan dan risiko yang perlu dimitigasi.

---

## 2. Latar Belakang & Tujuan Produk

### 2.1 Latar Belakang
Pelatihan lock picking secara konvensional umumnya dilakukan dengan lock trainer statis (mortise transparan) tanpa mekanisme penilaian objektif. Instruktur harus mengawasi manual untuk menilai kecepatan, kebisingan yang ditimbulkan, dan teknik siswa. Proses ini sulit distandardisasi antar sesi, antar instruktur, dan antar siswa, serta tidak menghasilkan data historis yang bisa dianalisis untuk kurikulum pelatihan.

### 2.2 Tujuan Produk
* Menyediakan simulasi realistis proses *covert entry* (bukaan kunci tanpa kunci sah) dengan mortise dan mekanisme pintu yang sebenarnya.
* Mengukur performa siswa secara objektif dan konsisten: waktu penyelesaian, tingkat kebisingan (desibel), dan kehalusan teknik.
* Menstandardisasi kurikulum pelatihan melalui sistem challenge bertingkat yang dapat dikonfigurasi instruktur/admin.
* Menyediakan sistem pencatatan nilai terpusat untuk keperluan evaluasi, sertifikasi internal, dan audit pelatihan.
* Mendukung operasional di lingkungan dengan pembatasan jaringan (restricted/air-gapped) yang umum di fasilitas instansi keamanan.

---

## 3. Target Pengguna & Persona

| Persona | Deskripsi | Kebutuhan Utama |
| :--- | :--- | :--- |
| **Siswa/Peserta Pelatihan** | Personel yang menjalani pelatihan *covert entry* sebagai bagian kurikulum keamanan/intelijen. | Antarmuka latihan yang jelas, umpan balik real-time, progres yang terukur. |
| **Instruktur** | Bertanggung jawab menyusun materi, memantau sesi, menilai hasil. | Kontrol challenge, monitoring live per device, laporan performa siswa. |
| **Admin Sistem/IT Instansi** | Mengelola perangkat, akun, dan keamanan data pelatihan. | Dashboard manajemen device, kontrol akses, audit log, opsi on-premise. |
| **Pimpinan/Divisi Diklat** | Memerlukan laporan agregat untuk evaluasi program pelatihan. | Analitik & pelaporan tingkat kohort/angkatan. |

---

## 4. Ruang Lingkup Produk

### 4.1 Termasuk dalam PoC (Fase 1)
* Unit device tunggal: miniatur pintu + mortise changeable + sensor proximity + mic eksternal + layar sentuh kapasitif.
* Minimal 5 mode challenge dasar (lihat Bab 6).
* Penyimpanan nilai sementara di device (local storage) dengan sinkronisasi ke dashboard pusat saat online.
* Dashboard pusat versi awal: manajemen device, siswa, challenge, dan nilai.

### 4.2 Tidak Termasuk dalam PoC (didorong ke Fase 2/3)
* Sensor internal per-pin di dalam mortise (memerlukan modifikasi/bongkar mortise).
* Deteksi audio granular per-pin menggunakan contact microphone/piezo untuk analisis pola klik.
* Modul kompetisi multi-device real-time (leaderboard lintas unit).
* Modul anti-cheat berbasis kamera/computer vision.

---

## 5. Kebutuhan Fungsional - Device LPST

### 5.1 Mortise Changeable
Mortise dipasang pada rangka daun pintu dengan mekanisme mounting yang memungkinkan pergantian cepat (quick-release plate/dudukan sekrup standar) tanpa mengubah wiring sensor. Setiap mortise merepresentasikan tingkat kesulitan berbeda (jumlah pin, adanya security pin/spool pin, dsb) dan diberi kode identitas (QR/label) yang dapat dipilih pada layar sebelum sesi dimulai, agar sistem tahu tingkat kesulitan yang sedang dilatih.

### 5.2 Sensor Proximity (Status Kunci)
Dipasang pada kusen, menghadap area strike plate, mendeteksi keberadaan bolt/latch secara non-kontak.
* **State ON** (aktif/terdeteksi) = pintu dalam kondisi terkunci (bolt menjorok ke kusen).
* **State OFF** (tidak terdeteksi) = bolt berhasil ditarik oleh siswa → sistem mencatat waktu penyelesaian picking.
* *Rekomendasi:* Menggunakan sensor proximity tipe inductive (target logam) untuk stabilitas terhadap kondisi lingkungan, dibanding capacitive yang lebih rentan terhadap kelembapan/debu.

### 5.3 Mikrofon Eksternal (Monitoring Desibel)
Menangkap tingkat kebisingan selama proses picking berlangsung, ditampilkan sebagai indikator real-time di layar (misal VU meter/bar).
* Sistem melakukan kalibrasi baseline noise ruangan di awal sesi, sehingga ambang batas (threshold) bersifat relatif terhadap kondisi lingkungan tempat device dipasang, bukan angka absolut yang statis.
* Pelanggaran ambang batas menghasilkan peringatan visual/audio pada layar dan tercatat sebagai penalti pada skor akhir.

### 5.4 Layar Sentuh Kapasitif
* **Fungsi:** memilih challenge, menampilkan countdown waktu, indikator desibel real-time, status login siswa, dan hasil akhir sesi.
* **Alur dasar:** Login/Pilih Siswa → Pilih Challenge & Mortise → Instruksi → Start → Sesi Berjalan (timer + indikator desibel) → Selesai/Timeout → Ringkasan Skor → Simpan Lokal.

### 5.5 Sensor Tambahan yang Direkomendasikan (Non-Invasif terhadap Mortise)
*Seluruh sensor berikut dipasang pada kusen atau daun pintu, tidak memerlukan pembongkaran mekanisme internal mortise sehingga sesuai dengan batasan desain PoC.*

| Sensor | Lokasi Pemasangan | Fungsi & Manfaat |
| :--- | :--- | :--- |
| **Reed switch / magnetic door sensor** | Kusen + tepi daun pintu | Memastikan pintu benar-benar terbuka (bukan hanya bolt tertarik), mencegah kecurangan siswa menarik bolt tanpa membuka pintu. |
| **Accelerometer / IMU (mis. MPU6050)** | Ditempel pada permukaan daun pintu dekat mortise | Mendeteksi getaran berlebih dari tension wrench yang terlalu kasar sebagai dasar metrik 'finesse score'. |
| **RFID/NFC reader** | Console device atau frame, terpisah dari mortise | Login otomatis siswa via tap kartu ID, terhubung langsung ke profil di dashboard. |
| **Rotary encoder / hall sensor engsel** | Engsel pintu | Mengukur kecepatan & kehalusan bukaan pintu untuk simulasi 'entry senyap'. |
| **Piezo / contact microphone (structure-borne)** | Kusen dekat strike plate, eksternal | Melengkapi mic udara dengan sinyal suara yang lebih presisi untuk analisis pola (opsional, Fase 2). |
| **Ambient light sensor / kamera kecil** | Frame device atau tripod terpisah | Deteksi anti-cheat dasar (mis. penggunaan cahaya HP untuk mengintip lubang kunci) – *nice-to-have*. |

### 5.6 Penyimpanan Nilai Sementara di Device
* Device menyimpan setiap hasil sesi (siswa, challenge, mortise, waktu, jumlah pelanggaran desibel, status lulus/gagal) ke local storage (SQLite) segera setelah sesi selesai.
* Data yang belum tersinkron ditandai status pending dan otomatis dikirim ke dashboard pusat saat koneksi tersedia.
* Tersedia mode ekspor manual (USB/file) untuk lingkungan air-gapped yang tidak mengizinkan koneksi jaringan sama sekali.

---

## 6. Konsep Challenge
Desain challenge disusun berdasarkan kombinasi sensor yang tersedia pada PoC, dari yang paling dasar hingga yang memerlukan sensor tambahan.

| Challenge | Deskripsi & Logika Skor | Sensor yang Digunakan |
| :--- | :--- | :--- |
| **Speed Run** | Membuka kunci secepat mungkin dalam batas waktu; skor utama = waktu penyelesaian. | Proximity, Timer |
| **Silent Operator** | Harus selesai sebelum waktu habis dan desibel tidak boleh melewati ambang batas sepanjang proses; setiap pelanggaran = penalti skor. | Proximity, Mic, Timer |
| **Clean Entry** | Setelah kunci terbuka, pintu harus dibuka dengan gerakan halus (kecepatan sudut terbatas) sebagai simulasi entry senyap penuh. | Proximity, Reed switch, Rotary encoder engsel |
| **No Force / Gentle Hands** | Gagal jika getaran tension wrench melebihi ambang batas untuk melatih teknik halus, bukan memaksa pin. | Proximity, Accelerometer |
| **Progressive Certification** | Mortise diganti bertahap (jumlah pin & security pin meningkat); siswa harus lulus level sebelumnya untuk lanjut. | Proximity, Timer, ID Mortise |
| **Blind Exam** | Layar hanya menampilkan timer (indikator desibel disembunyikan); menilai murni kemampuan tanpa umpan balik visual. | Proximity, Mic (dicatat, tidak ditampilkan), Timer |
| **Endurance / Multi-Attempt** | X percobaan dalam Y menit; skor dari rata-rata waktu, tingkat keberhasilan, dan rata-rata desibel. | Proximity, Mic, Timer |
| **Assessment Mode (Ujian Sertifikasi)** | Mortise ditentukan acak oleh sistem, tanpa percobaan ulang, hasil otomatis tercatat ke profil siswa untuk sertifikasi resmi. | Proximity, Mic, RFID login, Timer |

---

## 7. Kebutuhan Fungsional - Dashboard Pusat

### 7.1 Manajemen Device
* Registrasi & pairing unit baru, monitoring status online/offline dan kesehatan sensor (baseline mic, status proximity).
* Riwayat firmware/versi software per unit dan kemampuan push update.

### 7.2 Manajemen Siswa
* Profil siswa, pemetaan kartu RFID/NFC, pengelompokan berdasarkan kelas/angkatan/kohort.

### 7.3 Manajemen Nilai
* Riwayat lengkap setiap sesi per siswa: challenge, mortise, waktu, pelanggaran desibel, status lulus/gagal.
* Leaderboard per kelas/angkatan dan perbandingan progres antar sesi.

### 7.4 Manajemen Challenge
* Konfigurasi parameter tiap challenge: batas waktu, ambang desibel, tingkat kesulitan mortise yang disyaratkan, jumlah percobaan yang diizinkan.
* Penjadwalan challenge per kelas/sesi pelatihan.

### 7.5 Sinkronisasi & Mode Offline
* Antrian sinkronisasi otomatis saat device kembali online; dashboard menampilkan status sinkronisasi tiap unit.
* Dukungan impor manual dari file ekspor USB untuk skenario air-gapped.

### 7.6 Pelaporan & Analitik
* Statistik agregat per siswa, per kelas, per periode pelatihan; tren peningkatan kemampuan dari waktu ke waktu.

### 7.7 Keamanan & Kontrol Akses
* Role-based access control (admin, instruktur, viewer), audit log seluruh aktivitas administratif.
* Opsi deployment on-premise/server lokal instansi (tanpa ketergantungan cloud publik) mengingat sensitivitas data pelatihan bagi instansi keamanan/intelijen.
* Enkripsi data saat transit (sinkronisasi device-dashboard) dan saat disimpan (at-rest).

---

## 8. Arsitektur Teknis (Gambaran Umum)

### 8.1 Komponen Sistem
* **Device Layer:** Raspberry Pi (kontroler utama) + sensor proximity, mic eksternal, sensor tambahan, layar sentuh kapasitif, local storage (SQLite).
* **Middleware:** Aplikasi lokal di Raspberry Pi (mis. Python/Node.js) yang menangani logika sesi, pembacaan sensor, penyimpanan lokal, dan proses sinkronisasi.
* **Sync Layer:** Modul komunikasi (REST API/queue) yang mengirim data sesi ke server pusat saat koneksi tersedia, dengan mekanisme retry dan antrian offline.
* **Dashboard/Server Pusat:** Aplikasi web (dapat di-deploy on-premise) dengan database terpusat, menyediakan seluruh modul manajemen pada Bab 7.

### 8.2 Alur Data Ringkas
1. Siswa login di device (manual atau tap RFID).
2. Siswa memilih challenge & mortise terpasang (dikonfirmasi via label/kode).
3. Sesi berjalan: sensor proximity, mic, dan sensor tambahan membaca data secara real-time; layar menampilkan timer dan indikator.
4. Sesi berakhir (berhasil/timeout); hasil dihitung dan disimpan ke local storage device.
5. Device mengirim data ke dashboard pusat saat koneksi tersedia (atau menunggu ekspor manual pada mode air-gapped).
6. Dashboard memperbarui riwayat nilai, leaderboard, dan laporan terkait.

---

## 9. Estimasi Komponen (Bill of Materials) Per Unit POC
*Estimasi berikut bersifat indikatif untuk perencanaan anggaran awal PoC dan perlu divalidasi ulang terhadap harga pasar aktual serta ketersediaan komponen lokal saat pengadaan.*

| Komponen | Fungsi | Estimasi Harga (Rp) | Qty | Subtotal (Rp) |
| :--- | :--- | :--- | :--- | :--- |
| Raspberry Pi 4/5 (4GB) | Kontroler utama | 1.100.000 | 1 | 1.100.000 |
| Capacitive touchscreen 7"-10" | Layar antarmuka siswa | 1.500.000 | 1 | 1.500.000 |
| Inductive proximity sensor | Deteksi status bolt/latch | 150.000 | 1 | 150.000 |
| USB/Condenser microphone eksternal | Monitoring desibel | 250.000 | 1 | 250.000 |
| Reed switch/magnetic door sensor | Deteksi pintu terbuka | 50.000 | 1 | 50.000 |
| Accelerometer/IMU (MPU6050) | Deteksi getaran teknik | 40.000 | 1 | 40.000 |
| RFID/NFC reader + kartu | Login siswa | 180.000 | 1 | 180.000 |
| Mortise pintu (changeable) | Media latihan utama | 300.000 | 3 varian | 900.000 |
| Rangka miniatur pintu + kusen | Struktur fisik device (custom) | 2.000.000 | 1 | 2.000.000 |
| Speaker/buzzer + indikator LED | Umpan balik audio/visual | 100.000 | 1 | 100.000 |
| Enclosure, kabel, PSU, hardware | Perakitan & pengaman komponen | 500.000 | 1 | 500.000 |
| **Total per unit (estimasi)** | | | | **≈ Rp 6.770.000** |

*Catatan: harga di luar biaya pengembangan software (dashboard, firmware device), fabrikasi custom mortise premium, dan biaya instalasi/pelatihan penggunaan di lokasi instansi.*

---

## 10. Roadmap Pengembangan Lanjutan

### 10.1 Fase 2
* Contact/piezo microphone pada kusen untuk analisis pola klik pin yang lebih presisi (masih non-invasif terhadap mortise).
* Modul anti-cheat berbasis kamera/light sensor.
* Kompetisi multi-device real-time dengan leaderboard lintas unit dalam satu jaringan lokal.
* Laporan analitik lanjutan: prediksi kesiapan sertifikasi berdasarkan tren performa historis.

### 10.2 Fase 3 (Memerlukan Modifikasi Internal Mortise)
* Sensor per-pin (hall effect/optical di tiap pin) untuk telemetri detail proses picking secara real-time. Memerlukan mortise custom yang dibongkar/dirancang ulang, di luar cakupan PoC saat ini.
* Mode replay/analisis gerakan pick berbasis data pin-level untuk keperluan pelatihan teknik lanjutan.

---

## 11. Metrik Keberhasilan (KPI)

| Metrik | Target Indikatif |
| :--- | :--- |
| Akurasi deteksi status kunci (proximity) | ≥ 99% konsisten pada 100 percobaan berturut-turut |
| Latensi pencatatan waktu buka kunci | < 200 ms dari perubahan state proximity |
| Tingkat keberhasilan sinkronisasi data | ≥ 98% sesi tersinkron otomatis dalam 24 jam |
| Kepuasan pengguna instruktur (survei pilot)| ≥ 4/5 |
| Waktu penggantian mortise (changeable) | < 2 menit tanpa alat khusus |

---

## 12. Risiko & Mitigasi

| Risiko | Dampak | Mitigasi |
| :--- | :--- | :--- |
| Noise lingkungan bervariasi antar lokasi instansi | Threshold desibel tidak akurat | Kalibrasi baseline otomatis di awal setiap sesi. |
| Keterbatasan jaringan/air-gapped di fasilitas | Data nilai tidak tersinkron | Local storage + mode ekspor manual via USB. |
| Kecurangan siswa (menarik bolt tanpa membuka) | Skor tidak mencerminkan kemampuan asli | Kombinasi proximity + reed switch pintu sebagai validasi ganda. |
| Sensitivitas data pelatihan instansi intelijen | Risiko kebocoran data | Opsi deployment on-premise, enkripsi at-rest & in-transit, RBAC, audit log. |
| Keausan mortise akibat pemakaian intensif | Biaya penggantian & downtime | Desain mounting quick-release, stok mortise cadangan per tingkat kesulitan. |

---

## 13. Catatan Penutup
Dokumen ini merupakan draft awal PRD untuk tahap Proof of Concept dan akan diperbarui seiring hasil uji coba prototipe pertama, masukan dari calon pengguna (instruktur/instansi pilot), serta validasi teknis terhadap sensor dan komponen yang dipilih.

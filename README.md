#  TikTok Live Monitor və Recorder

TikTok canlı yayımlarını avtomatik izləmək, event-ləri toplamaq və canlı videonu hissələrə bölərək saxlamaq üçün hazırlanmış **Python əsaslı monitor və recorder sistemi**.

Bu layihə TikTok hesabı canlıya başlayan kimi:

- canlıya qoşulur
- event-ləri qeyd edir
- videonu seqmentlərə bölüb saxlayır
- sessiya məlumatlarını strukturlaşdırılmış şəkildə yazır
- recorder dayansa belə yenidən başlatmağa çalışır

---

## ✨ Xüsusiyyətlər

- 🔴 TikTok hesabının live statusunu davamlı yoxlayır
- 🎥 Canlı yayımı avtomatik yazır
- 🧩 Videonu hissələrə (`live_001.mp4`, `live_002.mp4` və s.) bölür
- 💬 Şərhləri (`comments`) saxlayır
- 🎁 Hədiyyələri (`gifts`) saxlayır
- ❤️ Like event-lərini saxlayır
- ➕ Join event-lərini saxlayır
- 👤 Follow event-lərini saxlayır
- 📤 Share event-lərini saxlayır
- 📄 JSON / CSV / TXT çıxış faylları yaradır
- 🔁 Recorder crash olsa auto-restart etməyə çalışır
- 🌐 Proxy dəstəyi var
- 🍪 `sessionid` cookie dəstəyi var
- ⚙️ `config.json` və environment variable dəstəyi var
- 🐧 Ubuntu / Linux serverlər üçün uyğundur

---

## 📌 Nə üçün istifadə olunur?

Bu layihə aşağıdakı məqsədlər üçün faydalıdır:

- TikTok live monitorinq
- canlı yayım analizi
- user davranışlarının toplanması
- sonradan data analizi
- comment / gift / like statistikası
- stream arxivləmə

---

# 📦 Tələblər

Sistem:

- Ubuntu 20.04+
- Debian / Kali / Linux Mint / digər Linux distributivləri
- Python 3.10+
- `ffmpeg`
- `yt-dlp`

Python kitabxanaları:

- `TikTokLive`

---

# ⚙️ Ubuntu / Linux Quraşdırma

## 1) Sistemi yenilə

```bash
sudo apt update && sudo apt upgrade -y
```

## 2) Lazımi paketləri quraşdır

```bash
sudo apt install -y python3 python3-pip python3-venv ffmpeg git
```

## 3) Repo-nu klonla

```bash
git clone https://github.com/f1r10/0s1r1s.git
cd 0s1r1s
```



## 4) Virtual environment yarat

```bash
python3 -m venv venv
source venv/bin/activate
```

## 5) Python dependency-ləri quraşdır

```bash
pip install --upgrade pip
pip install -U TikTokLive yt-dlp
```

---

# 📁 Layihə strukturu

```bash
.
├── osiris.py
├── config.json          # optional
├── README.md
├── output/
│   ├── monitor.log
│   └── username/
│       └── 2026-04-09/
│           └── 14-32-10/
│               ├── videos/
│               │   ├── live_001.mp4
│               │   ├── live_002.mp4
│               │   └── live_003.mp4
│               └── data/
│                   ├── meta.json
│                   ├── events.jsonl
│                   ├── comments.csv
│                   ├── comments.txt
│                   ├── gifts.csv
│                   ├── joins.csv
│                   ├── likes.csv
│                   ├── follows.csv
│                   └── shares.csv
└── venv/
```

---

# ▶️ İstifadə

## Sadə işə salma

```bash
python3 osiris.py username
```

və ya

```bash
python3 osiris.py @username
```

### Nümunə

```bash
python3 osiris.py mpl.id.official
```

və ya

```bash
python3 osiris.py @mpl.id.official
```

---


# Proxy istifadə
```bash
export TIKTOK_WEB_PROXY=http://127.0.0.1:8080
export TIKTOK_WS_PROXY=socks5://127.0.0.1:9050
python3 osiris.py username
```

---

# 🍪 Session Cookie istifadəsi

Bəzi hallarda `sessionid` cookie istifadə etmək faydalı ola bilər.

```bash
export TIKTOK_SESSION_ID=YOUR_SESSION_ID
python3 osiris.py username
```

və ya `config.json` daxilində:

```json
{
  "TIKTOK_SESSION_ID": "YOUR_SESSION_ID"
}
```

---

# Nümunə işə salma

```bash
python3 osiris.py @exampleuser
```



#  Arxa planda işlətmək

## `nohup` ilə

```bash
nohup python3 osiris.py username > run.log 2>&1 &
```

### Prosesi yoxlamaq

```bash
ps aux | grep osiris.py
```

### Dayandırmaq

```bash
pkill -f "python3 osiris.py username"
```

---

## `screen` ilə

Əgər serverdə uzun müddət açıq saxlamaq istəyirsənsə:

```bash
sudo apt install -y screen
screen -S tiktok-monitor
source venv/bin/activate
python3 osiris.py username
```

### Screen-dən çıxmaq

```text
Ctrl + A, sonra D
```

### Yenidən qoşulmaq

```bash
screen -r tiktok-monitor
```

---

#  `systemd` Service ilə avtomatik başlatmaq

Server restart olsa belə proqram avtomatik açılsın istəyirsənsə, `systemd` istifadə et.

## 1) Service faylı yarat

```bash
sudo nano /etc/systemd/system/osiris.service
```

Aşağıdakı məzmunu yapışdır:

```ini
[Unit]
Description=TikTok Live Monitor
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/YOUR_REPO
Environment="PATH=/home/ubuntu/YOUR_REPO/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/ubuntu/YOUR_REPO/venv/bin/python /home/ubuntu/YOUR_REPO/osiris.py username
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

> `ubuntu`, repo yolu və `username` hissəsini öz sisteminə uyğun dəyiş.

## 2) Service-i aktiv et

```bash
sudo systemctl daemon-reload
sudo systemctl enable osiris.service
sudo systemctl start osiris.service
```

## 3) Status yoxla

```bash
sudo systemctl status osiris.service
```

## 4) Loglara bax

```bash
journalctl -u osiris.service -f
```


# ❗ Mümkün problemlər və həllər

## 1) `TikTokLive` tapılmadı

### Xəta

```bash
ImportError: No module named TikTokLive
```

### Həll

```bash
source venv/bin/activate
pip install -U TikTokLive yt-dlp
```

---

## 2) `ffmpeg tapılmadı`

### Həll

```bash
sudo apt install -y ffmpeg
which ffmpeg
```

Əgər tapılırsa, lazım olsa `config.json` içində əl ilə göstər:

```json
{
  "FFMPEG_EXE": "/usr/bin/ffmpeg"
}
```

---

## 3) `yt-dlp tapılmadı`

### Həll

```bash
source venv/bin/activate
pip install -U yt-dlp
```

Yoxla:

```bash
yt-dlp --version
```

---

## 4) Recorder başlayır, sonra dayanır

Mümkün səbəblər:

- TikTok stream tərəfdə problem
- `yt-dlp` format problemi
- `ffmpeg` input stream kəsilməsi
- rate-limit / blok
- TikTok tərəfdə playback məhdudiyyəti

Bu proqram recorder dayanarsa müəyyən limit daxilində yenidən başladmağa çalışır.

---

## 5) `DEVICE_BLOCKED` və ya `RATE_LIMIT`

Bu proqram blok bypass etmir. Belə hallarda sadəcə gözləmə rejiminə keçir və sonra yenidən yoxlayır.

### Tövsiyə olunan yanaşmalar

- yoxlama intervalını artırmaq
- session cookie istifadə etmək
- uyğun proxy istifadə etmək
- eyni anda çox hesab izləməmək
- server IP reputasiyasını nəzərə almaq






#  Sürətli Başlanğıc

Əgər tez başlamaq istəyirsənsə, bunları birbaşa copy-paste et:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv ffmpeg git
git clone https://github.com/ISTIFADECI_ADIN/YOUR_REPO.git
cd YOUR_REPO

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -U TikTokLive yt-dlp

python3 osiris.py username
```

---


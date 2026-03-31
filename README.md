# TikTok Live Comment Listener Python ( OSIRIS )

Bu layihə **TikTok Live yayımına qoşularaq real vaxtda gələn şərhləri oxuyan və terminalda göstərən Python scriptidir**.

Script TikTok Live API wrapper olan **TikTokLive** kitabxanasından istifadə edir və aşağıdakı hadisələri izləyir:

* Yayım otağına qoşulma
* İstifadəçilərin yazdığı şərhlər
* Yayım bağlantısının kəsilməsi

Bu cür scriptlər aşağıdakı məqsədlər üçün istifadə oluna bilər:

* TikTok Live analitikası
* OSINT və sosial media monitorinqi
* Chat analiz sistemləri
* AI əsaslı mesaj analizi
* Live stream moderasiya alətləri

---

# Funksiyalar

Bu proqram aşağıdakı funksiyaları yerinə yetirir:

* TikTok live stream-ə qoşulur
* Yayım otağının ID məlumatını göstərir
* Real vaxtda gələn şərhləri oxuyur
* Şərh yazan istifadəçinin nickname-ni göstərir
* Yayım bağlantısı kəsiləndə xəbər verir

---

# İş prinsipi

Script TikTok Live serverinə websocket bağlantısı yaradır və aşağıdakı event-ləri dinləyir:

### ConnectEvent

Yayım otağına qoşulduqda işləyir.

### CommentEvent

Yeni şərh gəldikdə işləyir.

### DisconnectEvent

Bağlantı kəsildikdə işləyir.

---

# Tələblər

Proqramın işləməsi üçün aşağıdakılar lazımdır:

* Python 3.9+
* TikTokLive kitabxanası

---

# Qurulma

## 1. Repository klon edin

```bash
git clone https://github.com/USERNAME/tiktok-live-listener.git
cd tiktok-live-listener
```

## 2. Virtual environment yaradın

Linux / Mac

```bash
python3 -m venv venv
source venv/bin/activate
```

Windows

```powershell
python -m venv venv
venv\Scripts\activate
```

## 3. Lazımi kitabxanaları yükləyin

```bash
pip install TikTokLive
```

---

# İstifadə



```python
    python main2.py username
    python main2.py @username


```
Xüsusiyyətlər:
- username-ə görə avtomatik qovluq yaradır
- output/<username>/<YYYY-MM-DD>/<HH-MM-SS>/ strukturu ilə saxlayır
- videos/ altında 1 dəqiqəlik MP4 seqmentləri yaradır
- data/ altında comment, gift, join və digər event fayllarını saxlayır
- uzunmüddətli monitor rejimində işləyir
- xətalarda geri-çəkilmə (backoff) və təkrar cəhd edir
- recorder prosesi gözlənilmədən dayanarsa onu yenidən başlada bilir
burada:

---

## Scripti işə salmaq

```bash
python main2.py "username"
```

---

# Nümunə Output

```
✅ Bağlandı! Yayımçı: @asi_live1
Otaq ID: 123456789

💬 user1: salam
💬 user2: necəsiz
💬 user3: super yayım
```

---

# Layihə strukturu

```
tiktok-live-listener
│
├── main2.py
├── README.md
```

---

# Mümkün inkişaflar

Bu layihə gələcəkdə aşağıdakı funksiyalarla genişləndirilə bilər:

* Şərhləri fayla yazmaq
* MongoDB və ya MySQL bazaya yazmaq
* AI ilə sentiment analizi
* spam filter
* avtomatik cavab sistemi
* OBS və stream overlay inteqrasiyası

---

# Lisenziya

MIT License

---

# Müəllif

GitHub: f1r10

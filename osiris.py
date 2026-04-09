from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


try:
    from TikTokLive import TikTokLiveClient
    from TikTokLive.events import (
        ConnectEvent,
        DisconnectEvent,
        LiveEndEvent,
        CommentEvent,
        GiftEvent,
        LikeEvent,
        FollowEvent,
        ShareEvent,
        JoinEvent,
    )
except ImportError as imp_err:
    print(
        "[KRİTİK] TikTokLive kitabxanası tapılmadı.\n"
        "Quraşdırma: pip install -U TikTokLive yt-dlp\n"
        f"Detallar: {imp_err}"
    )
    sys.exit(1)


# ===========================================================================
# KONFİQURASİYA
# ===========================================================================

def _config_yukle(config_fayli: str = "config.json") -> dict:
    yol = Path(config_fayli)
    if not yol.exists():
        return {}
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except Exception:
        return {}


_CONFIG = _config_yukle()


def _conf(ad: str, default=None):
    return os.environ.get(ad) or _CONFIG.get(ad) or default


CHECK_INTERVAL_SECONDS   = int(_conf("CHECK_INTERVAL_SECONDS", 20))
OUTPUT_DIR               = Path(_conf("OUTPUT_DIR", "output"))
VIDEO_SEGMENT_SECONDS    = int(_conf("VIDEO_SEGMENT_SECONDS", 60))
YT_DLP_CMD               = str(_conf("YT_DLP_CMD", "yt-dlp"))
FFMPEG_EXE               = _conf("FFMPEG_EXE")
TIKTOK_PROXY             = _conf("TIKTOK_PROXY")
TIKTOK_WEB_PROXY         = _conf("TIKTOK_WEB_PROXY")
TIKTOK_WS_PROXY          = _conf("TIKTOK_WS_PROXY")
TIKTOK_SESSION_ID        = _conf("TIKTOK_SESSION_ID")

MIN_BACKOFF              = float(_conf("MIN_BACKOFF", 10))
MAX_BACKOFF              = float(_conf("MAX_BACKOFF", 300))
BACKOFF_FACTOR           = float(_conf("BACKOFF_FACTOR", 2))
DEVICE_BLOCK_WAIT        = float(_conf("DEVICE_BLOCK_WAIT", 300))
RECORDER_RESTART_WAIT    = float(_conf("RECORDER_RESTART_WAIT", 5))
RECORDER_START_DELAY     = float(_conf("RECORDER_START_DELAY", 3))
RECORDER_EARLY_EXIT_WAIT = float(_conf("RECORDER_EARLY_EXIT_WAIT", 8))
RECORDER_MAX_RESTARTS    = int(_conf("RECORDER_MAX_RESTARTS", 10))


# ===========================================================================
# LOGGING
# ===========================================================================

def logger_qur(log_fayli: Optional[Path] = None) -> logging.Logger:
    log = logging.getLogger("tiktok_live_monitor")
    log.setLevel(logging.DEBUG)
    log.propagate = False

    if log.handlers:
        return log

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    log.addHandler(stream_handler)

    if log_fayli:
        try:
            log_fayli.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_fayli, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            log.addHandler(file_handler)
        except Exception as exc:
            print(f"[XƏBƏRDARLIQ] Log faylı açıla bilmədi: {exc}")

    return log


OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
log = logger_qur(OUTPUT_DIR / "monitor.log")


# ===========================================================================
# KÖMƏKÇİLƏR
# ===========================================================================

def username_temizle(unique_id: str) -> str:
    return unique_id.strip().lstrip("@").strip()


def ad_temizle(metin: str) -> str:
    return re.sub(r"[^\w\-.]", "_", metin)


def indi() -> str:
    return datetime.now().isoformat()


def tarix_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def saat_str() -> str:
    return datetime.now().strftime("%H-%M-%S")


def qovluq_yarat(yol: Path) -> None:
    yol.mkdir(parents=True, exist_ok=True)


def atomik_json_yaz(yol: Path, data: dict) -> None:
    tmp = yol.with_suffix(yol.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(yol)
    except Exception as exc:
        log.warning(f"JSON yazıla bilmədi [{yol}]: {exc}")


def jsonl_elave_et(yol: Path, data: dict) -> None:
    try:
        with yol.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
    except Exception as exc:
        log.warning(f"JSONL yazı xətası [{yol.name}]: {exc}")


def csv_elave_et(yol: Path, basliq: list[str], satir: list) -> None:
    try:
        fayl_var = yol.exists()
        with yol.open("a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            if not fayl_var:
                writer.writerow(basliq)
            writer.writerow(satir)
    except Exception as exc:
        log.warning(f"CSV yazı xətası [{yol.name}]: {exc}")


def proxy_yoxla(proxy_url: Optional[str], ad: str) -> Optional[str]:
    if not proxy_url:
        return None
    protokollar = ("http://", "https://", "socks4://", "socks5://")
    if not proxy_url.startswith(protokollar):
        log.warning(f"{ad} proxy URL düzgün deyil: {proxy_url}")
        return None
    return proxy_url


def ffmpeg_tap() -> Optional[Path]:
    if FFMPEG_EXE:
        p = Path(FFMPEG_EXE)
        if p.is_file():
            return p
        log.warning(f"FFMPEG_EXE göstərilib, amma tapılmadı: {p}")
    path_ffmpeg = shutil.which("ffmpeg")
    if path_ffmpeg:
        return Path(path_ffmpeg)
    return None


def ytdlp_var() -> bool:
    try:
        result = subprocess.run(
            [YT_DLP_CMD, "--version"],
            capture_output=True, text=True, timeout=10, shell=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def block_xetasi(e: Exception) -> bool:
    s = str(e).upper()
    return "DEVICE_BLOCKED" in s or "DEVICEBLOCKED" in s or "RATE_LIMIT" in s


def jitter_sleep_muddeti(base: float) -> float:
    return base + random.uniform(0.3, 1.7)


def yeni_sessiya_qovlugu(unique_id: str) -> Path:
    temiz = ad_temizle(username_temizle(unique_id))
    root = OUTPUT_DIR / temiz / tarix_str() / saat_str()
    qovluq_yarat(root / "videos")
    qovluq_yarat(root / "data")
    return root


# ===========================================================================
# USER MƏLUMAT OXUMA  ← YENİLƏNDİ
# ===========================================================================

def _str(v) -> Optional[str]:
    """Boş string və None-u None-a çevirir."""
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _proto_field(obj, *adlar):
    """
    Bir proto/dataclass obyektindən sırayla field adlarını yoxlayır,
    ilk boş olmayan dəyəri qaytarır.
    """
    for ad in adlar:
        try:
            v = _str(getattr(obj, ad, None))
            if v:
                return v
        except Exception:
            pass
    return None


def user_melumat(event) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    TikTokLive-in müxtəlif versiyalarında user məlumatı fərqli
    field-lərdə saxlanılır. Bu funksiya bütün məlum yerlərə baxır.

    Qaytarır: (user_id, unique_id, nickname)

    Axtarış sırası:
      1. event.user_info      — köhnə versiyalarda əsas yer
      2. event.sender         — bəzi event tipləri
      3. event.from_user      — bəzi event tipləri
      4. event.user           — wrapper, crash riski var, try/except ilə
      5. event-in özündə      — bəzən düz field olaraq mövcuddur
    """
    kandidatlar = []

    # 1–3: birbaşa proto field-lər (wrapper yoxdur, crash riski az)
    for field_adi in ("user_info", "sender", "from_user"):
        try:
            obj = getattr(event, field_adi, None)
            if obj is not None:
                kandidatlar.append(obj)
        except Exception:
            pass

    # 4: event.user — wrapper, crash edə bilər, amma cəhd edirik
    try:
        u = event.user
        if u is not None:
            kandidatlar.append(u)
    except Exception:
        pass

    # 5: bəzi eventlərdə user_id/unique_id birbaşa event-də olur
    kandidatlar.append(event)

    # Hər kandidatdan oxu, ilk dolu dəyərləri götür
    user_id   = None
    unique_id = None
    nickname  = None

    for obj in kandidatlar:
        if user_id is None:
            user_id = _proto_field(obj, "user_id", "userId", "uid")
        if unique_id is None:
            unique_id = _proto_field(obj, "unique_id", "uniqueId", "display_id")
        if nickname is None:
            nickname = _proto_field(
                obj,
                "nick_name", "nickname", "nickName",  # bütün variant yazılışlar
                "display_name", "displayName",
            )
        if user_id and unique_id and nickname:
            break

    return user_id, unique_id, nickname


# ===========================================================================
# CLIENT
# ===========================================================================

def client_yarat(unique_id: str) -> TikTokLiveClient:
    temiz = username_temizle(unique_id)
    kwargs: dict = {"unique_id": f"@{temiz}"}

    web_proxy = proxy_yoxla(TIKTOK_WEB_PROXY or TIKTOK_PROXY, "WEB")
    ws_proxy  = proxy_yoxla(TIKTOK_WS_PROXY  or TIKTOK_PROXY, "WS")
    if web_proxy:
        kwargs["web_proxy"] = web_proxy
    if ws_proxy:
        kwargs["ws_proxy"] = ws_proxy

    try:
        client = TikTokLiveClient(**kwargs)
    except TypeError:
        client = TikTokLiveClient(unique_id=f"@{temiz}")

    if TIKTOK_SESSION_ID:
        try:
            client.web.cookies.set("sessionid", TIKTOK_SESSION_ID)
        except Exception:
            pass

    return client


# ===========================================================================
# RECORDER PROSESİ
# ===========================================================================

class RecorderHandle:
    def __init__(self, ytdlp: subprocess.Popen, ffmpeg: subprocess.Popen):
        self.ytdlp      = ytdlp
        self.ffmpeg     = ffmpeg
        self.started_at = time.time()

    def alive(self) -> bool:
        return (self.ytdlp.poll() is None) and (self.ffmpeg.poll() is None)

    def runtime(self) -> float:
        return time.time() - self.started_at

    def status(self) -> dict:
        return {
            "ytdlp_returncode":  self.ytdlp.poll(),
            "ffmpeg_returncode": self.ffmpeg.poll(),
            "runtime_seconds":   round(self.runtime(), 2),
        }


def recorder_baslat(
    unique_id: str, videos_dir: Path, ffmpeg_yolu: Optional[Path]
) -> Optional[RecorderHandle]:

    if ffmpeg_yolu is None:
        log.warning("ffmpeg tapılmadı. Video yazılmayacaq.")
        return None
    if not ytdlp_var():
        log.warning("yt-dlp tapılmadı. Video yazılmayacaq.")
        return None

    temiz         = username_temizle(unique_id)
    canli_url     = f"https://www.tiktok.com/@{temiz}/live"
    output_pattern = str(videos_dir / "live_%03d.mp4")
    ffmpeg_dir    = str(ffmpeg_yolu.parent)

    ytdlp_cmd = [
        YT_DLP_CMD,
        "--ffmpeg-location", ffmpeg_dir,
        "--no-live-from-start",
        "--no-part",
        "--hls-use-mpegts",
        "--no-warnings",
        "-o", "-",
        canli_url,
    ]

    ffmpeg_cmd = [
        str(ffmpeg_yolu),
        "-hide_banner",
        "-loglevel",  "warning",
        "-fflags",    "+genpts",
        "-i",         "pipe:0",
        "-map",       "0:v?",
        "-map",       "0:a?",
        "-c",         "copy",
        "-f",         "segment",
        "-segment_time",     str(VIDEO_SEGMENT_SECONDS),
        "-reset_timestamps", "1",
        "-segment_format",   "mp4",
        output_pattern,
    ]

    log.debug("yt-dlp: " + " ".join(ytdlp_cmd))
    log.debug("ffmpeg: " + " ".join(ffmpeg_cmd))

    try:
        ytdlp_proc = subprocess.Popen(
            ytdlp_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            bufsize=0,
        )
        ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=ytdlp_proc.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=False,
            bufsize=0,
        )
        if ytdlp_proc.stdout:
            ytdlp_proc.stdout.close()

        handle = RecorderHandle(ytdlp_proc, ffmpeg_proc)
        log.info(f"Recorder başladı → {videos_dir}")
        return handle

    except Exception as exc:
        log.error(f"Recorder başlaya bilmədi: {exc}")
        return None


def proses_dayandir(
    proc: Optional[subprocess.Popen], ad: str, timeout: int = 6
) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=timeout)
        log.debug(f"{ad} terminate ilə bağlandı")
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
            proc.wait(timeout=3)
            log.debug(f"{ad} kill ilə bağlandı")
        except Exception:
            pass
    except Exception:
        pass


def _stderr_oxu_ve_logla(proc: Optional[subprocess.Popen], ad: str) -> None:
    if proc is None:
        return
    try:
        if proc.poll() is not None and proc.stderr:
            err = proc.stderr.read()
            if err:
                try:
                    metn = err.decode("utf-8", errors="ignore").strip()
                except Exception:
                    metn = str(err)
                if metn:
                    log.warning(f"{ad} stderr:\n{metn[-3000:]}")
    except Exception:
        pass


def recorder_dayandir(handle: Optional[RecorderHandle]) -> None:
    if handle is None:
        return
    _stderr_oxu_ve_logla(handle.ytdlp,  "yt-dlp")
    _stderr_oxu_ve_logla(handle.ffmpeg, "ffmpeg")
    proses_dayandir(handle.ytdlp,  "yt-dlp")
    proses_dayandir(handle.ffmpeg, "ffmpeg", timeout=8)


def video_fayllari(videos_dir: Path) -> list[Path]:
    return sorted(videos_dir.glob("live_*.mp4"))


# ===========================================================================
# DİAQNOSTİKA — event strukturunu loglayır (debug üçün)
# ===========================================================================

def event_debug_logla(event, ad: str) -> None:
    """
    Hər yeni event tipinin strukturunu bir dəfə DEBUG səviyyəsində loglar.
    Bu, gələcəkdə hansı field-lərin mövcud olduğunu anlamağa kömək edir.
    """
    try:
        fields = {}
        for attr in dir(event):
            if attr.startswith("_"):
                continue
            try:
                v = getattr(event, attr, None)
                if callable(v):
                    continue
                fields[attr] = str(v)[:120]
            except Exception:
                fields[attr] = "<oxuna bilmir>"
        log.debug(f"[{ad}] event strukturu: {json.dumps(fields, ensure_ascii=False)}")
    except Exception:
        pass


_debug_loglanmis: set[str] = set()


def bir_defe_debug(event, ad: str) -> None:
    if ad not in _debug_loglanmis:
        _debug_loglanmis.add(ad)
        event_debug_logla(event, ad)


# ===========================================================================
# BİR SESSİYA
# ===========================================================================

async def bir_sessiya_isle(unique_id: str, ffmpeg_yolu: Optional[Path]) -> str:
    temiz  = username_temizle(unique_id)
    client = client_yarat(temiz)

    sessiya_dir = yeni_sessiya_qovlugu(temiz)
    videos_dir  = sessiya_dir / "videos"
    data_dir    = sessiya_dir / "data"

    meta_json    = data_dir / "meta.json"
    events_jsonl = data_dir / "events.jsonl"
    comments_csv = data_dir / "comments.csv"
    gifts_csv    = data_dir / "gifts.csv"
    joins_csv    = data_dir / "joins.csv"
    likes_csv    = data_dir / "likes.csv"
    follows_csv  = data_dir / "follows.csv"
    shares_csv   = data_dir / "shares.csv"
    comments_txt = data_dir / "comments.txt"

    meta: dict = {
        "username":              temiz,
        "started_at":            indi(),
        "session_dir":           str(sessiya_dir),
        "videos_dir":            str(videos_dir),
        "data_dir":              str(data_dir),
        "video_segment_seconds": VIDEO_SEGMENT_SECONDS,
        "connected":             False,
        "recorder_started":      False,
        "result":                None,
    }
    atomik_json_yaz(meta_json, meta)

    recorder: Optional[RecorderHandle] = None
    stop_flag     = False
    seen_comments: set[tuple] = set()

    # -----------------------------------------------------------------------
    async def recorder_watchdog() -> None:
        nonlocal recorder, stop_flag
        restart_count = 0

        while not stop_flag:
            await asyncio.sleep(5)
            if stop_flag:
                break
            if recorder is None:
                continue
            if recorder.alive():
                continue

            status = recorder.status()
            log.warning(f"Recorder dayandı: {status}")
            _stderr_oxu_ve_logla(recorder.ytdlp,  "yt-dlp")
            _stderr_oxu_ve_logla(recorder.ffmpeg, "ffmpeg")
            recorder_dayandir(recorder)

            if recorder.runtime() < 10:
                log.warning(
                    f"Recorder çox tez dayandı. "
                    f"{RECORDER_EARLY_EXIT_WAIT:.1f}s sonra yenidən cəhd ediləcək..."
                )
                await asyncio.sleep(RECORDER_EARLY_EXIT_WAIT)

            restart_count += 1
            if restart_count > RECORDER_MAX_RESTARTS:
                log.error("Recorder çox dəfə dayandı. Sonsuz restart qarşısı alındı.")
                recorder = None
                continue

            await asyncio.sleep(RECORDER_RESTART_WAIT)
            recorder = recorder_baslat(temiz, videos_dir, ffmpeg_yolu)

            if recorder is None:
                log.warning("Recorder yenidən başlatmaq mümkün olmadı.")
            else:
                meta["recorder_restarted_at"]  = indi()
                meta["recorder_restart_count"] = restart_count
                atomik_json_yaz(meta_json, meta)
                log.info(f"Recorder yenidən başladıldı. restart_count={restart_count}")

    watchdog_task = asyncio.create_task(recorder_watchdog())

    def hadisə_yaz(data: dict) -> None:
        jsonl_elave_et(events_jsonl, data)

    # -----------------------------------------------------------------------
    @client.on(ConnectEvent)
    async def on_connect(event: ConnectEvent):
        nonlocal recorder
        meta["connected"] = True
        meta["room_id"]   = str(getattr(client, "room_id", ""))
        atomik_json_yaz(meta_json, meta)

        hadisə_yaz({
            "type":     "connect",
            "time":     indi(),
            "room_id":  str(getattr(client, "room_id", "")),
            "username": temiz,
        })
        log.info(f"QOŞULDU → @{temiz} | room_id={getattr(client, 'room_id', '')}")

        if recorder is None:
            await asyncio.sleep(RECORDER_START_DELAY)
            recorder = recorder_baslat(temiz, videos_dir, ffmpeg_yolu)
            if recorder:
                meta["recorder_started"]    = True
                meta["recorder_started_at"] = indi()
                atomik_json_yaz(meta_json, meta)
                log.info("Recorder connect-dən sonra uğurla başladıldı.")
            else:
                log.warning("Recorder start alınmadı.")

    # -----------------------------------------------------------------------
    @client.on(CommentEvent)
    async def on_comment(event: CommentEvent):
        try:
            bir_defe_debug(event, "CommentEvent")
            user_id, u_id, nickname = user_melumat(event)
            comment = getattr(event, "comment", "")
            created = getattr(event, "create_time", None)
            key = (user_id, u_id, comment, str(created))
            if key in seen_comments:
                return
            seen_comments.add(key)

            data = {
                "type":        "comment",
                "time":        indi(),
                "user_id":     user_id,
                "unique_id":   u_id,
                "nickname":    nickname,
                "comment":     comment,
                "create_time": str(created) if created else None,
            }
            hadisə_yaz(data)
            csv_elave_et(
                comments_csv,
                ["time", "user_id", "unique_id", "nickname", "comment", "create_time"],
                [data["time"], user_id, u_id, nickname, comment, data["create_time"]],
            )
            try:
                with comments_txt.open("a", encoding="utf-8") as f:
                    f.write(f"[{data['time']}] {nickname} ({u_id}): {comment}\n")
            except Exception:
                pass
        except Exception as exc:
            log.warning(f"on_comment xətası: {exc}")

    # -----------------------------------------------------------------------
    @client.on(GiftEvent)
    async def on_gift(event: GiftEvent):
        try:
            bir_defe_debug(event, "GiftEvent")
            try:
                if getattr(event.gift, "streakable", False) and getattr(event, "streaking", True):
                    return
            except Exception:
                pass

            user_id, u_id, nickname = user_melumat(event)
            repeat_count  = getattr(event, "repeat_count",  1)
            diamond_count = getattr(event.gift, "diamond_count", None)
            try:
                total_diamond = (diamond_count or 0) * (repeat_count or 1)
            except Exception:
                total_diamond = None

            data = {
                "type":          "gift",
                "time":          indi(),
                "user_id":       user_id,
                "unique_id":     u_id,
                "nickname":      nickname,
                "gift_id":       getattr(event.gift, "id",         None),
                "gift_name":     getattr(event.gift, "name",       None),
                "repeat_count":  repeat_count,
                "diamond_count": diamond_count,
                "total_diamond": total_diamond,
                "streakable":    getattr(event.gift, "streakable", None),
            }
            hadisə_yaz(data)
            csv_elave_et(
                gifts_csv,
                [
                    "time", "user_id", "unique_id", "nickname",
                    "gift_id", "gift_name", "repeat_count",
                    "diamond_count", "total_diamond", "streakable",
                ],
                [
                    data["time"],         data["user_id"],    data["unique_id"],
                    data["nickname"],     data["gift_id"],    data["gift_name"],
                    data["repeat_count"], data["diamond_count"],
                    data["total_diamond"], data["streakable"],
                ],
            )
        except Exception as exc:
            log.warning(f"on_gift xətası: {exc}")

    # -----------------------------------------------------------------------
    @client.on(JoinEvent)
    async def on_join(event: JoinEvent):
        try:
            bir_defe_debug(event, "JoinEvent")
            user_id, u_id, nickname = user_melumat(event)
            data = {
                "type":      "join",
                "time":      indi(),
                "user_id":   user_id,
                "unique_id": u_id,
                "nickname":  nickname,
            }
            hadisə_yaz(data)
            csv_elave_et(
                joins_csv,
                ["time", "user_id", "unique_id", "nickname"],
                [data["time"], user_id, u_id, nickname],
            )
        except Exception as exc:
            log.warning(f"on_join xətası: {exc}")

    # -----------------------------------------------------------------------
    @client.on(LikeEvent)
    async def on_like(event: LikeEvent):
        try:
            bir_defe_debug(event, "LikeEvent")
            user_id, u_id, nickname = user_melumat(event)
            data = {
                "type":      "like",
                "time":      indi(),
                "user_id":   user_id,
                "unique_id": u_id,
                "nickname":  nickname,
                "count":     getattr(event, "count", None),
                "total":     getattr(event, "total", None),
            }
            hadisə_yaz(data)
            csv_elave_et(
                likes_csv,
                ["time", "user_id", "unique_id", "nickname", "count", "total"],
                [data["time"], user_id, u_id, nickname, data["count"], data["total"]],
            )
        except Exception as exc:
            log.warning(f"on_like xətası: {exc}")

    # -----------------------------------------------------------------------
    @client.on(FollowEvent)
    async def on_follow(event: FollowEvent):
        try:
            bir_defe_debug(event, "FollowEvent")
            user_id, u_id, nickname = user_melumat(event)
            data = {
                "type":      "follow",
                "time":      indi(),
                "user_id":   user_id,
                "unique_id": u_id,
                "nickname":  nickname,
            }
            hadisə_yaz(data)
            csv_elave_et(
                follows_csv,
                ["time", "user_id", "unique_id", "nickname"],
                [data["time"], user_id, u_id, nickname],
            )
        except Exception as exc:
            log.warning(f"on_follow xətası: {exc}")

    # -----------------------------------------------------------------------
    @client.on(ShareEvent)
    async def on_share(event: ShareEvent):
        try:
            bir_defe_debug(event, "ShareEvent")
            user_id, u_id, nickname = user_melumat(event)
            data = {
                "type":      "share",
                "time":      indi(),
                "user_id":   user_id,
                "unique_id": u_id,
                "nickname":  nickname,
            }
            hadisə_yaz(data)
            csv_elave_et(
                shares_csv,
                ["time", "user_id", "unique_id", "nickname"],
                [data["time"], user_id, u_id, nickname],
            )
        except Exception as exc:
            log.warning(f"on_share xətası: {exc}")

    # -----------------------------------------------------------------------
    @client.on(LiveEndEvent)
    async def on_live_end(event: LiveEndEvent):
        nonlocal stop_flag
        hadisə_yaz({"type": "live_end", "time": indi()})
        log.info(f"CANLI BİTDİ → @{temiz}")
        stop_flag = True

    @client.on(DisconnectEvent)
    async def on_disconnect(event: DisconnectEvent):
        nonlocal stop_flag
        hadisə_yaz({"type": "disconnect", "time": indi()})
        log.info(f"BAĞLANTI KƏSİLDİ → @{temiz}")
        stop_flag = True

    # -----------------------------------------------------------------------
    result = "tamam"
    try:
        log.info(f"Sessiyaya qoşulma cəhdi → @{temiz}")
        await client.connect()
    except Exception as exc:
        if block_xetasi(exc):
            result = "device_blok"
            log.warning(
                "Platforma məhdudiyyəti / rate limit aşkarlandı. "
                "Bypass edilmir, sadəcə gözləmə rejiminə keçilir."
            )
        else:
            result = "xeta"
            log.error(f"Sessiya xətası: {exc}")
    finally:
        stop_flag = True

        watchdog_task.cancel()
        try:
            await watchdog_task
        except (asyncio.CancelledError, Exception):
            pass

        recorder_dayandir(recorder)

        files = video_fayllari(videos_dir)
        meta["finished_at"]    = indi()
        meta["result"]         = result
        meta["segment_count"]  = len(files)
        meta["segments"]       = [f.name for f in files]
        try:
            meta["video_size_bytes"] = sum(f.stat().st_size for f in files)
        except Exception:
            pass
        atomik_json_yaz(meta_json, meta)
        log.info(
            f"Sessiya bağlandı → @{temiz} | "
            f"nəticə={result} | seqment={len(files)}"
        )

    return result


# ===========================================================================
# MONITOR
# ===========================================================================

async def monitor_et(unique_id: str) -> None:
    temiz       = username_temizle(unique_id)
    ffmpeg_yolu = ffmpeg_tap()

    if ffmpeg_yolu is None:
        log.warning("ffmpeg tapılmadı. Yalnız event-lər saxlanacaq.")
    if not ytdlp_var():
        log.warning("yt-dlp tapılmadı. Yalnız event-lər saxlanacaq.")

    backoff     = MIN_BACKOFF
    error_count = 0

    log.info(f"Monitor başladı → @{temiz}")

    while True:
        try:
            client = client_yarat(temiz)
            live   = await client.is_live()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            error_count += 1
            wait_time = min(
                MIN_BACKOFF * (BACKOFF_FACTOR ** (error_count - 1)),
                MAX_BACKOFF,
            )
            wait_time = jitter_sleep_muddeti(wait_time)
            log.warning(f"Canlı statusu yoxlanarkən xəta ({error_count}): {exc}")
            log.info(f"Təkrar cəhd üçün gözləmə: {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
            continue

        error_count = 0
        backoff     = MIN_BACKOFF

        if live:
            log.info(f"@{temiz} hazırda canlıdır. Sessiya başladılır...")
            try:
                result = await bir_sessiya_isle(temiz, ffmpeg_yolu)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                result = "xeta"
                log.error(f"Sessiya gözlənilməz xəta ilə bitdi: {exc}")

            if result == "device_blok":
                wait_time = jitter_sleep_muddeti(DEVICE_BLOCK_WAIT)
                log.warning(f"Məhdudiyyət səbəbilə {wait_time:.1f}s gözlənilir...")
                await asyncio.sleep(wait_time)
            elif result == "xeta":
                backoff   = min(backoff * BACKOFF_FACTOR, MAX_BACKOFF)
                wait_time = jitter_sleep_muddeti(backoff)
                log.info(f"Sessiya xətası sonrası gözləmə: {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
            else:
                await asyncio.sleep(jitter_sleep_muddeti(CHECK_INTERVAL_SECONDS))
        else:
            log.info(f"@{temiz} hazırda canlıda deyil.")
            await asyncio.sleep(jitter_sleep_muddeti(CHECK_INTERVAL_SECONDS))


# ===========================================================================
# GİRİŞ
# ===========================================================================

def istifade_komeyi() -> None:
    print("İstifadə:")
    print("  python osiris.py username")
    print("  python osiris.py @username")
    print()
    print("İstəyə bağlı mühit dəyişənləri:")
    for var in [
        "OUTPUT_DIR", "CHECK_INTERVAL_SECONDS", "VIDEO_SEGMENT_SECONDS",
        "FFMPEG_EXE", "YT_DLP_CMD", "TIKTOK_SESSION_ID",
        "TIKTOK_PROXY", "TIKTOK_WEB_PROXY", "TIKTOK_WS_PROXY",
        "RECORDER_START_DELAY", "RECORDER_EARLY_EXIT_WAIT", "RECORDER_MAX_RESTARTS",
    ]:
        print(f"  {var}")


def signal_qur(loop: asyncio.AbstractEventLoop) -> None:
    if sys.platform == "win32":
        return

    def stop_all() -> None:
        log.info("Dayandırma siqnalı alındı. Çıxılır...")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    try:
        loop.add_signal_handler(signal.SIGINT,  stop_all)
        loop.add_signal_handler(signal.SIGTERM, stop_all)
    except Exception:
        pass


async def esas(unique_id: str) -> None:
    loop = asyncio.get_running_loop()
    signal_qur(loop)
    await monitor_et(unique_id)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        istifade_komeyi()
        sys.exit(1)

    unique_id   = username_temizle(sys.argv[1])
    ffmpeg_path = ffmpeg_tap()
    ytdlp_ok    = ytdlp_var()

    print("=" * 68)
    print("  TikTok Live Monitor və Recorder")
    print("=" * 68)
    print(f"  İzlənən hesab       : @{unique_id}")
    print(f"  Çıxış qovluğu       : {OUTPUT_DIR.resolve()}")
    print(f"  ffmpeg tapıldı      : {'Bəli — ' + str(ffmpeg_path) if ffmpeg_path else 'Xeyr'}")
    print(f"  yt-dlp tapıldı      : {'Bəli' if ytdlp_ok else 'Xeyr'}")
    print(f"  Yoxlama aralığı     : {CHECK_INTERVAL_SECONDS}s")
    print(f"  Video seqmenti      : {VIDEO_SEGMENT_SECONDS}s")
    print(f"  Proxy (web)         : {TIKTOK_WEB_PROXY or TIKTOK_PROXY or 'Yoxdur'}")
    print(f"  Proxy (ws)          : {TIKTOK_WS_PROXY  or TIKTOK_PROXY or 'Yoxdur'}")
    print(f"  Sessiya cookie      : {'Var' if TIKTOK_SESSION_ID else 'Yoxdur'}")
    print("=" * 68)
    print("  Çıxmaq üçün CTRL+C basın")
    print("=" * 68)

    try:
        asyncio.run(esas(unique_id))
    except KeyboardInterrupt:
        log.info("İstifadəçi tərəfindən dayandırıldı.")
    except asyncio.CancelledError:
        log.info("Tapşırıqlar dayandırıldı.")
    except Exception as exc:
        log.critical(f"Proqram kritik xəta ilə dayandı: {exc}")
        sys.exit(1)

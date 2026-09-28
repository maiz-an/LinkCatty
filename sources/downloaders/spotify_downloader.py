import os
import shutil
import sys
import subprocess
import re
import json
import time
import random
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import logging

from yt_dlp import YoutubeDL

from utils.ffmpeg import get_ffmpeg_path
from utils.logger import log_download
from utils.ui import (
    DownloadProgress,
    SilentLogger,
    ask_url,
    card,
    confirm,
    format_eta,
    pause,
    plan_line,
    print_error,
    print_info,
    print_success,
    print_warning,
    result_card,
    section_header,
    show_menu,
    start_spinner,
    stop_spinner,
    strip_ansi,
)

# The lyrics providers log their timeouts ("An error occurred while searching for an LRC ...")
# straight to the console, in the middle of the progress bar. Lyrics are optional, so silence them.
for _noisy in ("syncedlyrics", "spotdl", "urllib3"):
    _log = logging.getLogger(_noisy)
    _log.setLevel(logging.CRITICAL)
    _log.addHandler(logging.NullHandler())
    _log.propagate = False

# ─────────────────────────────────────────────────────────────────────
#  spotdl imports  (metadata only – no official Spotify API ever)
# ─────────────────────────────────────────────────────────────────────
try:
    from spotdl.utils.spotify import SpotifyClient
    from spotdl.types.playlist import Playlist as SpotPlaylist
    from spotdl.types.album   import Album    as SpotAlbum
    _SPOTDL_AVAILABLE = True
except ImportError:
    SpotifyClient = None
    SpotPlaylist  = None
    SpotAlbum     = None
    _SPOTDL_AVAILABLE = False


def _find_spotdl_command() -> list:
    """How to run spotdl, without relying on PATH.

    pip often puts spotdl.exe in a Scripts folder that is not on PATH, so
    run it through the interpreter that is running LinkCatty instead.
    """
    if _SPOTDL_AVAILABLE:
        return [sys.executable, "-m", "spotdl"]
    found = shutil.which("spotdl")
    if found:
        return [found]
    raise RuntimeError(
        "spotdl is not installed for this Python.\n"
        "  → Run: pip install spotdl"
    )


# ─────────────────────────────────────────────────────────────────────
#  Deno – install once per process, never again
# ─────────────────────────────────────────────────────────────────────
_DENO_READY = False


def _deno_already_available() -> bool:
    try:
        from spotdl.utils.deno import get_deno_path
        return get_deno_path() is not None
    except Exception:
        return bool(shutil.which("deno"))


def _ensure_deno(spotdl_cmd: list) -> None:
    global _DENO_READY
    if _DENO_READY:
        return
    if _deno_already_available():
        _DENO_READY = True
        return
    print_info("Deno not found – installing automatically (one-time setup)…")
    try:
        proc = subprocess.Popen(
            [*spotdl_cmd, "--download-deno"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        proc.communicate(input="y\n", timeout=90)
        if _deno_already_available():
            print_success("Deno installed successfully.")
        else:
            print_warning("Deno may not have installed correctly. Some downloads could fail.")
    except Exception as exc:
        print_warning(f"Could not install Deno automatically: {exc}")
    _DENO_READY = True


# ─────────────────────────────────────────────────────────────────────
#  SpotifyClient – FREE MODE ONLY  (SpotipyFree / no credentials)
# ─────────────────────────────────────────────────────────────────────
_FREE_CLIENT = None


def _get_free_client():
    global _FREE_CLIENT
    if _FREE_CLIENT is not None:
        return _FREE_CLIENT

    if SpotifyClient is None:
        return None

    if SpotifyClient._instance is not None:
        try:
            _FREE_CLIENT = SpotifyClient()
            return _FREE_CLIENT
        except Exception:
            pass

    try:
        _FREE_CLIENT = SpotifyClient.init(
            client_id="",
            client_secret="",
            use_official_api=False,
        )
    except Exception:
        try:
            _FREE_CLIENT = SpotifyClient()
        except Exception:
            _FREE_CLIENT = None

    return _FREE_CLIENT


# ─────────────────────────────────────────────────────────────────────
#  Display helpers (all drawn with the shared UI kit in utils/ui.py)
# ─────────────────────────────────────────────────────────────────────

def _display_track_info(info: dict) -> None:
    card("TRACK", [
        ("Title", info.get("title") or "Unknown"),
        ("Artist", info.get("artist") or "Unknown"),
        ("Album", info.get("album")),
    ], icon="🎵")


def _display_album_info(info: dict) -> None:
    count = info.get("track_count")
    card("ALBUM", [
        ("Album", info.get("name") or "Unknown"),
        ("Artist", info.get("artist")),
        ("Tracks", count if count is not None else "Unknown"),
    ], icon="💿")


def _display_playlist_info(info: dict) -> None:
    count = info.get("track_count")
    card("PLAYLIST", [
        ("Name", info.get("name") or "Unknown"),
        ("Author", info.get("author")),
        ("Tracks", count if count is not None else "Unknown"),
    ], icon="📂")


def _display_download_result(item_type: str, name: str | None, out_folder: str,
                              downloaded: int, expected: int,
                              failed_report: str | None,
                              error_breakdown: dict | None = None,
                              elapsed: float | None = None) -> None:
    what = {"track": "Track", "album": "Album", "playlist": "Playlist"}[item_type]
    time_text = format_eta(elapsed) if elapsed is not None else None
    if failed_report is None:
        rows = [(what, name), ("Saved to", out_folder)]
        if item_type != "track":
            rows.append(("Files", f"{downloaded} of {expected}"))
        rows.append(("Time", time_text))
        result_card("ok", "DOWNLOAD COMPLETE", rows)
        return
    rows = [(what, name), ("Saved to", out_folder),
            ("Files", f"{downloaded} of {expected}"),
            ("Missing", max(expected - downloaded, 0)),
            ("Time", time_text)]
    details = [f"{label}  ×{count}"
               for label, count in (error_breakdown or {}).items() if count]
    footer = [("Report", failed_report)]
    json_path = os.path.splitext(failed_report)[0] + ".json"
    if os.path.exists(json_path):
        footer.append(("JSON", json_path))
    result_card("warn" if downloaded else "fail",
                "FINISHED WITH MISSING TRACKS" if downloaded else "DOWNLOAD FAILED",
                rows, details, footer)


# ─────────────────────────────────────────────────────────────────────
#  Error classification
# ─────────────────────────────────────────────────────────────────────

_ERROR_LABELS = {
    "blocked_or_rate_limited": "YouTube is limiting this connection (bot check)",
    "no_match":                "No matching track found (search/lookup miss)",
    "network":                 "Network / timeout error",
    "unavailable":             "Video removed, private, or region-locked",
    "ffmpeg":                  "FFmpeg is missing (spotdl needs it)",
    "runtime":                 "YouTube needs its JavaScript runtime (Deno)",
    "youtube":                 "YouTube download failed",
    "other":                   "Other / unclassified error",
}

# Environment problems: every track fails the same way, so more passes cannot help.
_SYSTEMIC = {"ffmpeg", "runtime"}

# A retry cannot help with these: the setup is broken, the video is gone or nobody has the song.
_NOT_FIXABLE_BY_RETRY = {_ERROR_LABELS["ffmpeg"], _ERROR_LABELS["runtime"], _ERROR_LABELS["unavailable"],
                         _ERROR_LABELS["no_match"]}

# Failures spotdl may still fix (its YouTube Music search finds different videos). It cannot
# get past YouTube's bot check (same yt-dlp underneath) and costs minutes, so it is skipped then.
_SPOTDL_HELPS = {"no_match", "other", "youtube"}


def _classify_error(message: str) -> str:
    msg = (message or "").lower()
    if any(term in msg for term in (
        "ffmpegerror", "ffmpeg is not installed", "ffmpeg not found",
        "ffmpeg executable",
    )):
        return "ffmpeg"
    if any(term in msg for term in (
        "js runtime", "javascript runtime", "no supported javascript",
        "n challenge", "deno",
    )):
        return "runtime"
    if any(term in msg for term in (
        "blocked by youtube", "rate/request limit", "rate limit",
        "429", "too many requests", "sign in to confirm",
    )):
        return "blocked_or_rate_limited"
    if "no results found" in msg or "lookuperror" in msg:
        return "no_match"
    if any(term in msg for term in (
        "timed out", "timeout", "connection", "network", "temporary failure",
        "max retries exceeded",
    )):
        return "network"
    if any(term in msg for term in (
        "unavailable", "private video", "video is no longer available",
        "removed", "copyright",
    )):
        return "unavailable"
    if any(term in msg for term in (
        "yt-dlp download error", "requested format is not available",
        "audioprovidererror", "downloaderror",
    )):
        return "youtube"
    return "other"


def _batch_log_reason(path) -> str | None:
    """The last error spotdl printed into a batch log, as one clean line.

    spotdl crashes (missing FFmpeg, ...) write no per-track error file, so the
    real reason only exists in its output."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()[-8000:]
    except Exception:
        return None
    text = re.sub(r"[│┃┌┐└┘─━╭╮╰╯]", " ", strip_ansi(text))
    text = re.sub(r"[ \t]+", " ", text)
    matches = re.findall(r"(?:FFmpeg is not installed|\b\w*(?:Error|Exception)\b:)[^\n]*", text)
    if not matches:
        return None
    return matches[-1].strip()[:160] or None


def _short(text, width=60) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= width else text[:width - 1] + "…"


# ─────────────────────────────────────────────────────────────────────
#  Adaptive retry-pass strategy
#
#  Pass 1: spotdl's normal, high-confidence settings (youtube-music
#          only, strict filtering).
#  Later passes widen the net progressively for whatever is STILL
#  missing: more audio-provider fallbacks, then loosened filtering.
#
#  max_passes default is now 4 (was 6). In practice passes 5 and 6
#  recovered almost nothing in real runs — the last two provider sets
#  rarely succeed on tracks that YouTube Music + YouTube couldn't
#  match. Users who want them can raise max_retry_passes in config.
# ─────────────────────────────────────────────────────────────────────

_PASS_STRATEGIES = [
    # (audio_providers,                                    dont_filter, thread_divisor, max_retries)
    (["youtube-music"],                                         False, 1,  5),
    (["youtube-music", "youtube"],                              False, 1,  6),
    (["youtube-music", "youtube", "soundcloud", "piped"],       False, 2,  8),
    (["youtube-music", "youtube", "soundcloud", "piped"],       True,  2,  8),
    (["soundcloud", "piped", "bandcamp", "youtube"],            True,  2,  8),
    (["soundcloud", "piped", "bandcamp"],                       True,  2, 10),
]


def _strategy_for_pass(pass_num: int, youtube_blocked: bool) -> tuple:
    idx = min(pass_num - 1, len(_PASS_STRATEGIES) - 1)
    providers, dont_filter, divisor, max_retries = _PASS_STRATEGIES[idx]
    if youtube_blocked:
        providers = [p for p in providers if p not in ("youtube-music", "youtube")]
        if not providers:
            providers = ["piped", "soundcloud", "bandcamp"]
    return providers, dont_filter, divisor, max_retries


# ─────────────────────────────────────────────────────────────────────
#  Fast engine
#
#  spotdl spends ~85 s per track on work LinkCatty can skip: it fetches the
#  Spotify metadata again (19 s), lyrics nobody asked for, retries YouTube
#  Music, scores results slowly and starts yt-dlp slowly. The fast engine
#  searches YouTube itself, picks the best match by duration / title /
#  artist, downloads and converts with yt-dlp and tags the file with the
#  Spotify data and cover. Tracks it cannot match go to spotdl unchanged.
# ─────────────────────────────────────────────────────────────────────

_CODECS = {"mp3": "mp3", "m4a": "m4a", "opus": "opus", "ogg": "vorbis",
           "flac": "flac", "wav": "wav"}
_UNWANTED = ("live", "cover", "remix", "karaoke", "instrumental", "acoustic",
             "sped up", "slowed", "nightcore", "reverb", "8d", "tribute",
             "reaction", "mashup", "loop", "hour", "parody", "lofi",
             "version", "ver", "male", "female", "acapella", "cappella", "piano",
             "guitar", "orchestral", "extended", "stripped", "demo", "remake")


def _words(text) -> list:
    text = re.sub(r"[^\w\s]", " ", str(text or "").lower())
    return [w for w in text.split() if w]


def _title_core(title) -> str:
    """The song title without '(feat. ...)', '[...]' and ' - Remastered 2011' parts."""
    text = re.sub(r"[\(\[].*?[\)\]]", " ", str(title or ""))
    text = re.split(r"\s+-\s+", text)[0]
    return re.sub(r"\s+", " ", text).strip() or str(title or "")


def _track_info(song) -> dict:
    """One flat dict from a spotdl Song, or from the plain dict of a single track."""
    artist = _song_artist(song)
    raw = _song_field(song, "artists") or []
    artists = []
    for a in raw:
        name = a if isinstance(a, str) else (a.get("name") if isinstance(a, dict) else None)
        if name:
            artists.append(name)
    if not artists and artist:
        artists = [artist]
    duration = _song_field(song, "duration")
    try:
        duration = float(duration) if duration else None
    except (TypeError, ValueError):
        duration = None
    return {
        "url": _song_url(song), "title": _song_title(song), "artist": artist,
        "artists": artists, "album": _song_field(song, "album_name", "album"),
        "album_artist": _song_field(song, "album_artist"), "duration": duration,
        "year": _song_field(song, "year"), "track_number": _song_field(song, "track_number"),
        "tracks_count": _song_field(song, "tracks_count"),
        "disc_number": _song_field(song, "disc_number"),
        "cover_url": _song_field(song, "cover_url"), "isrc": _song_field(song, "isrc"),
        "date": _song_field(song, "date"), "disc_count": _song_field(song, "disc_count"),
        "genres": [g for g in (_song_field(song, "genres") or []) if g],
        "copyright": _song_field(song, "copyright_text"),
        "publisher": _song_field(song, "publisher"),
    }


def _full_song(url):
    """The complete Spotify track object (ISRC, genres, copyright, popularity, ...).

    Album and playlist listings only carry a partial one. This is the ~20 s call spotdl
    used to make for every track; the fast engine runs it next to the YouTube search and
    download, so it costs no extra waiting time."""
    try:
        from spotdl.types.song import Song
        return Song.from_url(url)
    except Exception:
        return None


def _fetch_lyrics(title, artists):
    """Plain lyrics from spotdl's providers (best effort, never fatal)."""
    try:
        from spotdl.providers.lyrics import MusixMatch, Synced
        providers = []
        try:
            from spotdl.providers.lyrics import Genius
            from spotdl.utils.config import DEFAULT_CONFIG
            if DEFAULT_CONFIG.get("genius_token"):
                providers.append((Genius, (DEFAULT_CONFIG["genius_token"],)))
        except Exception:
            pass
        providers += [(MusixMatch, ()), (Synced, ())]
        for provider, args in providers:
            try:
                text = provider(*args).get_lyrics(title, list(artists))
            except Exception:
                continue
            if text:
                if provider is Synced:            # "[00:18.90] line" -> "line"
                    text = re.sub(r"^\[\d+:\d+(?:\.\d+)?\]\s*", "", text, flags=re.M)
                text = text.strip()
                if text:
                    return text
    except Exception:
        pass
    return None


_VERSION_NOISE = {"feat", "ft", "featuring", "with", "version", "ver", "remastered", "remaster",
                  "original", "mono", "stereo", "deluxe", "edit", "single", "album", "from"}


def _version_words(title) -> list:
    """Words that name a version of the song: the 'Acoustic Ver.' in 'WHISTLE - Acoustic Ver.'
    or the 'Japanese' in 'DDU-DU DDU-DU (Japanese Version)'. Featured artists do not count."""
    text = str(title or "")
    parts = re.findall(r"[\(\[](.*?)[\)\]]", text) + re.split(r"\s+-\s+", text)[1:]
    words = []
    for part in parts:
        if re.match(r"\s*(feat|ft|featuring|with)\b", part, re.I):
            continue
        words += [w for w in _words(part) if w not in _VERSION_NOISE and not w.isdigit()]
    return words


def _score_candidate(entry: dict, info: dict) -> float:
    """How well a YouTube search result matches the Spotify track (higher is better)."""
    title_words = set(_words(entry.get("title")))
    channel = " ".join(_words(entry.get("channel") or entry.get("uploader")))
    want_words = _words(_title_core(info["title"]))
    want_full = " ".join(_words(info["title"]))
    artist_words = set(w for a in info["artists"] for w in _words(a))
    score = 0.0
    title_hit = (sum(1 for w in want_words if w in title_words) / len(want_words)) if want_words else 0
    score += 45 * title_hit
    if artist_words:
        seen = title_words | set(channel.split())
        score += 25 * min(1.0, sum(1 for w in artist_words if w in seen) / len(artist_words))
    length, want = entry.get("duration"), info.get("duration")
    if length and want:
        gap = abs(float(length) - want)
        score += 30 if gap <= 3 else 22 if gap <= 8 else 10 if gap <= 15 else (-60 if gap > 30 else 0)
    if channel.endswith("topic"):
        score += 15                      # YouTube's auto-generated official audio
    if "official audio" in " ".join(_words(entry.get("title"))):
        score += 8
    title_text = " ".join(_words(entry.get("title")))
    entry["_unwanted"] = False
    for word in _UNWANTED:            # an edit of the song (live, cover, "male version", ...) unless Spotify's title says so too
        pattern = r"\b" + re.escape(word) + r"\b"
        if re.search(pattern, title_text) and not re.search(pattern, want_full):
            score -= 35
            entry["_unwanted"] = True
            break
    version = _version_words(info["title"])
    if version:                          # the right version of the song, not just the same title
        score += 20 * sum(1 for w in version if w in title_words) / len(version)
    entry["_title_hit"] = title_hit
    entry["_score"] = score
    return score


def _pick_match(entries: list, info: dict):
    best, best_score = None, -1e9
    for entry in entries:
        if not entry or not entry.get("id"):
            continue
        score = _score_candidate(entry, info)
        if score > best_score:
            best, best_score = entry, score
    if best is not None and best_score >= 55 and best.get("_title_hit", 0) >= 0.5:
        return best
    return None


def _cover_bytes(url, cache: dict, lock) -> bytes | None:
    if not url:
        return None
    with lock:
        if url in cache:
            return cache[url]
    data = None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
    except Exception:
        data = None
    with lock:
        cache[url] = data
    return data


def _tag_file(path: str, info: dict, cover: bytes | None, fmt: str) -> None:
    """Title, artist, album, track numbers, year, ISRC and cover art. Never fatal."""
    title, artists = info["title"] or "", info["artists"] or []
    artist_text = ", ".join(artists)
    album, album_artist = info.get("album"), info.get("album_artist") or (artists[0] if artists else None)
    year = str(info.get("date") or info.get("year") or "")[:10]
    genres = [g for g in (info.get("genres") or []) if g]
    copyright_text = info.get("copyright") or None
    lyrics, spotify_url, source_url = info.get("lyrics"), info.get("url"), info.get("youtube_url")
    try:
        track = int(info.get("track_number") or 0)
        total = int(info.get("tracks_count") or 0)
        disc = int(info.get("disc_number") or 0)
        disc_total = int(info.get("disc_count") or 0)
    except (TypeError, ValueError):
        track = total = disc = disc_total = 0
    try:
        if fmt == "mp3":
            from mutagen.id3 import (APIC, COMM, ID3, ID3NoHeaderError, TALB, TCON, TCOP,
                                     TDRC, TENC, TIT2, TPE1, TPE2, TPOS, TRCK, TSRC,
                                     USLT, WOAS)
            try:
                tags = ID3(path)
            except ID3NoHeaderError:
                tags = ID3()
            tags.add(TIT2(encoding=3, text=title))
            tags.add(TPE1(encoding=3, text=artists or [""]))
            if album:
                tags.add(TALB(encoding=3, text=album))
            if album_artist:
                tags.add(TPE2(encoding=3, text=album_artist))
            if track:
                tags.add(TRCK(encoding=3, text=f"{track}/{total}" if total else str(track)))
            if disc:
                tags.add(TPOS(encoding=3, text=f"{disc}/{disc_total}" if disc_total else str(disc)))
            if year:
                tags.add(TDRC(encoding=3, text=year))
            if genres:
                tags.add(TCON(encoding=3, text=genres))
            if copyright_text:
                tags.add(TCOP(encoding=3, text=copyright_text))
            if info.get("publisher"):
                tags.add(TENC(encoding=3, text=info["publisher"]))
            if spotify_url:
                tags.add(WOAS(url=spotify_url))
            if source_url:
                tags.add(COMM(encoding=3, lang="XXX", desc="", text=source_url))
            if lyrics:
                tags.add(USLT(encoding=3, lang="XXX", desc="", text=lyrics))
            if info.get("isrc"):
                tags.add(TSRC(encoding=3, text=str(info["isrc"])))
            if cover:
                tags.delall("APIC")
                tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover))
            tags.save(path, v2_version=3)
        elif fmt == "m4a":
            from mutagen.mp4 import MP4, MP4Cover
            f = MP4(path)
            f["\xa9nam"], f["\xa9ART"] = [title], [artist_text]
            if album:
                f["\xa9alb"] = [album]
            if album_artist:
                f["aART"] = [album_artist]
            if track:
                f["trkn"] = [(track, total)]
            if disc:
                f["disk"] = [(disc, 0)]
            if year:
                f["\xa9day"] = [year]
            if genres:
                f["\xa9gen"] = [", ".join(genres)]
            if copyright_text:
                f["cprt"] = [copyright_text]
            if lyrics:
                f["\xa9lyr"] = [lyrics]
            if source_url:
                f["\xa9cmt"] = [source_url]
            if cover:
                f["covr"] = [MP4Cover(cover, imageformat=MP4Cover.FORMAT_JPEG)]
            f.save()
        elif fmt in ("flac", "opus", "ogg"):
            import base64
            from mutagen.flac import FLAC, Picture
            if fmt == "flac":
                f = FLAC(path)
            elif fmt == "opus":
                from mutagen.oggopus import OggOpus
                f = OggOpus(path)
            else:
                from mutagen.oggvorbis import OggVorbis
                f = OggVorbis(path)
            f["title"], f["artist"] = [title], artists or [""]
            if album:
                f["album"] = [album]
            if album_artist:
                f["albumartist"] = [album_artist]
            if track:
                f["tracknumber"] = [str(track)]
            if year:
                f["date"] = [year]
            if genres:
                f["genre"] = genres
            if copyright_text:
                f["copyright"] = [copyright_text]
            if lyrics:
                f["lyrics"] = [lyrics]
            if source_url:
                f["comment"] = [source_url]
            if cover:
                pic = Picture()
                pic.type, pic.mime, pic.data = 3, "image/jpeg", cover
                if fmt == "flac":
                    f.add_picture(pic)
                else:
                    f["metadata_block_picture"] = [base64.b64encode(pic.write()).decode("ascii")]
            f.save()
    except Exception:
        pass


def _download_fraction(data: dict) -> float | None:
    """How far a yt-dlp download is (0..1), from its progress event."""
    if data.get("status") == "finished":
        return 1.0
    fragments, fragment = data.get("fragment_count"), data.get("fragment_index")
    if fragments and fragment is not None:
        return max(fragment - 1, 0) / fragments
    done = data.get("downloaded_bytes") or 0
    total = data.get("total_bytes") or data.get("total_bytes_estimate")
    if total and total > 0:
        return min(done / total, 0.99)
    return None


class _ByteTally:
    """Bytes downloaded so far by the fast engine, and an estimate of the total, for the
    size readout ('58.2MB/203.7MB'). Sizes are known one track at a time as each download
    starts, so tracks that have not started are assumed to be as big as the average."""

    def __init__(self, total_tracks: int):
        self.total_tracks = max(int(total_tracks), 1)
        self.active = False
        self._lock = threading.Lock()
        self._live, self._known, self._finished = {}, {}, {}

    def update(self, key, done, total=None):
        with self._lock:
            self._live[key] = done or 0
            if total:
                self._known[key] = total

    def finish(self, key, ok=True):
        with self._lock:
            got = self._live.pop(key, 0)
            if ok:
                self._finished[key] = self._known.get(key) or got
            else:
                self._known.pop(key, None)

    def snapshot(self):
        with self._lock:
            if not self.active:
                return 0, None
            downloaded = sum(self._finished.values()) + sum(self._live.values())
            sizes = list(self._finished.values()) + [v for k, v in self._known.items()
                                                    if k not in self._finished]
            if not sizes:
                return downloaded, None
            average = sum(sizes) / len(sizes)
            total = sum(sizes) + max(self.total_tracks - len(sizes), 0) * average
            return downloaded, max(total, downloaded)


class _BlockGate:
    """Shared by the workers of one pass. When YouTube's bot check trips, everybody waits a
    little before the next track; after several blocks in a row YouTube is skipped for the
    rest of the pass (hammering it only prolongs the block)."""
    LIMIT = 4

    def __init__(self):
        self._lock = threading.Lock()
        self._until = 0.0
        self._streak = 0

    @property
    def dead(self) -> bool:
        return self._streak >= self.LIMIT

    def blocked(self, pause: bool = True) -> None:
        """One more block. `pause` = the track failed, so give YouTube a rest; without it
        (SoundCloud saved the track) it only counts toward skipping YouTube."""
        with self._lock:
            self._streak += 1
            if pause:
                self._until = max(self._until, time.time() + min(15 * self._streak, 45))

    def ok(self) -> None:
        with self._lock:
            self._streak = 0

    def wait(self) -> None:
        while not self.dead:
            left = self._until - time.time()
            if left <= 0:
                return
            time.sleep(min(left, 1.0))


_BLOCKED_TEXT = ("YT-DLP download error - Sign in to confirm you're not a bot: "
                 "YouTube is limiting this connection")


def _clean_reason(text) -> str:
    text = strip_ansi(str(text or "")).strip()
    text = re.sub(r"^ERROR:\s*(\[[^\]]+\]\s*[\w.-]+:\s*)?", "", text)
    return re.sub(r"\s+", " ", text)[:200]


def _dedupe(entries: list) -> list:
    seen, out = set(), []
    for entry in entries:
        key = (entry or {}).get("id") or (entry or {}).get("url")
        if key and key not in seen:
            seen.add(key)
            out.append(entry)
    return out


def _flat_search(prefix: str, query: str, extra: dict) -> list:
    opts = {"quiet": True, "no_warnings": True, "logger": SilentLogger(),
            "extract_flat": True, "socket_timeout": 20}
    opts.update(extra)
    with YoutubeDL(opts) as ydl:
        found = ydl.extract_info(f"{prefix}:{query}", download=False)
    return list((found or {}).get("entries") or [])


def _rank_candidates(entries: list, info: dict, source: str = "youtube") -> list:
    """The acceptable search results, best first. SoundCloud is full of edits and previews,
    so its length has to match the Spotify track closely."""
    ranked = []
    for entry in entries:
        if not entry or not (entry.get("id") or entry.get("url")):
            continue
        score = _score_candidate(entry, info)
        if score < 55 or entry.get("_title_hit", 0) < 0.5 or entry.get("_unwanted"):
            continue
        if source == "soundcloud":
            length, want = entry.get("duration"), info.get("duration")
            if score < 80 or not length or (want and abs(float(length) - want) > 8):
                continue
        ranked.append((score, entry))
    ranked.sort(key=lambda pair: -pair[0])
    return [entry for _, entry in ranked]


def _download_audio(target: str, tmp: str, fmt: str, quality: str, ffmpeg,
                    on_progress, extra: dict) -> str:
    """Download one page with yt-dlp and convert it. Returns the audio file."""
    post = {"key": "FFmpegExtractAudio", "preferredcodec": _CODECS.get(fmt, "mp3")}
    if fmt not in ("flac", "wav"):
        post["preferredquality"] = quality
    opts = {"quiet": True, "no_warnings": True, "noprogress": True, "logger": SilentLogger(),
            "format": "bestaudio/best", "outtmpl": os.path.join(tmp, "audio.%(ext)s"),
            "noplaylist": True, "retries": 5, "fragment_retries": 5, "socket_timeout": 30,
            "postprocessors": [post]}
    opts.update(extra)
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg
    if on_progress:
        def hook(data):
            fraction = _download_fraction(data)
            if fraction is not None:
                # an exact total only for plain downloads (fragmented streams report estimates)
                exact = None if data.get("fragment_count") else data.get("total_bytes")
                on_progress(fraction, data.get("downloaded_bytes") or 0, exact)
        opts["progress_hooks"] = [hook]
    with YoutubeDL(opts) as ydl:
        ydl.download([target])
    produced = [f for f in os.listdir(tmp) if f.lower().endswith("." + fmt)]
    if not produced:
        raise RuntimeError("YT-DLP download error - no audio file was produced")
    return os.path.join(tmp, produced[0])


def _fast_fetch_one(info: dict, out_dir: str, fmt: str, quality: str,
                    ffmpeg, cover_cache: dict, cover_lock, on_progress=None,
                    full_metadata: bool = True, want_lyrics: bool = True,
                    sources=("youtube",), extra_opts=None) -> str:
    """Search, download, convert and tag one track. Returns the final file path.

    Several matching videos are tried in order, and SoundCloud when `sources` allows it, so
    one unavailable video does not lose the track. `info["_source"]` names the source used.
    Raises an Exception whose text is the reason when the track cannot be done."""
    title = info["title"] or "Unknown"
    artist_text = ", ".join(info["artists"]) or info["artist"] or "Unknown"
    name = _safe_name(f"{title} - {artist_text}") or "track"
    final = os.path.join(out_dir, f"{name[:150]}.{fmt}")
    if os.path.exists(final):
        return final                                   # done in an earlier run
    extra = dict(extra_opts or {})

    # the complete Spotify data and the lyrics load in the background while the audio downloads
    box = {}
    jobs = []
    if full_metadata and info.get("url"):
        jobs.append((threading.Thread(target=lambda: box.__setitem__("song", _full_song(info["url"])), daemon=True), 90))
    if want_lyrics:
        jobs.append((threading.Thread(target=lambda: box.__setitem__(
            "lyrics", _fetch_lyrics(_title_core(title), info["artists"] or [artist_text])), daemon=True), 25))
    for job, _ in jobs:
        job.start()

    # 1. find the videos: two queries (the second only when the first has no clear winner)
    core = _title_core(title)
    attempts, search_error, searched = [], None, False
    if "youtube" in sources:
        pool = []
        for query in (f"{info['artist'] or artist_text} {core}", f"{core} {artist_text} audio"):
            try:
                pool = _dedupe(pool + _flat_search("ytsearch8", query, extra))
                searched = True
            except Exception as exc:
                search_error = search_error or exc
                continue
            best = _rank_candidates(pool, info)
            if best and best[0]["_score"] >= 100:
                break
        attempts += [("youtube", e) for e in _rank_candidates(pool, info)[:3]]
    if "soundcloud" in sources:
        try:
            found = _flat_search("scsearch8", f"{info['artist'] or artist_text} {core}", extra)
            attempts += [("soundcloud", e) for e in _rank_candidates(found, info, "soundcloud")[:2]]
            searched = True
        except Exception:
            pass
    if not attempts:
        if search_error is not None and not searched:
            raise RuntimeError(f"YT-DLP download error - search failed: {_clean_reason(search_error)}")
        raise LookupError(f"No results found for song: {artist_text} - {title}")

    # 2. download the audio and convert it: the next candidate takes over when one fails
    reasons, blocked, src, tmp, page_url = [], False, None, None, None
    for source, entry in attempts:
        if blocked and source == "youtube":
            continue                                   # the same connection would get the same answer
        target = (entry.get("url") if source == "soundcloud"
                  else f"https://www.youtube.com/watch?v={entry['id']}")
        attempt_tmp = os.path.join(out_dir, ".linkcatty_tmp",
                                   re.sub(r"\W", "_", str(entry.get("id") or entry.get("url")))[-48:])
        shutil.rmtree(attempt_tmp, ignore_errors=True)
        os.makedirs(attempt_tmp, exist_ok=True)
        try:
            src = _download_audio(target, attempt_tmp, fmt, quality, ffmpeg, on_progress, extra)
            tmp, page_url = attempt_tmp, target
            info["_source"] = source
            break
        except Exception as exc:
            shutil.rmtree(attempt_tmp, ignore_errors=True)
            reasons.append(_clean_reason(exc))
            if _classify_error(reasons[-1]) == "blocked_or_rate_limited":
                blocked = True
    info["_blocked"] = blocked
    if src is None:
        if blocked:
            raise RuntimeError(_BLOCKED_TEXT)
        raise RuntimeError("YT-DLP download error - " + (reasons[-1] if reasons else "no usable source"))

    try:
        # 3. every tag spotdl used to write (from the complete Spotify data), then move into place
        for job, wait in jobs:
            job.join(timeout=wait)
        song, lyrics = box.get("song"), box.get("lyrics")
        tagged = False
        if song is not None:
            try:
                from spotdl.utils.metadata import embed_metadata
                song.download_url = page_url
                if lyrics:
                    song.lyrics = lyrics
                embed_metadata(Path(src), song, "/")
                tagged = True
            except Exception:
                tagged = False
        if not tagged:                                  # partial data: tag with everything we have
            more = dict(info)
            more.update(lyrics=lyrics, youtube_url=page_url)
            _tag_file(src, more, _cover_bytes(info.get("cover_url"), cover_cache, cover_lock), fmt)
        os.replace(src, final)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return final


# ─────────────────────────────────────────────────────────────────────
#  JSON track ledger
# ─────────────────────────────────────────────────────────────────────

def _ledger_path(out_dir: str) -> str:
    return os.path.join(out_dir, ".linkcatty_state.json")


def _load_ledger(out_dir: str) -> dict:
    path = _ledger_path(out_dir)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_ledger(out_dir: str, ledger: dict) -> None:
    path = _ledger_path(out_dir)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        print_warning(f"Could not write track ledger: {exc}")


def _init_ledger_entry(url: str, title: str | None, artist: str | None) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "url": url,
        "title": title,
        "artist": artist,
        "status": "pending",
        "attempts": 0,
        "error_type": None,
        "last_error": None,
        "providers_tried": [],
        "first_seen": now,
        "last_attempt": None,
    }


def _song_field(song, *names, default=None):
    for name in names:
        if isinstance(song, dict):
            if song.get(name):
                return song[name]
        else:
            val = getattr(song, name, None)
            if val:
                return val
    return default


def _song_url(song) -> str | None:
    return _song_field(song, "url")


def _song_title(song) -> str | None:
    return _song_field(song, "name", "title")


def _song_artist(song) -> str | None:
    artist = _song_field(song, "artist")
    if artist:
        return artist
    artists = _song_field(song, "artists")
    if artists:
        first = artists[0]
        return first if isinstance(first, str) else first.get("name")
    return None


# ─────────────────────────────────────────────────────────────────────
#  Jittered sleep
# ─────────────────────────────────────────────────────────────────────

def _jitter_sleep(low: float, high: float) -> None:
    if high <= 0:
        return
    low = max(0.0, min(low, high))
    time.sleep(random.uniform(low, high))


# ─────────────────────────────────────────────────────────────────────
#  SpotifyDownloader
# ─────────────────────────────────────────────────────────────────────

class _SetupError(Exception):
    """The machine cannot run spotdl yet (not a per-track failure)."""
    def __init__(self, message, hint=None):
        super().__init__(message)
        self.hint = hint


class SpotifyDownloader:
    def __init__(self, config):
        self.config        = config
        self.spotify_config = config["spotify"]
        self.download_dir  = Path(config["download_dir"])
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.spotdl_cmd = _find_spotdl_command()

        self.client_id     = self.spotify_config.get("client_id", "").strip()
        self.client_secret = self.spotify_config.get("client_secret", "").strip()

        self._client = _get_free_client()

        _ensure_deno(self.spotdl_cmd)

        # ── pacing / anti-rate-limit settings (all overridable in config) ──
        #
        #  Speed tuning: batches within a pass now run in PARALLEL, so the
        #  effective concurrency is parallel_batches * threads. Defaults
        #  give 3 * 2 = 6 concurrent downloads, which is fast without
        #  tripping YouTube's rate limiter. Lower parallel_batches to 2 (or
        #  threads to 1) if you see "blocked by youtube" errors.
        self.parallel_batches         = max(1, int(self.spotify_config.get("parallel_batches", 3)))
        self.batch_size               = max(1, int(self.spotify_config.get("batch_size", 10)))
        self.batch_cooldown_min       = float(self.spotify_config.get("batch_cooldown_min", 1))
        self.batch_cooldown_max       = float(self.spotify_config.get("batch_cooldown_max", 3))
        self.pass_cooldown_seconds    = int(self.spotify_config.get("retry_delay_seconds", 8))
        self.blocked_cooldown_seconds = int(self.spotify_config.get("blocked_cooldown_seconds", 45))
        self.max_passes               = (max(1, int(self.spotify_config.get("max_retry_passes", 4)))
                                         if self.spotify_config.get("auto_retry", True) else 1)
        self.base_threads             = int(self.spotify_config.get("threads", 2))
        # "fast" = LinkCatty's own search + download first, spotdl for what it cannot match;
        # "spotdl" = spotdl only (slower, the previous behaviour)
        self.engine                   = str(self.spotify_config.get("engine", "fast")).lower()

    def _find_ffmpeg(self):
        """FFmpeg for spotdl: bundled, on PATH, or spotdl's own copy (downloaded on demand).

        spotdl refuses to start without it and every track would fail at once."""
        if getattr(self, "_ffmpeg_checked", False):
            return self.ffmpeg
        self._ffmpeg_checked = True
        self.ffmpeg = get_ffmpeg_path()
        if not self.ffmpeg and _SPOTDL_AVAILABLE:
            try:
                from spotdl.utils.ffmpeg import download_ffmpeg, get_local_ffmpeg
                local = get_local_ffmpeg()
                if not local:
                    start_spinner("🔧 Getting FFmpeg (one-time setup)")
                    try:
                        download_ffmpeg()
                    finally:
                        stop_spinner()
                    local = get_local_ffmpeg()
                self.ffmpeg = str(local) if local else None
            except Exception:
                self.ffmpeg = None
        return self.ffmpeg

    def _fast_pass(self, pending_urls, songs_by_url, out_dir, ledger, fmt, quality, reporter,
                   inflight, tally=None, pass_num=1, throttled=False):
        """Try every pending track with the fast engine (in parallel). Failures stay
        pending. Returns True when YouTube looked rate-limited.

        The first pass uses YouTube only; later passes may use SoundCloud for what YouTube
        would not give (a lower-quality copy is better than a missing song). While YouTube
        is refusing this connection the workers back off instead of hammering it."""
        workers = max(1, self.parallel_batches * self.base_threads)
        if throttled:
            workers = max(2, workers // 2)
        cover_cache, cover_lock = {}, threading.Lock()
        gate = _BlockGate()
        blocked = False
        wanted = ("youtube",)
        if pass_num > 1 and self.spotify_config.get("soundcloud_fallback", True):
            wanted = ("youtube", "soundcloud")
        browser = str(self.spotify_config.get("cookies_from_browser") or "").strip()
        extra = {"cookiesfrombrowser": (browser,)} if browser else {}

        def work(url):
            gate.wait()
            sources = tuple(x for x in wanted if not (x == "youtube" and gate.dead))
            if not sources:
                raise RuntimeError(_BLOCKED_TEXT)
            info = _track_info(songs_by_url[url])
            try:
                # the audio download is ~90% of a track; converting and tagging is the rest
                _fast_fetch_one(info, out_dir, fmt, quality, self.ffmpeg,
                                cover_cache, cover_lock,
                                full_metadata=bool(self.spotify_config.get("full_metadata", True)),
                                want_lyrics=bool(self.spotify_config.get("lyrics", True)),
                                sources=sources, extra_opts=extra,
                                on_progress=lambda f, d=0, t=None: (
                                    inflight.__setitem__(url, f * 0.9),
                                    tally.update(url, d, t) if tally else None))
            except Exception as exc:
                if _classify_error(strip_ansi(str(exc))) == "blocked_or_rate_limited":
                    gate.blocked()
                    raise
                if "youtube" in wanted and "youtube" not in sources:
                    # YouTube was not even tried (it keeps refusing) and the other source
                    # failed too: this is still the block, not a problem with the track
                    raise RuntimeError(_BLOCKED_TEXT) from exc
                raise
            if info.get("_blocked"):
                gate.blocked(pause=False)
            elif info.get("_source") != "soundcloud":
                gate.ok()
            return info.get("_source")

        if tally:
            tally.active = True
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(work, u): u for u in pending_urls}
            for future in as_completed(futures):
                url = futures[future]
                inflight.pop(url, None)
                rec = ledger[url]
                rec["attempts"] += 1
                rec["last_attempt"] = datetime.now().isoformat(timespec="seconds")
                if "fast" not in rec["providers_tried"]:
                    rec["providers_tried"].append("fast")
                try:
                    source = future.result()
                    rec.update(status="success", last_error=None, error_type=None)
                    if source and source not in rec["providers_tried"]:
                        rec["providers_tried"].append(source)
                    if tally:
                        tally.finish(url, ok=True)
                except Exception as exc:
                    if tally:
                        tally.finish(url, ok=False)
                    message = _clean_reason(exc)
                    rec.update(status="failed", last_error=message,
                               error_type=_classify_error(message))
                    if rec["error_type"] == "blocked_or_rate_limited":
                        blocked = True
                _save_ledger(out_dir, ledger)
                reporter._render()
        if tally:
            tally.active = False              # back to the plain "n/total tracks" for the spotdl fallback
        return blocked

    def _download_tracks_safe(self, songs, item_type, meta_name, title):
        """_download_tracks, but an unusable setup becomes a clear message."""
        try:
            return self._download_tracks(songs, item_type, meta_name)
        except _SetupError as exc:
            section_header(title)
            print_error(str(exc), exc.hint)
            return None

    def _download_until_done(self, songs, item_type, name, title):
        """Download; while tracks are missing, offer to retry just those (the ledger resumes).

        Returns (outcome, seconds spent downloading)."""
        spent = 0.0
        started = time.time()
        outcome = self._download_tracks_safe(songs, item_type, name, title)
        spent += time.time() - started
        last_missing = None
        for _ in range(5):
            if outcome is None:
                break
            count, out_folder, expected, failed_report, breakdown = outcome
            missing = expected - count
            if failed_report is None or missing <= 0:
                break
            # nothing to retry when the machine is missing something or the videos are gone
            fixable = [label for label in breakdown if label not in _NOT_FIXABLE_BY_RETRY]
            if not fixable:
                break
            section_header(title)
            _display_download_result(item_type, name, out_folder, count, expected,
                                     failed_report, breakdown, elapsed=spent)
            if _ERROR_LABELS["blocked_or_rate_limited"] in breakdown:
                print_info("YouTube is limiting this connection. Waiting a few minutes or "
                           "turning on a VPN usually clears it.")
            progressed = last_missing is None or missing < last_missing
            plural = "s" if missing != 1 else ""
            if not confirm(f"Retry the {missing} missing track{plural} now?", default=progressed):
                break
            last_missing = missing
            section_header(title)
            started = time.time()
            outcome = self._download_tracks_safe(songs, item_type, name, title)
            spent += time.time() - started
        return outcome, spent

    # ── metadata ──────────────────────────────────────────────────────

    def _get_playlist_meta(self, url: str):
        meta = {"name": None, "author": None, "track_count": None}
        songs = None
        if SpotPlaylist is not None and self._client is not None:
            try:
                pl_meta, songs = SpotPlaylist.get_metadata(url)
                meta["name"]        = pl_meta.get("name")
                meta["author"]      = pl_meta.get("author_name")
                meta["track_count"] = len(songs)
                return meta, songs
            except Exception:
                pass
        meta["name"] = _oembed_title(url)
        return meta, songs

    def _get_album_meta(self, url: str):
        meta = {"name": None, "artist": None, "track_count": None}
        songs = None
        if SpotAlbum is not None and self._client is not None:
            try:
                al_meta, songs = SpotAlbum.get_metadata(url)
                meta["name"]        = al_meta.get("name")
                meta["artist"]      = al_meta.get("artist")
                meta["track_count"] = len(songs)
                return meta, songs
            except Exception:
                pass
        title = _oembed_title(url)
        if title:
            meta["name"] = re.sub(r"\s*[-–|].*$", "", title).strip()
        return meta, songs

    def _get_track_meta(self, url: str) -> dict:
        meta = {"title": None, "artist": None, "album": None, "artists": [],
                "album_artist": None, "duration": None, "year": None,
                "track_number": None, "tracks_count": None, "disc_number": None,
                "cover_url": None, "isrc": None}
        if self._client is not None:
            try:
                track_id = url.split("/track/")[-1].split("?")[0]
                tr = self._client.track(track_id)
                meta["title"]  = tr.get("name")
                artists = tr.get("artists", [])
                names = [a.get("name") if isinstance(a, dict) else str(a) for a in artists]
                meta["artists"] = [n for n in names if n]
                if meta["artists"]:
                    meta["artist"] = meta["artists"][0]
                if tr.get("duration_ms"):
                    meta["duration"] = tr["duration_ms"] / 1000
                meta["track_number"] = tr.get("track_number")
                meta["disc_number"] = tr.get("disc_number")
                meta["isrc"] = (tr.get("external_ids") or {}).get("isrc")
                alb = tr.get("album")
                if isinstance(alb, dict):
                    meta["album"] = alb.get("name")
                    meta["tracks_count"] = alb.get("total_tracks")
                    meta["year"] = str(alb.get("release_date") or "")[:4] or None
                    images = alb.get("images") or []
                    if images and isinstance(images[0], dict):
                        meta["cover_url"] = images[0].get("url")
                    alb_artists = alb.get("artists") or []
                    if alb_artists and isinstance(alb_artists[0], dict):
                        meta["album_artist"] = alb_artists[0].get("name")
                return meta
            except Exception:
                pass
        title = _oembed_title(url)
        if title:
            parts = title.split(" - ", 1)
            meta["title"]  = parts[0].strip()
            meta["artist"] = parts[1].strip() if len(parts) > 1 else None
            meta["artists"] = [meta["artist"]] if meta["artist"] else []
        return meta

    # ── core download engine (parallel batches, ledger-driven, adaptive) ──

    def _run_spotdl_batch(self, urls: list, out_dir: str, template: str,
                           audio_format: str, bitrate_arg: str,
                           archive_file: str, errors_file: str, log_file: str,
                           providers: list, dont_filter: bool,
                           threads: int, max_retries: int) -> int:
        """
        Run one spotdl batch. Returns the subprocess exit code.

        spotdl's CLI is `spotdl [operation] query...`; the operation slot
        only accepts download|save|web|sync|meta|url. Without the explicit
        `download` verb, argparse binds the first URL to `operation` and
        dies immediately.
        """
        if os.path.exists(errors_file):
            os.remove(errors_file)

        cmd = [
            *self.spotdl_cmd,
            "download",
            *urls,
            "--output", template,
            "--format", audio_format,
            "--bitrate", bitrate_arg,
            "--threads", str(threads),
            "--max-retries", str(max_retries),
            "--archive", archive_file,
            "--save-errors", errors_file,
            "--overwrite", "skip",
            "--audio", *providers,
        ]
        if getattr(self, "ffmpeg", None):
            cmd += ["--ffmpeg", self.ffmpeg]
        if dont_filter:
            cmd.append("--dont-filter-results")
        if self.client_id and self.client_secret:
            cmd += ["--client-id", self.client_id,
                    "--client-secret", self.client_secret]

        with open(log_file, "a", encoding="utf-8") as logf:
            logf.write(f"\n\n===== Batch — {datetime.now()} — "
                       f"providers={providers} dont_filter={dont_filter} =====\n")
            logf.write("CMD: " + " ".join(cmd) + "\n")
            proc = subprocess.Popen(cmd, stdout=logf,
                                    stderr=subprocess.STDOUT, text=True)
            proc.wait()
            return proc.returncode

    def _run_spotdl_batch_isolated(self, batch_urls, batch_idx, pass_temp,
                                    out_dir, template, audio_format, bitrate_arg,
                                    main_archive_file, providers, dont_filter,
                                    threads, max_retries):
        """
        Runs one spotdl batch with its own archive/errors/log files.
        Designed to be called from a ThreadPoolExecutor — nothing here
        touches shared state (only per-batch files in pass_temp), so it
        is safe to run several in parallel.
        """
        batch_archive = os.path.join(pass_temp, f"archive.{batch_idx}.spotdl")
        batch_errors  = os.path.join(pass_temp, f"errors.{batch_idx}.txt")
        batch_log     = os.path.join(pass_temp, f"log.{batch_idx}.txt")

        # Seed the batch archive with the main archive so spotdl skips
        # anything already downloaded in previous passes / runs.
        if os.path.exists(main_archive_file):
            try:
                shutil.copyfile(main_archive_file, batch_archive)
            except Exception:
                pass

        exit_code = self._run_spotdl_batch(
            batch_urls, out_dir, template, audio_format, bitrate_arg,
            batch_archive, batch_errors, batch_log,
            providers, dont_filter, threads, max_retries,
        )

        return {
            "batch_idx":     batch_idx,
            "batch_urls":    batch_urls,
            "exit_code":     exit_code,
            "errors":        _read_errors_file(batch_errors),
            "archive":       _read_archive(batch_archive),
            "archive_path":  batch_archive,
            "log_path":      batch_log,
        }

    def _merge_archive(self, main_path: str, batch_path: str) -> None:
        """Append any new URLs from a per-batch archive to the main one."""
        if not os.path.exists(batch_path):
            return
        try:
            existing = _read_archive(main_path)
            new_urls = []
            with open(batch_path, "r", encoding="utf-8", errors="ignore") as src:
                for line in src:
                    line = line.strip()
                    if line.startswith("http") and line not in existing:
                        new_urls.append(line)
                        existing.add(line)
            if new_urls:
                with open(main_path, "a", encoding="utf-8") as dst:
                    for url in new_urls:
                        dst.write(url + "\n")
        except Exception:
            pass

    def _download_tracks(self, songs: list, item_type: str,
                          meta_name: str | None) -> tuple:
        """
        Download a list of Song objects with parallel batched pacing and
        an adaptive, ledger-tracked multi-pass retry.

        Returns (final_count, out_dir, expected_total,
                 failed_report_path, error_breakdown).
        """
        if not self._find_ffmpeg():
            raise _SetupError(
                "FFmpeg is missing, so Spotify downloads cannot start.",
                "Run  linkcatty --update  to fetch it, or install FFmpeg and try again.")
        audio_format = self.spotify_config.get("audio_format", "mp3").lower()
        quality  = self.spotify_config.get("audio_quality", "320k").replace("k", "")
        bitrate_arg = "disable" if audio_format in ("flac", "wav") else f"{quality}k"
        base_dir = str(self.download_dir)

        if item_type in ("album", "playlist"):
            folder_name = _safe_name(meta_name) if meta_name else f"{{{item_type}}}"
            out_dir = os.path.join(base_dir, folder_name)
        else:
            out_dir = base_dir
        template = os.path.join(out_dir, "{title} - {artists}.{output-ext}")
        os.makedirs(out_dir, exist_ok=True)

        archive_file = os.path.join(out_dir, ".spotdl_archive.spotdl")
        errors_file  = os.path.join(out_dir, ".spotdl_errors.txt")
        log_file     = os.path.join(out_dir, ".spotdl_log.txt")

        expected_total = len(songs) or 1

        format_label = audio_format.upper() + (
            "" if audio_format in ("flac", "wav") else f" {quality}k")
        plan_line(format_label,
                  f"{self.parallel_batches * self.base_threads} parallel")

        # ── build / merge the ledger ────────────────────────────────
        ledger = _load_ledger(out_dir)
        song_urls = {_song_url(s) for s in songs if _song_url(s)}
        for song in songs:
            url = _song_url(song)
            if not url:
                continue
            if url not in ledger:
                ledger[url] = _init_ledger_entry(
                    url, _song_title(song), _song_artist(song))
        _save_ledger(out_dir, ledger)

        youtube_blocked = False
        spotdl_runs = 0
        songs_by_url = {_song_url(s): s for s in songs if _song_url(s)}
        use_fast = self.engine != "spotdl" and bool(songs_by_url) and \
            all(u.startswith("http") and "/track/" in u for u in songs_by_url)

        inflight = {}                        # url -> how far its download is (fast engine)
        tally = _ByteTally(len([u for u in song_urls if ledger.get(u, {}).get("status") != "success"]))
        reporter = DownloadProgress(
            "Downloading", expected_total, unit="tracks",
            count_fn=_make_progress_counter(out_dir, ledger, song_urls, expected_total),
            partial_fn=lambda: sum(list(inflight.values())),
            bytes_fn=tally.snapshot)
        reporter.start()

        try:
            for pass_num in range(1, self.max_passes + 1):
                pending_urls = [
                    u for u, rec in ledger.items()
                    if u in song_urls and rec["status"] != "success"
                ]
                if not pending_urls:
                    break

                if use_fast:
                    # the fast engine goes first in every pass (later passes are more patient and
                    # may use SoundCloud); spotdl only gets what the search could not find
                    if self._fast_pass(pending_urls, songs_by_url, out_dir, ledger,
                                       audio_format, quality, reporter, inflight, tally,
                                       pass_num=pass_num, throttled=youtube_blocked):
                        youtube_blocked = True
                    pending_urls = [
                        u for u, rec in ledger.items()
                        if u in song_urls and rec["status"] != "success"
                    ]
                    if not pending_urls:
                        break
                    pending_urls = [u for u in pending_urls
                                    if ledger[u].get("error_type") in _SPOTDL_HELPS] \
                        if spotdl_runs < 2 else []
                    if pending_urls:
                        spotdl_runs += 1

                providers, dont_filter, divisor, max_retries = \
                    _strategy_for_pass(spotdl_runs if use_fast else pass_num, youtube_blocked)
                if pending_urls:
                    threads = max(1, self.base_threads // divisor)

                    batches = [
                        pending_urls[i:i + self.batch_size]
                        for i in range(0, len(pending_urls), self.batch_size)
                    ]

                    # Per-pass scratch dir for per-batch archive/errors/log.
                    pass_temp = os.path.join(out_dir, f".linkcatty_pass{pass_num}")
                    shutil.rmtree(pass_temp, ignore_errors=True)
                    os.makedirs(pass_temp, exist_ok=True)

                    try:
                        with ThreadPoolExecutor(max_workers=self.parallel_batches) as executor:
                            futures = {
                                executor.submit(
                                    self._run_spotdl_batch_isolated,
                                    batch_urls, b_idx, pass_temp, out_dir, template,
                                    audio_format, bitrate_arg, archive_file,
                                    providers, dont_filter, threads, max_retries,
                                ): (b_idx, batch_urls)
                                for b_idx, batch_urls in enumerate(batches)
                            }

                            for future in as_completed(futures):
                                b_idx, batch_urls = futures[future]

                                try:
                                    result       = future.result()
                                    exit_code    = result["exit_code"]
                                    batch_errors = result["errors"]
                                    batch_archive_set = result["archive"]
                                    batch_archive_path = result["archive_path"]
                                    batch_log_path     = result["log_path"]
                                except Exception as exc:
                                    exit_code = -1
                                    batch_errors = {}
                                    batch_archive_set = set()
                                    batch_archive_path = None
                                    batch_log_path = None

                                # Merge archive & append log
                                if batch_archive_path:
                                    self._merge_archive(archive_file, batch_archive_path)
                                if batch_log_path and os.path.exists(batch_log_path):
                                    try:
                                        with open(batch_log_path, "r",
                                                  encoding="utf-8",
                                                  errors="ignore") as src:
                                            with open(log_file, "a",
                                                      encoding="utf-8") as dst:
                                                dst.write(
                                                    f"\n\n===== Pass {pass_num} "
                                                    f"batch {b_idx} =====\n"
                                                )
                                                dst.write(src.read())
                                    except Exception:
                                        pass

                                # Update ledger (main thread only — no lock needed)
                                now = datetime.now().isoformat(timespec="seconds")
                                for url in batch_urls:
                                    rec = ledger.get(url)
                                    if rec is None:
                                        continue
                                    rec["attempts"] += 1
                                    rec["last_attempt"] = now
                                    for p in providers:
                                        if p not in rec["providers_tried"]:
                                            rec["providers_tried"].append(p)

                                    if url in batch_errors:
                                        msg = batch_errors[url]
                                        rec["status"]     = "failed"
                                        rec["last_error"] = msg
                                        rec["error_type"] = _classify_error(msg)
                                        if rec["error_type"] == "blocked_or_rate_limited":
                                            youtube_blocked = True
                                    elif url in batch_archive_set:
                                        rec["status"]     = "success"
                                        rec["last_error"] = None
                                        rec["error_type"] = None
                                    elif exit_code != 0:
                                        rec["status"]     = "failed"
                                        rec["last_error"] = (
                                            (batch_log_path and _batch_log_reason(batch_log_path))
                                            or f"spotdl exited with code {exit_code} "
                                               f"(no per-track error captured; see "
                                               f"{os.path.basename(log_file)})"
                                        )
                                        rec["error_type"] = _classify_error(rec["last_error"])
                                    else:
                                        rec["status"]     = "success"
                                        rec["last_error"] = None
                                        rec["error_type"] = None

                                _save_ledger(out_dir, ledger)

                                reporter._render()
                    finally:
                        shutil.rmtree(pass_temp, ignore_errors=True)

                pass_end_success = sum(
                    1 for r in ledger.values() if r["status"] == "success")
                still_missing = expected_total - pass_end_success

                if still_missing <= 0:
                    break

                if pass_end_success == 0 and any(
                        r.get("error_type") in _SYSTEMIC
                        for u, r in ledger.items() if u in song_urls):
                    break

                if pass_num < self.max_passes:
                    cooldown = (self.blocked_cooldown_seconds
                                if youtube_blocked
                                else self.pass_cooldown_seconds)
                    _jitter_sleep(cooldown, cooldown + 3)
        finally:
            reporter.stop()

        relevant_records = [ledger[u] for u in song_urls if u in ledger]
        final_count = sum(1 for r in relevant_records if r["status"] == "success")
        failed_records   = [r for r in relevant_records if r["status"] != "success"]

        error_breakdown = {}
        for r in failed_records:
            etype = r.get("error_type") or "other"
            label = _ERROR_LABELS.get(etype)
            if etype == "other" or label is None:
                label = "Error: " + _short(r.get("last_error") or "unknown")
            error_breakdown[label] = error_breakdown.get(label, 0) + 1

        failed_report_path = None
        if failed_records:
            failed_report_path = _write_failed_report(
                out_dir, meta_name, failed_records,
                expected_total, final_count, error_breakdown
            )
        else:                                 # everything is here: an old report would only mislead
            for stale in ("failed_downloads.txt", "failed_downloads.json"):
                try:
                    os.remove(os.path.join(out_dir, stale))
                except OSError:
                    pass

        return final_count, out_dir, expected_total, failed_report_path, error_breakdown

    # ── public entry-points ───────────────────────────────────────────

    def download_single_track(self, url: str) -> None:
        title = "🎵 Spotify Downloader — Track"
        start_spinner("🎶 Fetching track info")
        meta = self._get_track_meta(url)
        stop_spinner()
        section_header(title)
        _display_track_info(meta)
        if not confirm("Proceed with download?", default=True):
            return
        song = {"url": url, "name": meta.get("title"), "artist": meta.get("artist"),
                "artists": meta.get("artists"), "album_name": meta.get("album"),
                "album_artist": meta.get("album_artist"), "duration": meta.get("duration"),
                "year": meta.get("year"), "track_number": meta.get("track_number"),
                "tracks_count": meta.get("tracks_count"), "disc_number": meta.get("disc_number"),
                "cover_url": meta.get("cover_url"), "isrc": meta.get("isrc")}
        outcome, elapsed = self._download_until_done([song], "track", meta.get("title"), title)
        if outcome is None:
            return
        count, out_folder, expected, failed_report, breakdown = outcome
        section_header(title)
        _display_download_result("track", meta.get("title"), out_folder,
                                  count, expected, failed_report, breakdown,
                                  elapsed=elapsed)
        status = "Success" if failed_report is None else "Partial"
        log_download("Spotify", url, artist=meta.get("artist", "spotdl"),
                     mode="Single", status=status)

    def download_album(self, url: str) -> None:
        title = "💿 Spotify Downloader — Album"
        start_spinner("💿 Fetching album info")
        meta, songs = self._get_album_meta(url)
        stop_spinner()
        section_header(title)
        _display_album_info(meta)
        if not confirm("Download all tracks?", default=True):
            return
        if not songs:
            print_error("Could not resolve the album's track list.",
                        "Falling back to a single bulk download via spotdl.")
            songs = [{"url": url, "name": meta.get("name"),
                      "artist": meta.get("artist")}]
        outcome, elapsed = self._download_until_done(songs, "album", meta["name"], title)
        if outcome is None:
            return
        count, out_folder, expected, failed_report, breakdown = outcome
        section_header(title)
        _display_download_result("album", meta["name"], out_folder,
                                  count, expected, failed_report, breakdown,
                                  elapsed=elapsed)
        status = "Success" if failed_report is None else "Partial"
        log_download("Spotify", url, artist="spotdl", mode="Album", status=status)

    def download_playlist(self, url: str) -> None:
        title = "📂 Spotify Downloader — Playlist"
        start_spinner("📂 Fetching playlist info")
        meta, songs = self._get_playlist_meta(url)
        stop_spinner()
        section_header(title)
        _display_playlist_info(meta)
        if not confirm("Download all tracks?", default=True):
            return
        if not songs:
            print_error("Could not resolve the playlist's track list.",
                        "Falling back to a single bulk download via spotdl.")
            songs = [{"url": url, "name": meta.get("name"),
                      "artist": meta.get("author")}]
        outcome, elapsed = self._download_until_done(songs, "playlist", meta["name"], title)
        if outcome is None:
            return
        count, out_folder, expected, failed_report, breakdown = outcome
        section_header(title)
        _display_download_result("playlist", meta["name"], out_folder,
                                  count, expected, failed_report, breakdown,
                                  elapsed=elapsed)
        status = "Success" if failed_report is None else "Partial"
        log_download("Spotify", url, artist="spotdl", mode="Playlist", status=status)


# ─────────────────────────────────────────────────────────────────────
#  Standalone helpers
# ─────────────────────────────────────────────────────────────────────

def _oembed_title(url: str) -> str | None:
    try:
        api = "https://open.spotify.com/oembed?url=" + urllib.parse.quote(url, safe="")
        req = urllib.request.Request(
            api,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode()).get("title", "").strip() or None
    except Exception:
        return None


def _safe_name(name: str | None) -> str | None:
    if not name:
        return None
    return re.sub(r'[\\/*?:"<>|]', "", name).strip() or None


def _count_audio_files(folder: str) -> int:
    exts = {".mp3", ".m4a", ".opus", ".ogg", ".flac", ".wav"}
    count = 0
    if not os.path.isdir(folder):
        return 0
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".linkcatty")]
        for f in files:
            if Path(f).suffix.lower() in exts:
                count += 1
    return count


def _make_progress_counter(out_dir, ledger, song_urls, expected_total):
    """Tracks finished IN THIS RUN, for the progress bar.

    Counting every audio file in the folder is wrong: for a single track the folder is
    the whole download folder (hundreds of songs), so the bar started at 100%, and an
    album downloaded before started full too. Files already there are the baseline."""
    baseline = _count_audio_files(out_dir)
    already = sum(1 for u in song_urls if ledger.get(u, {}).get("status") == "success")

    def count():
        fresh = max(0, _count_audio_files(out_dir) - baseline)
        done = sum(1 for u in song_urls if ledger.get(u, {}).get("status") == "success")
        return min(expected_total, max(done, already + fresh))
    return count


def _read_errors_file(path: str) -> dict:
    result = {}
    if not os.path.exists(path):
        return result
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                m = re.match(r"^(\S+)\s*-\s*(.+)$", line)
                if m:
                    result[m.group(1)] = m.group(2)
                else:
                    result[line] = line
    except Exception:
        pass
    return result


def _read_archive(path: str) -> set:
    urls = set()
    if not os.path.exists(path):
        return urls
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("http"):
                    urls.add(line)
    except Exception:
        pass
    return urls


def _write_failed_report(out_dir: str, meta_name: str | None, failed_records: list,
                          expected_total: int, final_count: int,
                          error_breakdown: dict) -> str:
    report_path = os.path.join(out_dir, "failed_downloads.txt")
    missing = len(failed_records)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("LinkCatty — failed / missing tracks report\n")
        f.write(f"Playlist or album : {meta_name or 'Unknown'}\n")
        f.write(f"Generated         : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Expected tracks   : {expected_total}\n")
        f.write(f"Downloaded tracks : {final_count}\n")
        f.write(f"Missing tracks    : {missing}\n")
        f.write("-" * 60 + "\n")
        if error_breakdown:
            f.write("Breakdown by cause:\n")
            for label, count in error_breakdown.items():
                f.write(f"  • {label}: {count}\n")
            f.write("-" * 60 + "\n")
        f.write("Per-track detail:\n\n")
        for r in failed_records:
            title = r.get("title") or "Unknown title"
            artist = r.get("artist") or "Unknown artist"
            etype = _ERROR_LABELS.get(r.get("error_type"),
                                       r.get("error_type") or "other")
            tried = ", ".join(r.get("providers_tried") or []) or "n/a"
            f.write(f"{r['url']}\n")
            f.write(f"    {artist} - {title}\n")
            f.write(f"    Cause      : {etype}\n")
            f.write(f"    Last error : {r.get('last_error') or 'n/a'}\n")
            f.write(f"    Providers tried : {tried}\n")
            f.write(f"    Attempts   : {r.get('attempts', 0)}\n\n")
        f.write("-" * 60 + "\n")
        f.write("The same list, machine-readable: failed_downloads.json (same folder).\n\n")
        f.write(
            "Tip: re-run the same playlist/album download again (even in a new\n"
            "session). LinkCatty keeps a machine-readable ledger next to this\n"
            "report (.linkcatty_state.json) plus spotdl's own archive file, so\n"
            "already-downloaded tracks are always skipped and only the tracks\n"
            "listed above are retried.\n"
        )
        if error_breakdown and _ERROR_LABELS["no_match"] in error_breakdown:
            f.write(
                "\nMost of these failed with 'no match found', not a rate limit —\n"
                "the audio-provider fallback chain still couldn't find a usable\n"
                "match, most often for regional / film-soundtrack tracks whose\n"
                "Spotify title differs a lot from how it's titled on YouTube.\n"
            )
        if error_breakdown and _ERROR_LABELS["blocked_or_rate_limited"] in error_breakdown:
            f.write(
                "\nSome failures were YouTube's bot check on this connection.\n"
                "Wait a few minutes, turn on a VPN, or set spotify.cookies_from_browser\n"
                "(for example \"firefox\") in settings.json to use your logged-in browser,\n"
                "then run the same link again: only the missing tracks are retried.\n"
            )
    _write_failed_json(out_dir, meta_name, failed_records, expected_total, final_count)
    return report_path


def _write_failed_json(out_dir, meta_name, failed_records, expected_total, final_count) -> None:
    """failed_downloads.json: what is missing and why, for people and for scripts."""
    try:
        data = {
            "name": meta_name or "Unknown",
            "generated": datetime.now().isoformat(timespec="seconds"),
            "expected": expected_total,
            "downloaded": final_count,
            "missing": len(failed_records),
            "tracks": [{
                "url": r.get("url"), "title": r.get("title"), "artist": r.get("artist"),
                "cause": _ERROR_LABELS.get(r.get("error_type"), r.get("error_type") or "other"),
                "cause_key": r.get("error_type") or "other",
                "last_error": r.get("last_error"),
                "attempts": r.get("attempts", 0),
                "sources_tried": r.get("providers_tried") or [],
                "last_attempt": r.get("last_attempt"),
            } for r in failed_records],
        }
        with open(os.path.join(out_dir, "failed_downloads.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def extract_spotify_id(url: str, item_type: str) -> str | None:
    m = re.search(rf"{item_type}/([a-zA-Z0-9]+)", url)
    return m.group(1) if m else None


def is_spotify_url(url: str, item_type: str) -> bool:
    return bool(re.match(r"^https?://", url)) and f"spotify.com/{item_type}/" in url


# ─────────────────────────────────────────────────────────────────────
#  Workflow runners
# ─────────────────────────────────────────────────────────────────────

def create_downloader(config):
    try:
        return SpotifyDownloader(config)
    except Exception as err:
        print_error(str(err))
        return None


def run_spotify_workflow(config, choice: str) -> None:
    downloader = create_downloader(config)
    if downloader is None:
        pause()
        return

    item_type = {"1": "track", "2": "album", "3": "playlist"}[choice]
    while True:
        url = ask_url(f"Spotify {item_type}")
        if not url:
            return
        if not is_spotify_url(url, item_type):
            print_error(
                f"Invalid Spotify {item_type} URL",
                f"Use a link containing spotify.com/{item_type}/.",
            )
            continue

        if choice == "1":
            downloader.download_single_track(url)
        elif choice == "2":
            downloader.download_album(url)
        elif choice == "3":
            downloader.download_playlist(url)

        if not confirm(f"\nProcess another Spotify {item_type}?"):
            return


def run(config) -> None:
    while True:
        choice = show_menu("🎵 Spotify Downloader", [
            "Download single track",
            "Download album",
            "Download playlist",
        ])
        if choice in (None, "0"):
            return
        try:
            run_spotify_workflow(config, choice)
        except Exception as err:
            stop_spinner()
            print_error(
                f"Spotify workflow error: {err}",
                "You remain in the Spotify Downloader.",
            )
            pause()

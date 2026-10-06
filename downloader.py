"""Core YouTube download logic (reused by CLI and Flask)."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from pytubefix import YouTube
from pytubefix.exceptions import PytubeFixError

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "download"

# Accepts watch, youtu.be, shorts, embed, music.youtube...
YOUTUBE_URL_RE = re.compile(
    r"^(https?://)?(www\.|m\.|music\.)?(youtube\.com/(watch|shorts|embed|live)|youtu\.be/).+$"
)


def sanitize_filename(filename: str, max_length: int = 150) -> str:
    """Remove filesystem-unsafe characters and truncate safely."""
    invalid_chars = '<>:"/\\|?*\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    cleaned = "".join("_" if c in invalid_chars else c for c in filename)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip()
    return cleaned or "video"


def unique_path(directory: Path, filename: str) -> Path:
    """Avoid overwriting existing files by appending (1), (2), ..."""
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    counter = 1
    while True:
        alt = directory / f"{stem} ({counter}){suffix}"
        if not alt.exists():
            return alt
        counter += 1


def ensure_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "ffmpeg não encontrado. Instale com: sudo apt install ffmpeg"
        )
    return ffmpeg


def get_youtube(url: str) -> YouTube:
    url = (url or "").strip()
    if not url or not YOUTUBE_URL_RE.match(url):
        raise ValueError("URL do YouTube inválida.")
    try:
        return YouTube(url)
    except PytubeFixError as exc:
        raise RuntimeError(f"Não foi possível acessar o vídeo: {exc}") from exc
    except Exception as exc:  # regex match, unavailable, network...
        raise RuntimeError(f"Não foi possível acessar o vídeo: {exc}") from exc


def get_video_info(url: str) -> dict:
    """Fetch metadata without downloading (used by the web UI)."""
    yt = get_youtube(url)
    try:
        length = yt.length
    except Exception:
        length = 0
    streams = yt.streams
    progressive = streams.filter(progressive=True, file_extension="mp4").order_by(
        "resolution"
    )
    resolutions = sorted(
        {s.resolution for s in progressive if s.resolution},
        key=lambda r: int(r.replace("p", "")),
        reverse=True,
    )
    has_adaptive = bool(
        streams.filter(adaptive=True, only_video=True, file_extension="mp4").first()
    )
    return {
        "title": yt.title,
        "author": yt.author,
        "length": length,
        "views": getattr(yt, "views", 0),
        "thumbnail_url": getattr(yt, "thumbnail_url", ""),
        "resolutions": resolutions,
        "has_adaptive_only": (not resolutions) and has_adaptive,
    }


def _best_progressive_mp4(yt: YouTube):
    return (
        yt.streams.filter(progressive=True, file_extension="mp4")
        .order_by("resolution")
        .desc()
        .first()
    )


def _best_adaptive_video_mp4(yt: YouTube):
    video = (
        yt.streams.filter(adaptive=True, only_video=True, file_extension="mp4")
        .order_by("resolution")
        .desc()
        .first()
    )
    if video is None:  # fallback: any adaptive video (webm included)
        video = (
            yt.streams.filter(adaptive=True, only_video=True)
            .order_by("resolution")
            .desc()
            .first()
        )
    return video


def _best_audio(yt: YouTube):
    audio = yt.streams.get_audio_only()
    if audio is None:
        audio = (
            yt.streams.filter(only_audio=True).order_by("abr").desc().first()
        )
    return audio


def _merge_video_audio(
    video_path: Path, audio_path: Path, output_path: Path
) -> Path:
    ensure_ffmpeg()
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    try:
        subprocess.run(
            cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Falha ao unir vídeo + áudio (ffmpeg): "
            f"{exc.stderr.decode(errors='ignore')[-500:]}"
        ) from exc
    return output_path


def download_video(url: str, output_dir: Path | None = None) -> Path:
    """Download best-quality MP4 with audio.

    Strategy:
      1. Prefer progressive MP4 (video+audio in one file).
      2. Fallback (bug fix): adaptive-only videos have NO progressive
         stream -> get_highest_resolution() returns None. In that case
         download best adaptive video + best audio and merge with ffmpeg.
    """
    output_dir = Path(output_dir) if output_dir else DOWNLOAD_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    yt = get_youtube(url)
    title = sanitize_filename(yt.title)

    # 1) Progressive path (simplest, no merge needed)
    stream = _best_progressive_mp4(yt)
    if stream is not None:
        dest = unique_path(output_dir, f"{title}.mp4")
        stream.download(output_path=str(output_dir), filename=dest.name)
        return dest

    # 2) Adaptive-only fallback (this was the reported AttributeError:
    #    'NoneType' object has no attribute 'download')
    video = _best_adaptive_video_mp4(yt)
    audio = _best_audio(yt)
    if video is None or audio is None:
        raise RuntimeError("Nenhum stream de vídeo/áudio disponível para este vídeo.")

    tmp_video = unique_path(output_dir, f"{title}.video.{video.subtype}")
    tmp_audio = unique_path(output_dir, f"{title}.audio.{audio.subtype}")
    try:
        video.download(output_path=str(output_dir), filename=tmp_video.name)
        audio.download(output_path=str(output_dir), filename=tmp_audio.name)
        dest = unique_path(output_dir, f"{title}.mp4")
        _merge_video_audio(tmp_video, tmp_audio, dest)
        return dest
    finally:
        for tmp in (tmp_video, tmp_audio):
            try:
                if tmp.exists() and tmp != dest:
                    tmp.unlink()
            except OSError:
                pass


def download_mp3(url: str, output_dir: Path | None = None) -> Path:
    """Download audio-only and convert to MP3."""
    output_dir = Path(output_dir) if output_dir else DOWNLOAD_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    ensure_ffmpeg()

    yt = get_youtube(url)
    title = sanitize_filename(yt.title)

    stream = _best_audio(yt)
    if stream is None:
        raise RuntimeError("Nenhum stream de áudio disponível para este vídeo.")

    tmp_file = unique_path(output_dir, f"{title}.{stream.subtype}")
    mp3_file = unique_path(output_dir, f"{title}.mp3")
    try:
        stream.download(output_path=str(output_dir), filename=tmp_file.name)
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(tmp_file),
            "-vn",
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(mp3_file),
        ]
        try:
            subprocess.run(
                cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as exc:
            if mp3_file.exists():
                mp3_file.unlink(missing_ok=True)
            raise RuntimeError(
                "Falha na conversão para MP3: "
                f"{exc.stderr.decode(errors='ignore')[-500:]}"
            ) from exc
        return mp3_file
    finally:
        try:
            if tmp_file.exists():
                tmp_file.unlink()
        except OSError:
            pass

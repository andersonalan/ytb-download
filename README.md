# YouTube Downloader (MP4 + MP3)

A simple and robust YouTube downloader with a command-line interface and a Flask web UI. Download videos as MP4 (with audio) or extract audio as MP3.

Built as a portfolio project focused on correct error handling, real-world YouTube edge cases, and clean, reusable Python code.

## Features

- **MP4 video download with audio guaranteed** — prefers progressive streams, falls back to adaptive video + audio merge via `ffmpeg`.
- **MP3 audio extraction** — best audio stream converted with `libmp3lame`.
- **CLI + Web UI** — same core logic (`downloader.py`) powers both `main.py` and the Flask app.
- **YouTube metadata preview** — title, author, duration, thumbnail (web flow).
- **Safe filenames** — sanitizes `< > : " / \ | ? *`, trims whitespace/dots, truncates, avoids overwrites with `(1)`, `(2)` suffixes.
- **Input validation** — rejects non-YouTube URLs early with a clear message.
- **Graceful errors** — unavailable videos, network failures, missing `ffmpeg`, and conversion errors are reported, never raw tracebacks.
- **Downloadable files** — web UI lists recent files and serves them as attachments with path-traversal protection.

## Bug fixed

**`AttributeError: 'NoneType' object has no attribute 'download'`**

`YouTube(...).streams.get_highest_resolution()` returns `None` for adaptive-only videos (no progressive MP4 stream — increasingly common on YouTube). The old code called `.download()` on that `None` unconditionally.

Fix in `downloader.py:download_video`:

1. Try best progressive MP4 first.
2. If `None`, download best adaptive video + best audio and merge with `ffmpeg` (`-c:v copy -c:a aac -movflags +faststart`).
3. Clean up temp files even on failure; raise a human-readable `RuntimeError` if no streams exist.

Verified with `https://www.youtube.com/watch?v=bTw5iRl9PWg` (20 adaptive streams, 0 progressive): produces a ~41 MB playable MP4, and MP3 conversion yields correct ~200 s duration.

## Tech stack

- Python 3.11+
- [pytubefix](https://github.com/JuanBindez/pytubefix) — YouTube stream access
- [Flask](https://flask.palletsprojects.com/) 3.x — web UI
- `ffmpeg` (system binary) — merge + MP3 conversion

## Requirements

- Python 3.11+
- `ffmpeg` on `PATH`:
  ```bash
  sudo apt install ffmpeg        # Debian/Ubuntu
  brew install ffmpeg            # macOS
  ```
  Verify: `ffmpeg -version` and `ffmpeg -hide_banner -h encoder=libmp3lame`.

## Installation

```bash
git clone https://github.com/andersonalan/ytb-download.git
cd ytb-download

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

## Usage

### CLI

```bash
python main.py
```

```
Digite a URL do vídeo: https://www.youtube.com/watch?v=...
O que você deseja baixar?
1 - Vídeo (MP4)
2 - Apenas áudio (MP3)
Escolha uma opção: 1
```

Files are saved to `./download/` (auto-created, git-ignored).

### Web UI

```bash
python app.py
# open http://127.0.0.1:5000
```

1. Paste the video URL.
2. Choose **Vídeo (MP4)** or **Áudio (MP3)**.
3. Click **Baixar**, then **Salvar** the file.
4. Recent files are listed below the form.

For production, use a WSGI server instead of `app.run(debug=True)`:

```bash
pip install gunicorn
gunicorn app:app --bind 127.0.0.1:8000
```

## Project structure

```
.
├── app.py               # Flask web UI (/, /download, /files/<name>)
├── downloader.py        # Core logic: info, MP4, MP3, ffmpeg merge
├── main.py              # CLI wrapper over downloader.py
├── requirements.txt     # Flask, pytubefix (direct deps only)
├── templates/
│   └── index.html       # Form, result card, recent files
├── static/
│   └── style.css        # Dark minimal theme
└── download/            # Output dir (git-ignored)
```

## API / modules

- `get_video_info(url) -> dict` — title, author, length, views, thumbnail, resolutions.
- `download_video(url, output_dir?) -> Path` — MP4 with audio (progressive or merged).
- `download_mp3(url, output_dir?) -> Path` — MP3 via best audio + `ffmpeg`.
- `sanitize_filename(name)`, `unique_path(dir, name)`, `ensure_ffmpeg()`, `get_youtube(url)`.

Web routes:

| Method | Route                | Description                          |
|--------|----------------------|--------------------------------------|
| GET    | `/`                  | Form + recent files                  |
| POST   | `/download`          | Validates, downloads, shows result   |
| GET    | `/files/<filename>`  | Serves file as attachment            |

## Configuration

| Item | Default | Notes |
|------|---------|-------|
| Output dir | `./download/` | `downloader.DOWNLOAD_DIR`; override per-call via `output_dir` |
| Flask secret | `"ytb-download-dev-key"` | Set a real `app.secret_key` via env var in production |
| Flask host/port | `127.0.0.1:5000` | Change in `app.py` or use gunicorn |

## Limitations & roadmap

- Synchronous downloads block the request (fine for personal use; for scale, add a job queue + progress via SSE/websockets).
- No quality selector yet (`get_video_info` already exposes `resolutions` for this).
- No playlist support.
- No tests yet — suggested next step: `pytest` for `sanitize_filename`, `unique_path`, URL validation, and Flask smoke tests.

## License

No license file yet. If you want others to reuse this, add an MIT `LICENSE` (suggested for portfolio projects).

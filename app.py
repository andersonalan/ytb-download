"""Flask web UI for YouTube downloads."""
from __future__ import annotations

import os
from pathlib import Path

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from downloader import (
    DOWNLOAD_DIR,
    download_mp3,
    download_video,
    get_video_info,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ytb-download-dev-key")


def list_downloads(limit: int = 20) -> list[dict]:
    if not DOWNLOAD_DIR.exists():
        return []
    files = sorted(
        (p for p in DOWNLOAD_DIR.iterdir() if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    result = []
    for p in files[:limit]:
        size_mb = p.stat().st_size / (1024 * 1024)
        result.append({"name": p.name, "size_mb": f"{size_mb:.1f}"})
    return result


@app.get("/")
def index():
    return render_template("index.html", files=list_downloads(), result=None)


@app.post("/download")
def download():
    url = request.form.get("url", "").strip()
    fmt = request.form.get("format", "mp4")

    if not url:
        flash("Informe a URL do vídeo.", "error")
        return redirect(url_for("index"))

    try:
        info = get_video_info(url)
    except (ValueError, RuntimeError) as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))

    try:
        if fmt == "mp3":
            output = download_mp3(url)
        else:
            output = download_video(url)
    except (ValueError, RuntimeError) as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))

    result = {
        "title": info.get("title", output.name),
        "author": info.get("author", ""),
        "filename": output.name,
    }
    return render_template(
        "index.html", files=list_downloads(), result=result
    )


@app.get("/files/<path:filename>")
def serve_file(filename: str):
    directory: Path = DOWNLOAD_DIR.resolve()
    target = (directory / filename).resolve()
    # Prevent path traversal
    if directory not in target.parents and target != directory:
        flash("Arquivo inválido.", "error")
        return redirect(url_for("index"))
    return send_from_directory(directory, target.name, as_attachment=True)


if __name__ == "__main__":
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug, host="0.0.0.0", port=port)

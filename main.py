from pathlib import Path
from pytubefix import YouTube
from pytubefix.cli import on_progress
import subprocess


DOWNLOAD_DIR = Path("/home/anderson/dev/python/ytbd/download")


def sanitize_filename(filename):
    """Remove caracteres que podem causar problemas no nome do arquivo."""
    invalid_chars = '<>:"/\\|?*'
    return "".join("_" if char in invalid_chars else char for char in filename)


def download_video(url):
    yt = YouTube(url, on_progress_callback=on_progress)

    print(f"\nTítulo: {yt.title}")
    print("Baixando vídeo...")

    stream = yt.streams.get_highest_resolution()

    filename = sanitize_filename(yt.title)
    output_file = DOWNLOAD_DIR / f"{filename}.mp4"

    stream.download(
        output_path=DOWNLOAD_DIR,
        filename=output_file.name
    )

    print(f"\nDownload concluído:")
    print(output_file)


def download_mp3(url):
    yt = YouTube(url, on_progress_callback=on_progress)

    print(f"\nTítulo: {yt.title}")
    print("Baixando áudio...")

    stream = yt.streams.get_audio_only()

    filename = sanitize_filename(yt.title)
    temp_file = DOWNLOAD_DIR / f"{filename}.{stream.subtype}"
    mp3_file = DOWNLOAD_DIR / f"{filename}.mp3"

    stream.download(
        output_path=DOWNLOAD_DIR,
        filename=temp_file.name
    )

    print("Convertendo para MP3...")

    subprocess.run(
        [
            "ffmpeg",
            "-i", str(temp_file),
            "-vn",
            "-codec:a", "libmp3lame",
            "-q:a", "2",
            str(mp3_file)
        ],
        check=True
    )

    temp_file.unlink()

    print(f"\nDownload concluído:")
    print(mp3_file)


def main():
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    url = input("Digite a URL do vídeo: ").strip()

    print("\nO que você deseja baixar?")
    print("1 - Vídeo")
    print("2 - Apenas áudio (MP3)")

    option = input("\nEscolha uma opção: ").strip()

    if option == "1":
        download_video(url)

    elif option == "2":
        download_mp3(url)

    else:
        print("Opção inválida.")


if __name__ == "__main__":
    main()


"""CLI for YouTube downloads (thin wrapper over downloader.py)."""
from downloader import DOWNLOAD_DIR, download_mp3, download_video


def main() -> None:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    url = input("Digite a URL do vídeo: ").strip()

    print("\nO que você deseja baixar?")
    print("1 - Vídeo (MP4)")
    print("2 - Apenas áudio (MP3)")

    option = input("\nEscolha uma opção: ").strip()

    try:
        if option == "1":
            print("Baixando vídeo...")
            output_file = download_video(url)
            print(f"\nDownload concluído:\n{output_file}")
        elif option == "2":
            print("Baixando áudio...")
            output_file = download_mp3(url)
            print(f"\nDownload e conversão concluídos:\n{output_file}")
        else:
            print("Opção inválida.")
    except (ValueError, RuntimeError) as exc:
        print(f"\nErro: {exc}")
    except KeyboardInterrupt:
        print("\nOperação cancelada.")


if __name__ == "__main__":
    main()

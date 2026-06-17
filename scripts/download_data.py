from pathlib import Path
from urllib.request import urlretrieve


ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "web-redditEmbeddings-subreddits.csv": "https://snap.stanford.edu/data/web-redditEmbeddings-subreddits.csv",
    "web-redditEmbeddings-users.csv": "https://snap.stanford.edu/data/web-redditEmbeddings-users.csv",
}
RAW_DIR = ROOT / "data" / "raw"


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in FILES.items():
        out = RAW_DIR / filename
        if out.exists() and out.stat().st_size > 0:
            print(f"Arquivo ja existe: {out} ({out.stat().st_size} bytes)")
            continue
        print(f"Baixando {url}")
        urlretrieve(url, out)
        print(f"Salvo em {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()

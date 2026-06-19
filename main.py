import subprocess
import sys
from pathlib import Path


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, cwd=Path(__file__).resolve().parent)


def main() -> None:
    python = sys.executable
    run([python, "scripts/download_data.py"])
    run([python, "scripts/build_graph.py", "--k", "10"])
    run(
        [
            python,
            "scripts/analyze_graph.py",
            "--benchmark-runs",
            "30",
            "--robustness-runs",
            "30",
            "--path-samples",
            "16",
            "--random-graphs",
            "5",
        ]
    )


if __name__ == "__main__":
    main()

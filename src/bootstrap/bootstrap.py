from pathlib import Path
import shutil

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = Path(__file__).parent / "templates"

STRUCTURE = {
    "directories": ["data/klines", "data/state", "logs"],
    "files": [
        (".env.secret", ".env.secret.template"),
    ],
}


def ensure_directory(path: Path):
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)


def ensure_file_from_template(target: Path, template: Path):
    if not target.exists():
        shutil.copy(template, target)


def run_bootstrap():
    for dir_path in STRUCTURE["directories"]:
        print(f"[init] Created directory {dir_path}")
        ensure_directory(PROJECT_ROOT / dir_path)

    for target, template in STRUCTURE["files"]:
        print(f"[init] Created file {target} from template. Remember to fill the required data in.")
        ensure_file_from_template(PROJECT_ROOT / target, TEMPLATES_DIR / template)

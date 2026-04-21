from pathlib import Path
import shutil
import logging

from src.config import Config

config = Config()

logger = logging.getLogger("[init]")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = Path(__file__).parent / "templates"

STRUCTURE = {
    "directories": [
        f"data/klines/{config.run_id}",
        f"data/state/{config.run_id}",
        f"data/chart/{config.run_id}",
        "data/symbol_lists",
        f"logs/{config.run_id}",
    ],
    "files": [
        (".env.secret", ".env.secret.template"),
        ("data/symbol_lists/symbols.csv", "data/symbol_lists/symbols.csv.template"),
    ],
}


def ensure_directory(path: Path):
    if not path.exists():
        logger.info(f"Created directory {path}")
        path.mkdir(parents=True, exist_ok=True)


def ensure_file_from_template(target: Path, template: Path):
    if not target.exists():
        logger.info(
            f"Created file {target} from template. Remember to fill the required data in."
        )
        shutil.copy(template, target)


def run_bootstrap():
    for dir_path in STRUCTURE["directories"]:
        ensure_directory(PROJECT_ROOT / dir_path)

    for target, template in STRUCTURE["files"]:
        ensure_file_from_template(PROJECT_ROOT / target, TEMPLATES_DIR / template)

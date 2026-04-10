from csv import reader
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Build path relative to the module
csv_path = BASE_DIR / "data" / "precisions" / "precisions.csv"

try:
    with open(csv_path) as f:
        precisions_csv = reader(f)

        precisions_dict: dict[str, int] = {}

        next(precisions_csv)  # skip header
        for row in precisions_csv:
            if row[1]:
                precisions_dict[row[0]] = int(row[1])


except FileNotFoundError:
    print(f"[fatal] Precisions CSV file not found at {csv_path}")
    raise


def get_precision(symbol: str) -> int | None:
    sanitized_symbol: str = symbol.upper().replace("USDT", "")
    return precisions_dict.get(sanitized_symbol, None)

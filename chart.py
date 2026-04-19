import sys

from PyQt6.QtWidgets import QApplication
from src.visualization import ChartWindow

if len(sys.argv) < 2:
    print("Usage: python chart_viewer.py SYMBOL")
    sys.exit(1)

symbol = sys.argv[1]

app = QApplication(sys.argv)
window = ChartWindow(symbol)
window.show()
sys.exit(app.exec())

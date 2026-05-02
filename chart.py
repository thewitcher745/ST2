import sys

from PyQt6.QtWidgets import QApplication
from src.visualization import ChartWindow

app = QApplication(sys.argv)
window = ChartWindow()
window.show()
sys.exit(app.exec())

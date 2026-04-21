from datetime import datetime
from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import QTimer
from ormsgpack import unpackb
import pandas as pd
import numpy as np

from .chart_widget import ChartWidget
from src.config import Config


class ChartWindow(QMainWindow):
    def __init__(self, symbol: str, data_dir: str = f"data/chart/{Config().run_id}"):
        super().__init__()
        self.symbol = symbol
        self._data_dir = data_dir
        self._filepath = f"{data_dir}/{symbol}.pack"

        self._chart_widget = ChartWidget()

        # Central widget with layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.setWindowTitle(f"Live Chart - {symbol}")
        self.resize(1360, 768)

        layout = QVBoxLayout(central_widget)

        layout.addLayout(self._init_labels())
        layout.addWidget(self._chart_widget)

        # Timer to read file every 2 seconds
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(2000)

    def _init_labels(self) -> QHBoxLayout:
        placeholder_info_text = """
Symbol: {self.symbol}
Candles: 
Blocks: 
Last close:
Last candle time:
Last update: {datetime.now()}
            """

        placeholder_cursor_text = """Index:
Time:
O:
H:
L:
C:"""

        # Horizontal layout for the two labels
        labels_layout = QHBoxLayout()

        # Label showing updates
        self._info_label = QLabel(placeholder_info_text, self)
        labels_layout.addWidget(self._info_label)

        # Label showing the candle the cursor is on

        self._cursor_label = QLabel(placeholder_cursor_text, self)
        labels_layout.addWidget(self._cursor_label)
        self._chart_widget.cursor_moved.connect(self._cursor_label.setText)

        return labels_layout

    def update_data(self):
        try:
            with open(self._filepath, "rb") as f:
                packed_data = f.read()

            data = unpackb(packed_data)

            # Extract info
            klines_data = data["klines"]
            blocks = data["blocks"]

            times = np.array(klines_data["time"])
            closes = np.array(klines_data["close"])

            n_candles = len(closes)
            n_blocks = len(blocks)
            last_close = closes[-1]
            last_time = pd.Timestamp(times[-1])

            # Display in label
            info = f"""
            Symbol: {self.symbol}
            Candles: {n_candles}
            Blocks: {n_blocks}
            Last close: {last_close:.2f}
            Last candle time: {last_time}
            Last update: {datetime.now()}
            """
            self._info_label.setText(info)
            self._chart_widget.update_chart(klines_data, blocks)

        except FileNotFoundError:
            self._info_label.setText(f"Waiting for data file: {self._filepath}")
        except Exception as e:
            self._info_label.setText(f"Error: {str(e)}")

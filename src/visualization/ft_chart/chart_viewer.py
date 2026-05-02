from datetime import datetime
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import QTimer
from ormsgpack import unpackb
import pandas as pd
import numpy as np
import os
from pyqtgraph import ComboBox
from pyqtgraph.Qt.QtWidgets import QComboBox

from .chart_widget import ChartWidget


class ChartWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._filedir: str | None = None
        self._symbol: str | None = None

        self._info_label = None
        self._cursor_label = None

        self._chart_widget = ChartWidget()

        # Central widget with layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        # self.setWindowTitle(f"Live Chart - {symbol}")
        self.resize(1360, 768)

        layout = QVBoxLayout(central_widget)

        layout.addLayout(self._init_top_section())
        layout.addWidget(self._chart_widget)

        # Timer to read file every 2 seconds
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(2000)

    def _init_top_section(self) -> QHBoxLayout:
        top_section_layout = QHBoxLayout()

        top_section_layout.addLayout(self._init_menus())
        top_section_layout.addLayout(self._init_labels())

        return top_section_layout

    def _init_menus(self) -> QVBoxLayout:
        menus_layout = QVBoxLayout()
        menus_layout.setSpacing(5)
        
        # Directory dropdown with label
        dir_label = QLabel("Run ID:")
        menus_layout.addWidget(dir_label)
        
        dirs = os.listdir("data/chart")
        self.dir_menu = ComboBox(items=dirs)
        self.dir_menu.currentIndexChanged.connect(self._on_dir_change)
        menus_layout.addWidget(self.dir_menu)

        if self.dir_menu.currentText() is not None:
            self._filedir = self.dir_menu.currentText()

        # Symbol dropdown with label
        symbol_label = QLabel("Symbol:")
        menus_layout.addWidget(symbol_label)
        
        self.symbol_menu = QComboBox()
        self.symbol_menu.currentIndexChanged.connect(self._on_symbol_change)
        menus_layout.addWidget(self.symbol_menu)

        # Initialize symbol_menu with files from first directory if available
        if dirs:
            self._update_symbol_menu(dirs[0])

        menus_layout.addStretch()

        return menus_layout

    def _on_dir_change(self, index):
        selected_dir = self.dir_menu.currentText()
        self._filedir = selected_dir
        self._update_symbol_menu(selected_dir)
        self.update_data()

    def _on_symbol_change(self, index):
        self._symbol = self.symbol_menu.currentText()
        self.update_data()
        self._chart_widget.apply_auto_zoom()

    def _update_symbol_menu(self, directory):
        self.symbol_menu.clear()
        files = os.listdir(f"data/chart/{directory}")
        symbols = [f.replace(".pack", "") for f in files]
        self.symbol_menu.addItems(symbols)

    @property
    def _filename(self) -> str:
        if self._symbol is not None:
            return self._symbol + ".pack"
        else:
            return ""

    @property
    def _filepath(self) -> str | None:
        if self._filename is None or self._filedir is None:
            return None

        return os.path.join("data", "chart", self._filedir, self._filename)

    def _init_labels(self) -> QVBoxLayout:

        placeholder_info_text = f"""
Symbol: {self._symbol}
Candles: 
Blocks: 
Last close:
Last candle time:
Last update: {datetime.now()}
            """

        placeholder_cursor_text = """
Index:
Time:
O:
H:
L:
C:"""

        # Horizontal layout for the two labels
        labels_layout = QVBoxLayout()

        # Label showing updates
        self._info_label = QLabel(placeholder_info_text, self)
        labels_layout.addWidget(self._info_label)

        # Label showing the candle the cursor is on

        self._cursor_label = QLabel(placeholder_cursor_text, self)
        labels_layout.addWidget(self._cursor_label)
        self._chart_widget.cursor_moved.connect(self._cursor_label.setText)

        return labels_layout

    def update_data(self):
        if self._filepath is None:
            return
        if (
            self._info_label is None
            or self._chart_widget is None
            or self._cursor_label is None
        ):
            return

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
Symbol: {self._symbol}
Candles: {n_candles}
Blocks: {n_blocks}
Last close: {last_close}
Last candle time: {last_time}
Last update: {datetime.now()}
            """
            self._info_label.setText(info)
            self._chart_widget.update_chart(klines_data, blocks)

        except FileNotFoundError as e:
            print(e)
            self._info_label.setText(f"Waiting for data file: {self._filename}")
        except Exception as e:
            self._info_label.setText(f"Error: {str(e)}")

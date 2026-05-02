import time
from typing import Optional, cast
from PyQt6 import QtCore, QtGui
from PyQt6.QtWidgets import QVBoxLayout, QWidget
from pandas import Timestamp
import pyqtgraph as pg
import numpy as np


class ChartWidget(QWidget):
    cursor_moved = QtCore.pyqtSignal(str)

    def __init__(self, chart_title: str = "Forward test live chart"):
        super().__init__()
        self.widget = pg.PlotWidget()

        self._is_auto_zooming = True
        self._auto_zoom_n_klines = 80  # Number of KLines to auto-zoom on
        self._auto_zoom_y_margin = 0.15  # 15% padding top/bottom (KLines occupy 70%)
        self._auto_zoom_x_margin = 0.20  # 20% empty space on right
        self._auto_zoom_timeout = 60  # Seconds before resuming auto-zoom
        self._last_manual_zoom = None

        layout = QVBoxLayout(self)
        layout.addWidget(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)  # No margins

        self.indices: Optional[np.ndarray] = None
        self.times: Optional[np.ndarray] = None
        self.opens: Optional[np.ndarray] = None
        self.highs: Optional[np.ndarray] = None
        self.lows: Optional[np.ndarray] = None
        self.closes: Optional[np.ndarray] = None

        # Crosshair
        self.vLine = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(color=(50, 50, 50, 150), width=1),
        )
        self.hLine = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen(color=(50, 50, 50, 150), width=1),
        )

        # Cursor price level indicator
        self.y_value_label = pg.TextItem(anchor=(1, 1), color="white")
        self.widget.addItem(self.y_value_label)

        # Connect mouse move signal
        scene = cast(pg.GraphicsScene, self.widget.scene())
        scene.sigMouseMoved.connect(self.on_mouse_move)

        if self.widget.plotItem is not None:
            view_box: Optional[pg.ViewBox] = self.widget.plotItem.vb
            if view_box is not None:
                view_box.sigRangeChangedManually.connect(self.on_manual_range_change)

    def _clear_chart(self):
        """Clears all elements from the chart other than the crosshair."""
        self.widget.clear()
        self.widget.addItem(self.vLine)
        self.widget.addItem(self.hLine)
        self.widget.addItem(self.y_value_label)

    def on_manual_range_change(self, view_box: pg.ViewBox):
        self._last_manual_zoom = time.time()

    def _should_auto_zoom(self):
        """Checks if auto-zoom should occur based on a timeout."""
        if self._last_manual_zoom is None:
            return True

        if (time.time() - self._last_manual_zoom) > self._auto_zoom_timeout:
            return True

        return False

    def apply_auto_zoom(self):
        """Checks auto-zoom conditions and applies it if applicable."""

        if (
            self.indices is None
            or self.highs is None
            or self.lows is None
            or len(self.indices) == 0
        ):
            return

        last_n_indices = self.indices[-self._auto_zoom_n_klines :]
        last_n_highs = self.highs[-self._auto_zoom_n_klines :]
        last_n_lows = self.lows[-self._auto_zoom_n_klines :]

        LL = np.min(last_n_lows)  # Lowest low in the data in the zooming range
        HH = np.max(last_n_highs)  # Highest high in the data in the zooming range

        klines_ratio = (
            1 - 2 * self._auto_zoom_y_margin
        )  # Ratio of the chart occupied by the KLines

        y_max = 0.5 * (HH + LL + (HH - LL) / klines_ratio)
        y_min = 0.5 * (HH + LL - (HH - LL) / klines_ratio)

        x_min = last_n_indices[0]
        time_span = last_n_indices[-1] - x_min
        x_max = last_n_indices[-1] + (time_span * self._auto_zoom_x_margin)

        self.widget.setXRange(x_min, x_max)
        self.widget.setYRange(y_min, y_max)

    def on_mouse_move(self, pos):
        if (
            self.times is None
            or self.opens is None
            or self.highs is None
            or self.lows is None
            or self.closes is None
            or self.indices is None
        ):
            return

        widget_plot_item = self.widget.plotItem
        if widget_plot_item is None:
            return

        view_box = widget_plot_item.vb
        if view_box is None:
            return

        mouse_location = view_box.mapSceneToView(pos)
        x = mouse_location.x()
        y = mouse_location.y()

        # Find the nearest candle to the mouse pointer
        cursor_index = np.argmin(np.abs(self.indices - x))

        cursor_index_offset = self.indices[cursor_index]
        cursor_time = self.times[cursor_index]
        cursor_open = self.opens[cursor_index]
        cursor_high = self.highs[cursor_index]
        cursor_low = self.lows[cursor_index]
        cursor_close = self.closes[cursor_index]

        cursor_text = f"Index: {cursor_index_offset}\nTime: {Timestamp(cursor_time).strftime('%Y-%m-%d %H:%M')}\nO: {cursor_open}\nH: {cursor_high}\nL: {cursor_low}\nC: {cursor_close}"
        self.cursor_moved.emit(cursor_text)

        self.hLine.setPos(y)
        self.vLine.setPos(cursor_index_offset)

        view_range = self.widget.viewRange()
        x_max = view_range[0][1]
        self.y_value_label.setText(f"{y:.6f}")
        self.y_value_label.setPos(x_max, y)

    def update_chart(
        self,
        klines_data: dict,
        blocks: list[dict],
        max_visible=1000,
    ):
        """Draws KLines and blocks from passed-down data."""
        self._clear_chart()

        # Extract klines
        self.times = np.array(klines_data["time"])
        self.opens = np.array(klines_data["open"])
        self.highs = np.array(klines_data["high"])
        self.lows = np.array(klines_data["low"])
        self.closes = np.array(klines_data["close"])
        self.indices = np.arange(len(self.times))

        # Only show last N candles
        full_length = len(self.times)
        if len(self.times) > max_visible:
            offset = full_length - max_visible

            self.times = self.times[-max_visible:]
            self.opens = self.opens[-max_visible:]
            self.highs = self.highs[-max_visible:]
            self.lows = self.lows[-max_visible:]
            self.closes = self.closes[-max_visible:]
            self.indices = np.arange(offset, full_length)

        self._draw_klines(self.indices, self.opens, self.highs, self.lows, self.closes)
        self._draw_blocks(blocks, fallback_end_index=self.indices[-1])

        if self._should_auto_zoom():
            self.apply_auto_zoom()

    def _draw_klines(
        self,
        index: np.ndarray,
        open: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
    ):
        # Updates the KLines data on the chart widget from OHLC + time ndarrays
        bullish_mask = close >= open
        bearish_mask = close < open

        body_width = 0.7 * (index[1] - index[0])
        shadow_width = 0.0001

        bullish_bodies = pg.BarGraphItem(
            x=index[bullish_mask],
            y=(open[bullish_mask] + close[bullish_mask]) / 2,
            height=np.abs(open[bullish_mask] - close[bullish_mask]),
            width=body_width,
            brush="#26a69a",  # Green for bullish
            pen="#26a69a",
        )

        bearish_bodies = pg.BarGraphItem(
            x=index[bearish_mask],
            y=(open[bearish_mask] + close[bearish_mask]) / 2,
            height=np.absolute(open[bearish_mask] - close[bearish_mask]),
            width=body_width,
            brush="#ef5350",  # Red for bearish
            pen="#ef5350",
        )

        bullish_shadows = pg.BarGraphItem(
            x=index[bullish_mask],
            y=(low[bullish_mask] + high[bullish_mask]) / 2,
            height=high[bullish_mask] - low[bullish_mask],
            width=shadow_width,
            brush="#26a69a",  # Green for bullish
            pen="#26a69a",
        )

        bearish_shadows = pg.BarGraphItem(
            x=index[bearish_mask],
            y=(low[bearish_mask] + high[bearish_mask]) / 2,
            height=high[bearish_mask] - low[bearish_mask],
            width=shadow_width,
            brush="#ef5350",  # Red for bearish
            pen="#ef5350",
        )

        self.widget.addItem(bullish_bodies)
        self.widget.addItem(bearish_bodies)
        self.widget.addItem(bullish_shadows)
        self.widget.addItem(bearish_shadows)

    def _draw_blocks(self, blocks: list[dict], fallback_end_index: int):
        """
        Draws blocks given by the forward test. Block data is passed in serialized form.
        Each block dict should have: start_index, end_index (or None), low, high, direction, type
        fallback_end_index is the end index assigned to a block if it has no end_index, aka if it
        hasn't ended.
        """
        for block in blocks:
            end_index = block["end_index"]
            if end_index is None:
                end_index = fallback_end_index

            start_index = block["start_index"]

            high = block["high"]
            low = block["low"]
            height = high - low
            width = end_index - start_index

            rect = pg.QtWidgets.QGraphicsRectItem(
                QtCore.QRectF(start_index, low, width, height)
            )

            # Determine color based on direction
            if block["direction"] == "bullish":
                fill_color = QtGui.QColor(38, 166, 154, 50)  # Green with alpha=50
            else:  # bearish
                fill_color = QtGui.QColor(239, 83, 80, 50)  # Red with alpha=50

            rect.setBrush(QtGui.QBrush(fill_color))
            rect.setPen(QtGui.QColor(0, 0, 0, 0))

            self.widget.addItem(rect)

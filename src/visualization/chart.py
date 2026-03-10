from typing import Any
import plotly.graph_objects as go
from pandas import DataFrame, NaT
import numpy as np


class ChartManager:
    """
    Handles the visualization of trading data.
    """

    def __init__(
        self,
        max_n_candles_visible: int = 150,
        title: str = "Algorithm Visualization",
        output_file: str = "chart.html",
    ):
        self.title = title
        self.output_file = output_file
        self._fig = go.Figure()
        self.max_n_candles_visible = max_n_candles_visible
        self._setup_layout()

    def _setup_layout(self):
        """Unlocks the axes for independent zooming and panning."""
        self._fig.update_layout(
            template="plotly_dark",
            hovermode="x unified",
            dragmode="zoom",
            xaxis_rangeslider_visible=False,
            title=self.title,
            autosize=True,
            width=1800,
            height=900,
            margin=dict(l=20, r=20, t=40, b=20),
            # Configure X-axis interaction
            xaxis=dict(
                fixedrange=False,  # Essential: Allows the axis to be changed
                title="Time",
                # This ensures the axis labels react to the mouse
                anchor="y",
                side="bottom",
            ),
            # Configure Y-axis interaction
            yaxis=dict(
                fixedrange=False,  # Essential: Allows the axis to be changed
                title="Price",
                side="right",  # Put price on the right like TradingView
                autorange=True,  # Fits candles to height automatically
            ),
        )

        # This allows you to scroll to zoom on one axis at a time
        self._fig.update_layout(xaxis_scaleanchor=None)

    def add_candlesticks(self, df: DataFrame, name: str = "Price"):
        """Adds candlestick traces to the figure with index in tooltip."""

        # Ensure we have the integer index available as an array
        df_indices = df.index

        self._fig.add_trace(
            go.Candlestick(
                x=df["time"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name=name,
                increasing_line_color="#26a69a",
                decreasing_line_color="#ef5350",
                # Pass the index to the frontend
                customdata=df_indices,
                # Update the template to show the index (i)
                hovertemplate=(
                    "<b>Index (i): %{customdata}</b><br>"
                    + "O: %{open}<br>"
                    + "H: %{high}<br>"
                    + "L: %{low}<br>"
                    + "C: %{close}<extra></extra>"
                ),
            )
        )

        if len(df) > self.max_n_candles_visible:
            self._zoom_start = df["time"].iloc[-self.max_n_candles_visible]
            self._zoom_end = df["time"].iloc[-1]
            self._should_zoom = True
        else:
            self._should_zoom = False

    def add_zigzag(self, zigzag_df: DataFrame, name: str = "Zigzag"):
        """
        Adds the zigzag line with HH, LH, HL, LL text labels.
        Expects columns: [time, pivot_value, pivot_type, structure]
        """
        if zigzag_df.empty:
            return

        # Determine position: Peaks (1) go 'top center', Valleys (-1) go 'bottom center'
        text_positions = np.where(
            zigzag_df["pivot_type"] == 1, "top center", "bottom center"
        )

        self._fig.add_trace(
            go.Scatter(
                x=zigzag_df["time"],
                y=zigzag_df["pivot_value"],
                mode="lines+text",  # Enable text labels
                name=name,
                # The text to display (HH, HL, etc.)
                text=zigzag_df["structure"],
                textposition=text_positions,
                textfont=dict(size=12, color="rgba(255, 255, 255, 0.8)"),
                line=dict(color="rgba(255, 255, 255, 0.5)", width=2),
                hoverinfo="skip",
                hovertemplate=None,
            )
        )

    def add_msb(self, msb_df: DataFrame, zigzag_df: DataFrame):
        """
        Draws Market Structure Break (MSB) lines and labels.
        MSB lines are drawn at the price level of the broken pivot.
        """
        if msb_df.empty or zigzag_df.empty:
            return

        # Prepare zigzag data for lookup
        zz_temp = zigzag_df.copy().reset_index().rename(columns={"index": "zz_idx"})

        # Merge MSB results with Zigzag data to get coordinates
        # We need the price of the pivot that was BROKEN.
        # For a 3-pivot pattern (0, 1, 2), the 'broken' level is usually pivot 1.
        merged = msb_df.merge(
            zz_temp[["zz_idx", "pivot_value", "time"]],
            left_on="pivot_index",
            right_on="zz_idx",
        )

        for _, row in merged.iterrows():
            color = "#26a69a" if row["direction"] == "bullish" else "#ef5350"

            # 1. Add the MSB Label
            self._fig.add_trace(
                go.Scatter(
                    x=[row["time"]],
                    y=[row["pivot_value"]],
                    mode="markers+text",
                    name=f"MSB {row['direction']}",
                    text=["MSB"],
                    textposition="top center"
                    if row["direction"] == "bullish"
                    else "bottom center",
                    marker=dict(size=8, color=color, symbol="diamond-open"),
                    textfont=dict(color=color, size=11, family="Arial Black"),
                    showlegend=False,
                )
            )

            # 2. Add a horizontal line to show the break level
            # Draw from the MSB pivot to the pivot 2 positions after
            target_idx = row["zz_idx"] + 2
            if target_idx < len(zz_temp):
                end_time = zz_temp.iloc[target_idx]["time"]
            else:
                end_time = row["time"]  # Fallback if not enough pivots

            self._fig.add_shape(
                type="line",
                x0=row["time"],
                y0=row["pivot_value"],
                x1=end_time,
                y1=row["pivot_value"],
                name="MSB",
                xref="x",
                yref="y",
                line=dict(color=color, width=2),
            )

    def add_blocks(
        self,
        blocks_df: DataFrame,
        last_time: Any,
        draw_base_candle_extension: bool = False,
    ):
        """
        Draws boxes: Green for all Bullish, Red for all Bearish.

        Args:
            draw_base_candle_extension: If True, a hollow box will be drawn to show where the base candle of the block.
        """
        if blocks_df.empty:
            return

        for _, row in blocks_df.iterrows():
            # 1. Logic: Green for Bullish, Red for Bearish
            if row["direction"] == "bullish":
                base_color = "38, 166, 154"  # Emerald Green
            else:
                base_color = "239, 83, 80"  # Soft Red

            fill_color = f"rgba({base_color}, {0.15})"
            line_color = f"rgba({base_color}, 0.8)"

            # 2. Determine horizontal extent (handle None)
            end_x = row["end_time"] if row["end_time"] is not NaT else last_time

            # 3. Draw the Box
            self._fig.add_shape(
                type="rect",
                x0=row["start_time"],
                y0=row["low"],
                x1=end_x,
                y1=row["high"],
                fillcolor=fill_color,
                line=dict(color=line_color, width=1),
                layer="below",
                xref="x",
                yref="y",
            )

            # 4. If th argument is true, draw the Box showing the base candle
            if draw_base_candle_extension:
                self._fig.add_shape(
                    type="rect",
                    x0=row["base_candle_time"],
                    y0=row["low"],
                    x1=row["start_time"],
                    y1=row["high"],
                    line=dict(color=line_color, width=1),
                    layer="below",
                    xref="x",
                    yref="y",
                )

            # Label the specific type in the corner of the box
            self._fig.add_trace(
                go.Scatter(
                    x=[row["start_time"]],
                    y=[row["high"]],
                    mode="text",
                    text=[f"{row['type']}"],
                    textposition="top right",
                    textfont=dict(size=9, color=line_color),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

    def add_positions(self, positions_df):
        """
        Draws lines representing the entry, targets and stops of a dataframe of positions.
        """
        colors = [
            "cyan",
            "magenta",
            "yellow",
            "green",
            "blue",
            "orange",
            "purple",
            "red",
            "lime",
            "gold",
        ]
        for i, row in positions_df.iterrows():
            if row["entry_time"] is not NaT:
                # Marker for entry
                self._fig.add_trace(
                    go.Scatter(
                        x=[row["entry_time"]],
                        y=[row["entry"]],
                        mode="markers",
                        marker=dict(
                            size=10,
                            color=colors[i % len(colors)],
                            symbol="circle",
                            line=dict(width=2, color="LightBlue"),
                        ),
                    )
                )

                if row["target_times"] is not None and len(row["target_times"]) > 0:
                    prev_time = row["entry_time"]
                    prev_price = row["entry"]
                    for t_time, t_price in zip(row["target_times"], row["targets"]):
                        # Line from previous (entry or previous target) to current target
                        self._fig.add_trace(
                            go.Scatter(
                                x=[prev_time, t_time],
                                y=[prev_price, t_price],
                                mode="lines+markers",
                                line=dict(color=colors[i % len(colors)], width=2),
                                marker=dict(size=6, color=colors[i % len(colors)]),
                                name=f"Target {i + 1}",
                            )
                        )
                        prev_time, prev_price = (
                            t_time,
                            t_price,
                        )  # Update for next segment

                if row["stop_time"] is not NaT:
                    # If the position has hit ANY targets, draw a line connecting the last target hit
                    # to the stoploss.
                    if row["status"] != "STOPLOSS":
                        highest_target = int(row["status"].split("_")[-1])
                        last_time = row["target_times"][-1]
                        last_price = row["targets"][highest_target - 1]
                    # If no targets are registered, just connect the entry to the stoploss
                    else:
                        last_time = row["entry_time"]
                        last_price = row["entry"]

                    # Don't draw the line connecting the last target to the stoploss if the position has achieved all targets
                    if not row["full_target"]:
                        self._fig.add_trace(
                            go.Scatter(
                                x=[last_time, row["stop_time"]],
                                y=[last_price, row["stoploss"]],
                                mode="lines",
                                line=dict(
                                    color=colors[i % len(colors)], width=2, dash="dash"
                                ),
                                name=f"Stop {i + 1}",
                            )
                        )

                        self._fig.add_trace(
                            go.Scatter(
                                x=[row["stop_time"]],
                                y=[row["stoploss"]],
                                mode="markers",
                                marker=dict(
                                    size=10,
                                    color=colors[i % len(colors)],
                                    symbol="circle",
                                    line=dict(width=2, color="DarkRed"),
                                ),
                            )
                        )

    def _apply_zoom(self):
        """Applies the zoom to the chart."""
        if hasattr(self, "_should_zoom") and self._should_zoom:
            self._fig.update_xaxes(range=[self._zoom_start, self._zoom_end])

    def show(self):
        self._apply_zoom()
        # The scrollZoom config enables the 'zoom-where-hovered' behavior
        self._fig.show(
            config={
                "scrollZoom": True,
                "displayModeBar": True,
                "modeBarButtonsToRemove": ["select2d", "lasso2d"],
            }
        )

    def save(self, auto_open=False):
        self._apply_zoom()
        # When saving to HTML, you can include the config here
        self._fig.write_html(
            self.output_file, auto_open=auto_open, config={"scrollZoom": True}
        )

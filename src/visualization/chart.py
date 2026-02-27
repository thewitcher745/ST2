import plotly.graph_objects as go
from pandas import DataFrame


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
        """Initializes the dark theme and layout settings."""
        self._fig.update_layout(
            template="plotly_dark",
            hovermode="x unified",
            dragmode="pan",
            xaxis_rangeslider_visible=False,
            title=self.title,
            autosize=True,
            width=1800,
            height=900,
            margin=dict(l=20, r=20, t=40, b=20),
        )

    def add_candlesticks(self, df: DataFrame, name: str = "Price"):
        """Adds candlestick traces to the figure with index in tooltip."""
        
        # Ensure we have the integer index available as an array
        # We use reset_index if 'klines_df_index' isn't a column, or just df.index
        df_indices = df.index
        print(df_indices)
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
                    "<b>Index (i): %{customdata}</b><br>" +
                    "O: %{open}<br>" +
                    "H: %{high}<br>" +
                    "L: %{low}<br>" +
                    "C: %{close}<extra></extra>"
                )
            )
        )

        if len(df) > self.max_n_candles_visible:
            self._zoom_start = df["time"].iloc[-self.max_n_candles_visible]
            self._zoom_end = df["time"].iloc[-1]
            self._should_zoom = True
        else:
            self._should_zoom = False
    def _apply_zoom(self):
        """Applies the zoom to the chart."""
        if hasattr(self, "_should_zoom") and self._should_zoom:
            self._fig.update_xaxes(range=[self._zoom_start, self._zoom_end])

    def save(self, auto_open=False):
        """
        Saves the chart to an HTML file.
        """
        self._apply_zoom()
        # Save the basic Plotly HTML
        self._fig.write_html(self.output_file, auto_open=auto_open)

        print(f"--- Chart updated at {self.output_file} ---")

    def show(self):
        self._apply_zoom()
        self._fig.show()

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
from pandas import DataFrame
import logging

logging.getLogger("matplotlib").setLevel(logging.WARNING)

# ============================================================================
# Data Models
# ============================================================================


@dataclass
class VisualizationConfig:
    """Configuration for visualization output."""

    output_dir: Path
    output_format: str = "pdf"  # "pdf" or "png"
    dpi: int = 300
    figsize_heatmap: tuple[int, int] = (12, 10)
    figsize_bar: tuple[int, int] = (14, 8)
    figsize_3d: tuple[int, int] = (12, 10)
    figsize_box: tuple[int, int] = (16, 10)
    color_palette: str = "coolwarm"

    def __post_init__(self):
        """Ensure output directory exists."""
        self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class AnalysisData:
    """Container for processed backtest data."""

    df: DataFrame
    parameter_names: list[str]
    fitness_functions: list[str]
    params_range_dict: dict[str, Any]


# ============================================================================
# Data Provider
# ============================================================================


class DataProvider:
    """
    Extracts and prepares data from ResultsAggregator.

    Responsibilities:
        - Read data from aggregator's in-memory structures
        - Identify parameter columns vs metric columns
        - Prepare DataFrame for analysis
    """

    DEFAULT_FITNESS_FUNCTIONS = [
        "score",
        "total_net_profit",
        "total_winrate",
        "total_performance",
        "average_target_hit",
    ]

    def __init__(self, aggregator: Any):
        """
        Initialize data provider.

        Args:
            aggregator: ResultsAggregator instance with completed backtest results
        """
        self.aggregator = aggregator

    def get_analysis_data(self) -> AnalysisData:
        """
        Extract and prepare all data needed for visualization.

        Returns:
            AnalysisData containing DataFrame, parameter names, and fitness functions
        """
        # Convert aggregator's rows to DataFrame
        df = DataFrame(self.aggregator.rows)

        # Extract parameter names from params_range_dict
        parameter_names = list(self.aggregator.params_range_dict.keys())

        # Validate fitness functions exist in data
        fitness_functions = [
            ff for ff in self.DEFAULT_FITNESS_FUNCTIONS if ff in df.columns
        ]

        if not fitness_functions:
            raise ValueError(
                f"None of the expected fitness functions {self.DEFAULT_FITNESS_FUNCTIONS} "
                f"found in data columns: {df.columns.tolist()}"
            )

        return AnalysisData(
            df=df,
            parameter_names=parameter_names,
            fitness_functions=fitness_functions,
            params_range_dict=self.aggregator.params_range_dict,
        )


# ============================================================================
# Correlation Analyzer
# ============================================================================


class CorrelationAnalyzer:
    """
    Computes correlation metrics between parameters and fitness functions.

    Handles both numerical and categorical parameters by encoding categoricals
    as integers for correlation computation.
    """

    def __init__(self, data: AnalysisData):
        """
        Initialize analyzer with prepared data.

        Args:
            data: AnalysisData containing DataFrame and metadata
        """
        self.data = data
        self._encoded_df: DataFrame | None = None

    def compute_correlations(self) -> dict[str, pd.Series]:
        """
        Compute correlations between all parameters and each fitness function.

        Returns:
            Dictionary mapping fitness_function_name -> Series of correlations
            with parameter names as index
        """
        encoded_df = self._get_encoded_dataframe()

        correlations = {}
        for fitness_func in self.data.fitness_functions:
            corr_series = pd.Series(
                {
                    param: encoded_df[param].corr(encoded_df[fitness_func])
                    for param in self.data.parameter_names
                },
                name=fitness_func,
            )
            correlations[fitness_func] = corr_series

        return correlations

    def _get_encoded_dataframe(self) -> DataFrame:
        """
        Create a copy of DataFrame with categorical parameters encoded as integers.

        Returns:
            DataFrame with all parameters as numeric types
        """
        if self._encoded_df is not None:
            return self._encoded_df

        df = self.data.df.copy()

        # Encode categorical parameters
        for param in self.data.parameter_names:
            # Check if parameter is non-numeric (handles StringDtype and object types)
            if pd.api.types.is_string_dtype(df[param]) or pd.api.types.is_object_dtype(
                df[param]
            ):
                # Create categorical codes
                df[param] = pd.Categorical(df[param]).codes
            elif not pd.api.types.is_numeric_dtype(df[param]):
                # Fallback for any other non-numeric types
                df[param] = pd.Categorical(df[param]).codes

        self._encoded_df = df
        return self._encoded_df


# ============================================================================
# Base Visualizer Interface
# ============================================================================


class BaseVisualizer(ABC):
    """
    Abstract base class for all visualizers.

    Enforces Single Responsibility and Open/Closed principles.
    Each concrete visualizer handles one specific chart type.
    """

    def __init__(self, data: AnalysisData, config: VisualizationConfig):
        """
        Initialize visualizer.

        Args:
            data: Prepared analysis data
            config: Visualization configuration
        """
        self.data = data
        self.config = config

    @abstractmethod
    def generate(self) -> Figure:
        """
        Generate the visualization.

        Returns:
            Matplotlib Figure object
        """
        pass

    @abstractmethod
    def get_filename(self) -> str:
        """
        Get the output filename for this visualization.

        Returns:
            Filename string (without extension)
        """
        pass


# ============================================================================
# Concrete Visualizers
# ============================================================================


class MultiObjectiveCorrelationVisualizer(BaseVisualizer):
    """
    Generates correlation heatmaps for each fitness function.

    Creates a grid of heatmaps showing parameter correlations with each
    fitness objective.
    """

    def __init__(
        self,
        data: AnalysisData,
        config: VisualizationConfig,
        correlations: dict[str, pd.Series],
    ):
        """
        Initialize with pre-computed correlations.

        Args:
            data: Analysis data
            config: Visualization config
            correlations: Pre-computed correlation dictionary
        """
        super().__init__(data, config)
        self.correlations = correlations

    def generate(self) -> Figure:
        """Generate multi-objective correlation heatmaps."""
        n_fitness = len(self.data.fitness_functions)
        n_cols = 2
        n_rows = (n_fitness + 1) // 2

        fig, axes = plt.subplots(
            n_rows,
            n_cols,
            figsize=(
                self.config.figsize_heatmap[0],
                self.config.figsize_heatmap[1] * n_rows / 2,
            ),
        )

        if n_fitness == 1:
            axes = np.array([axes])
        axes = axes.flatten()

        for idx, fitness_func in enumerate(self.data.fitness_functions):
            ax = axes[idx]
            corr_matrix = self.correlations[fitness_func].to_frame()

            sns.heatmap(
                corr_matrix,
                annot=True,
                fmt=".3f",
                cmap=self.config.color_palette,
                center=0,
                vmin=-1,
                vmax=1,
                cbar_kws={"label": "Correlation"},
                ax=ax,
                linewidths=0.5,
            )

            ax.set_title(
                f"Parameter Correlation with {fitness_func}",
                fontsize=12,
                fontweight="bold",
            )
            ax.set_xlabel("")
            ax.set_ylabel("Parameters", fontsize=10)

        # Hide unused subplots
        for idx in range(n_fitness, len(axes)):
            axes[idx].axis("off")

        fig.suptitle(
            "Multi-Objective Parameter Correlation Analysis",
            fontsize=16,
            fontweight="bold",
            y=0.995,
        )
        fig.tight_layout()

        return fig

    def get_filename(self) -> str:
        return "01_multi_objective_correlations"


class ParameterImpactVisualizer(BaseVisualizer):
    """
    Generates bar charts comparing parameter impact across fitness functions.

    Shows which parameters have the strongest correlation with each objective.
    """

    def __init__(
        self,
        data: AnalysisData,
        config: VisualizationConfig,
        correlations: dict[str, pd.Series],
    ):
        super().__init__(data, config)
        self.correlations = correlations

    def generate(self) -> Figure:
        """Generate parameter impact comparison bar charts."""
        # Prepare data for grouped bar chart
        corr_df = pd.DataFrame(self.correlations).abs()  # Use absolute correlation

        fig, ax = plt.subplots(figsize=self.config.figsize_bar)

        x = np.arange(len(self.data.parameter_names))
        width = 0.8 / len(self.data.fitness_functions)

        for idx, fitness_func in enumerate(self.data.fitness_functions):
            offset = (idx - len(self.data.fitness_functions) / 2) * width + width / 2
            ax.bar(
                x + offset, corr_df[fitness_func], width, label=fitness_func, alpha=0.8
            )

        ax.set_xlabel("Parameters", fontsize=12, fontweight="bold")
        ax.set_ylabel("Absolute Correlation", fontsize=12, fontweight="bold")
        ax.set_title(
            "Parameter Impact Across Fitness Functions", fontsize=14, fontweight="bold"
        )
        ax.set_xticks(x)
        ax.set_xticklabels(self.data.parameter_names, rotation=45, ha="right")
        ax.legend(title="Fitness Function", loc="upper right")
        ax.grid(axis="y", alpha=0.3)
        ax.set_ylim(0, 1)

        fig.tight_layout()

        return fig

    def get_filename(self) -> str:
        return "02_parameter_impact_comparison"


class ParetoFrontVisualizer(BaseVisualizer):
    """
    Generates 3D scatter plot showing Pareto front of multi-objective optimization.

    Visualizes trade-offs between three primary fitness functions.
    """

    def generate(self) -> Figure:
        """Generate 3D Pareto front visualization."""
        # Use first three fitness functions for 3D plot
        if len(self.data.fitness_functions) < 3:
            # Fallback to 2D if less than 3 fitness functions
            return self._generate_2d_pareto()

        fig = Figure(figsize=self.config.figsize_3d)
        ax = fig.add_subplot(111, projection="3d")

        x_metric = self.data.fitness_functions[1]  # total_net_profit
        y_metric = self.data.fitness_functions[2]  # total_winrate
        z_metric = (
            self.data.fitness_functions[3]
            if len(self.data.fitness_functions) > 3
            else self.data.fitness_functions[0]
        )
        color_metric = self.data.fitness_functions[0]  # score

        scatter = ax.scatter(
            xs=self.data.df[x_metric],
            ys=self.data.df[y_metric],
            zs=self.data.df[z_metric],
            c=self.data.df[color_metric],
            cmap="viridis",
            alpha=0.6,
            s=20,
        )

        ax.set_xlabel(x_metric, fontsize=10, fontweight="bold")
        ax.set_ylabel(y_metric, fontsize=10, fontweight="bold")
        ax.set_zlabel(z_metric, fontsize=10, fontweight="bold")
        ax.set_title(
            "Pareto Front: Multi-Objective Trade-offs", fontsize=14, fontweight="bold"
        )

        cbar = fig.colorbar(scatter, ax=ax, pad=0.1, shrink=0.8)
        cbar.set_label(color_metric, fontsize=10, fontweight="bold")

        fig.tight_layout()

        return fig

    def _generate_2d_pareto(self) -> Figure:
        """Fallback 2D Pareto front if less than 3 fitness functions."""
        fig, ax = plt.subplots(figsize=self.config.figsize_3d)

        x_metric = self.data.fitness_functions[0]
        y_metric = (
            self.data.fitness_functions[1]
            if len(self.data.fitness_functions) > 1
            else self.data.fitness_functions[0]
        )

        ax.set_xlabel(x_metric, fontsize=12, fontweight="bold")
        ax.set_ylabel(y_metric, fontsize=12, fontweight="bold")
        ax.set_title("Pareto Front: 2D Trade-off", fontsize=14, fontweight="bold")
        ax.grid(alpha=0.3)

        fig.tight_layout()

        return fig

    def get_filename(self) -> str:
        return "03_pareto_front"


class ParameterSensitivityVisualizer(BaseVisualizer):
    """
    Generates box plots showing fitness distribution across parameter values.

    For each parameter, shows how different values affect each fitness function.
    """

    def generate(self) -> Figure:
        """Generate parameter sensitivity box plots."""
        n_params = len(self.data.parameter_names)
        n_fitness = len(self.data.fitness_functions)

        fig, axes = plt.subplots(
            n_params,
            n_fitness,
            figsize=(
                self.config.figsize_box[0],
                self.config.figsize_box[1] * n_params / 4,
            ),
        )

        if n_params == 1:
            axes = axes.reshape(1, -1)
        if n_fitness == 1:
            axes = axes.reshape(-1, 1)

        for param_idx, param in enumerate(self.data.parameter_names):
            for fit_idx, fitness_func in enumerate(self.data.fitness_functions):
                ax = axes[param_idx, fit_idx]

                # Prepare data for box plot
                param_values = sorted(self.data.df[param].unique())
                data_to_plot = [
                    self.data.df[self.data.df[param] == val][fitness_func].values
                    for val in param_values
                ]

                bp = ax.boxplot(
                    data_to_plot,
                    labels=[str(v) for v in param_values],
                    patch_artist=True,
                    showmeans=True,
                )

                # Color boxes
                for patch in bp["boxes"]:
                    patch.set_facecolor("lightblue")
                    patch.set_alpha(0.7)

                if param_idx == 0:
                    ax.set_title(fitness_func, fontsize=10, fontweight="bold")

                if fit_idx == 0:
                    ax.set_ylabel(param, fontsize=9, fontweight="bold")

                ax.tick_params(axis="x", rotation=45, labelsize=7)
                ax.grid(axis="y", alpha=0.3)

        fig.suptitle("Parameter Sensitivity Analysis", fontsize=16, fontweight="bold")
        fig.tight_layout()

        return fig

    def get_filename(self) -> str:
        return "04_parameter_sensitivity"


class TopConfigsVisualizer(BaseVisualizer):
    """
    Generates tables showing top-performing configurations for each fitness function.

    Highlights parameter patterns in winning configurations.
    """

    def __init__(
        self, data: AnalysisData, config: VisualizationConfig, top_n: int = 10
    ):
        super().__init__(data, config)
        self.top_n = top_n

    def generate(self) -> Figure:
        """Generate top configurations dashboard."""
        n_fitness = len(self.data.fitness_functions)

        fig, axes = plt.subplots(n_fitness, 1, figsize=(16, 4 * n_fitness))

        if n_fitness == 1:
            axes = [axes]

        for idx, fitness_func in enumerate(self.data.fitness_functions):
            ax = axes[idx]
            ax.axis("tight")
            ax.axis("off")

            # Get top N configurations
            top_configs = self.data.df.nlargest(self.top_n, fitness_func)

            # Select columns to display
            display_cols = ["run_id"] + self.data.parameter_names + [fitness_func]
            table_data = top_configs[display_cols].copy()

            # Round numeric columns
            for col in table_data.columns:
                if pd.api.types.is_numeric_dtype(table_data[col]):
                    table_data[col] = table_data[col].round(4)

            # Create table
            table = ax.table(
                cellText=table_data.values,
                colLabels=table_data.columns,
                cellLoc="center",
                loc="center",
                bbox=[0, 0, 1, 1],
            )

            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1, 1.5)

            # Style header
            for i in range(len(display_cols)):
                table[(0, i)].set_facecolor("#4CAF50")
                table[(0, i)].set_text_props(weight="bold", color="white")

            # Alternate row colors
            for i in range(1, len(table_data) + 1):
                for j in range(len(display_cols)):
                    if i % 2 == 0:
                        table[(i, j)].set_facecolor("#f0f0f0")

            ax.set_title(
                f"Top {self.top_n} Configurations by {fitness_func}",
                fontsize=12,
                fontweight="bold",
                pad=20,
            )

        fig.suptitle(
            "Top Performing Configurations Dashboard", fontsize=16, fontweight="bold"
        )
        fig.tight_layout()

        return fig

    def get_filename(self) -> str:
        return "05_top_configurations"


# ============================================================================
# Visualization Engine (Orchestrator)
# ============================================================================


class VisualizationEngine:
    """
    Main orchestrator for backtest visualization pipeline.

    Coordinates data extraction, analysis, and visualization generation.
    Follows Dependency Inversion principle by depending on abstractions.

    Usage:
        engine = VisualizationEngine(aggregator, output_dir="./results")
        engine.generate_all_visualizations()
    """

    def __init__(
        self,
        aggregator: Any,
        output_dir: Path | None = None,
        config: VisualizationConfig | None = None,
    ):
        """
        Initialize visualization engine.

        Args:
            aggregator: ResultsAggregator instance with completed results
            output_dir: Directory for output files (defaults to aggregator's output_dir)
            config: Optional custom visualization configuration
        """
        self.aggregator = aggregator

        # Use aggregator's output directory if not specified
        if output_dir is None:
            output_dir = Path(aggregator.output_dir)

        self.config = config or VisualizationConfig(output_dir=output_dir)
        self.data_provider = DataProvider(aggregator)
        self.data: AnalysisData | None = None
        self.analyzer: CorrelationAnalyzer | None = None
        self.correlations: dict[str, pd.Series] | None = None

    def generate_all_visualizations(
        self, save_pdf: bool = True, save_individual: bool = True
    ):
        """
        Generate all visualizations and save to files.

        Args:
            save_pdf: If True, save all charts in a single PDF
            save_individual: If True, save each chart as individual PNG
        """
        print("🎨 Starting visualization generation...")

        # Step 1: Extract and prepare data
        print("📊 Extracting data from aggregator...")
        self.data = self.data_provider.get_analysis_data()
        print(f"   ✓ Loaded {len(self.data.df)} configurations")
        print(f"   ✓ Parameters: {', '.join(self.data.parameter_names)}")
        print(f"   ✓ Fitness functions: {', '.join(self.data.fitness_functions)}")

        # Step 2: Compute correlations
        print("🔢 Computing correlations...")
        self.analyzer = CorrelationAnalyzer(self.data)
        self.correlations = self.analyzer.compute_correlations()
        print("   ✓ Correlations computed")

        # Step 3: Generate visualizations
        visualizers = self._create_visualizers()

        figures = []
        for visualizer in visualizers:
            print(f"📈 Generating {visualizer.get_filename()}...")
            fig = visualizer.generate()
            figures.append((visualizer.get_filename(), fig))

        # Step 4: Save outputs
        if save_pdf:
            self._save_pdf(figures)

        if save_individual:
            self._save_individual_figures(figures)

        # Clean up
        for _, fig in figures:
            plt.close(fig)

        print(f"✅ All visualizations saved to: {self.config.output_dir}")

    def _create_visualizers(self) -> list[BaseVisualizer]:
        """
        Create all visualizer instances.

        Returns:
            list of configured visualizers
        """
        visualizers: list[BaseVisualizer] = [
            MultiObjectiveCorrelationVisualizer(
                self.data, self.config, self.correlations
            ),
            ParameterImpactVisualizer(self.data, self.config, self.correlations),
            ParetoFrontVisualizer(self.data, self.config),
            ParameterSensitivityVisualizer(self.data, self.config),
            TopConfigsVisualizer(self.data, self.config, top_n=10),
        ]
        return visualizers

    def _save_pdf(self, figures: list[tuple[str, Figure]]):
        """Save all figures to a single PDF file."""
        pdf_path = self.config.output_dir / "backtest_analysis_report.pdf"
        print("💾 Saving PDF report...")

        with PdfPages(pdf_path) as pdf:
            for name, fig in figures:
                pdf.savefig(fig, dpi=self.config.dpi, bbox_inches="tight")

        print(f"   ✓ PDF report saved: {pdf_path}")

    def _save_individual_figures(self, figures: list[tuple[str, Figure]]):
        """Save each figure as an individual PNG file."""
        for name, fig in figures:
            path = self.config.output_dir / f"{name}.png"
            fig.savefig(path, dpi=self.config.dpi, bbox_inches="tight")
            print(f"   ✓ Saved {path}")

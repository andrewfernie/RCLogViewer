"""
Copyright Andrew Fernie, 2025

dataseries_plot_panel.py

Provides a QWidget-based panel for plotting data series using matplotlib, designed for
PySide6 compatibility.
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                              QGroupBox, QCheckBox, QComboBox, QLabel,
                              QSpinBox)
from PySide6.QtCore import Signal, QSettings
import numpy as np

# Matplotlib imports
import matplotlib
matplotlib.use('Qt5Agg')  # Use Qt backend
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

class DataSeriesPlotPanel(QWidget):
    """
    QWidget-based panel for plotting multiple data series using matplotlib.

    Features:
        - Supports plotting up to three data series with separate y-axes (auto-switches to single
         axis for 4+ channels).
        - Interactive controls for auto-range, grid, single axis mode, offset formatting, line
          width, and style.
        - Color-coded axes and legend for clarity.
        - Persistent color settings using QSettings.
        - Emits x_limits_changed signal when x-axis limits change.

    Args:
        title (str): Title for the plot panel.
        parent (QWidget, optional): Parent widget.
    """

    # Signal emitted when x-axis limits change (start_time, end_time)
    x_limits_changed = Signal(float, float)

    def __init__(self, title="Plot", parent=None):
        super().__init__(parent)
        self.title = title
        self.curves = {}
        self.total_curves = 0
        # Expanded color palette with distinct, easily distinguishable colors
        self.colors = [
            '#FF0000',  # Red
            '#0000FF',  # Blue
            '#008000',  # Green
            '#FF8C00',  # Dark Orange
            '#8A2BE2',  # Blue Violet
            '#A52A2A',  # Brown
            '#FF1493',  # Deep Pink
            '#2F4F4F',  # Dark Slate Gray
            '#FFD700',  # Gold
            '#00CED1',  # Dark Turquoise
            '#FF4500',  # Orange Red
            '#9932CC',  # Dark Orchid
            '#228B22',  # Forest Green
            '#DC143C',  # Crimson
            '#4169E1',  # Royal Blue
            '#32CD32',  # Lime Green
        ]
        self.color_index = 0
        self.axes = []  # List to store multiple axes
        self.current_axis_index = 0
        self.force_single_axis = False  # Flag to force single axis mode

        self._setup_ui()

    def _setup_ui(self):
        """Set up the plot widget UI."""
        layout = QVBoxLayout(self)

        # Create matplotlib figure and canvas
        # Reduced width from 12 to 10 to make plot narrower and leave more room for y-axes
        self.figure = Figure(figsize=(10, 8), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setParent(self)

        # Create subplot with adjusted margins to provide more space for multiple y-axes
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title(self.title)
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Value')

        # Adjust subplot margins to leave more room for multiple y-axes on the right
        self.figure.subplots_adjust(left=0.1, right=0.75)

        # Initialize with single axis
        self.axes = [self.ax]

        # Set minimum size to ensure visibility
        self.canvas.setMinimumSize(400, 300)

        layout.addWidget(self.canvas)

        # Add navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)

        # Connect to axis limit change events
        self.canvas.mpl_connect('button_release_event', self._on_button_release)

        # Control panel
        controls_group = QGroupBox("Plot Controls")
        controls_layout = QVBoxLayout(controls_group)

        # First row - Checkboxes only
        row1_layout = QHBoxLayout()

        # Auto-range checkbox
        self.auto_range_cb = QCheckBox("Auto Range")
        self.auto_range_cb.setChecked(True)
        self.auto_range_cb.toggled.connect(self._toggle_auto_range)
        row1_layout.addWidget(self.auto_range_cb)

        # Grid checkbox
        self.grid_cb = QCheckBox("Grid")
        self.grid_cb.setChecked(True)
        self.grid_cb.toggled.connect(self._set_grid_visibility)
        row1_layout.addWidget(self.grid_cb)
        self._set_grid_visibility()

        # Single axis checkbox
        self.single_axis_cb = QCheckBox("Single Y-Axis")
        self.single_axis_cb.setChecked(False)
        self.single_axis_cb.toggled.connect(self._toggle_single_axis)
        row1_layout.addWidget(self.single_axis_cb)

        # Use Offset Format checkbox
        self.use_offset_cb = QCheckBox("Use Offset Format")
        self.use_offset_cb.setChecked(False)
        self.use_offset_cb.toggled.connect(self._toggle_offset_format)
        row1_layout.addWidget(self.use_offset_cb)

        row1_layout.addStretch()
        controls_layout.addLayout(row1_layout)

        # Second row - Width and Style controls
        row2_layout = QHBoxLayout()

        # Line width (first, to the left)
        row2_layout.addWidget(QLabel("Line Width:"))
        self.line_width_spin = QSpinBox()
        self.line_width_spin.setRange(1, 5)
        self.line_width_spin.setValue(2)
        self.line_width_spin.valueChanged.connect(self._update_line_width)
        row2_layout.addWidget(self.line_width_spin)

        # Line style combo (second, to the right)
        row2_layout.addWidget(QLabel("Line Style:"))
        self.line_style_combo = QComboBox()
        self.line_style_combo.addItems(["Solid", "Dashed", "Dotted", "Points"])
        self.line_style_combo.currentTextChanged.connect(self._update_line_style)
        row2_layout.addWidget(self.line_style_combo)

        row2_layout.addStretch()
        controls_layout.addLayout(row2_layout)

        # Third row - Clear and Reset Zoom buttons
        row3_layout = QHBoxLayout()

        # Clear button
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear)
        row3_layout.addWidget(clear_button)

        # Reset Zoom button
        reset_zoom_button = QPushButton("Reset Zoom")
        reset_zoom_button.clicked.connect(self.reset_zoom)
        row3_layout.addWidget(reset_zoom_button)

        row3_layout.addStretch()
        controls_layout.addLayout(row3_layout)

        layout.addWidget(controls_group)

        # Initialize QSettings for persistence
        self.settings = QSettings('RCLogViewer', 'DataSeriesPlotPanel')
        self._load_color_settings()

    def _set_plot_title(self):
        """Set the plot title."""
        title = ""
        num_curves = len(self.curves)
        if num_curves == 0:
            title = self.title
        elif num_curves == 1:
            title = list(self.curves.keys())[0] + " vs. Elapsed Time (s)"
        elif num_curves == 2:
            title = list(self.curves.keys())[0] + " and " + list(self.curves.keys())[1] + \
                " vs. Elapsed Time (s)"
        elif num_curves == 3:
            title = list(self.curves.keys())[0] + ", " + list(self.curves.keys())[1] + \
                ", and " + list(self.curves.keys())[2] + " vs. Elapsed Time (s)"
        elif num_curves > 3:
            title = "Multiple Data Series vs. Elapsed Time (s)"

        self.ax.set_title(title)

        # Refresh the canvas
        self.canvas.draw()

    def _save_color_settings(self):
        """Save color selections to QSettings."""
        self.settings.setValue('colors', self.colors)
        self.settings.setValue('color_index', self.color_index)

    def _load_color_settings(self):
        """Load color selections from QSettings."""
        saved_colors = self.settings.value('colors')
        if saved_colors:
            self.colors = saved_colors

        saved_color_index = self.settings.value('color_index')
        if saved_color_index is not None:
            self.color_index = int(saved_color_index)


    def plot_data(self, x_data, y_data, name, color=None):
        """Plot data with given name and optional color."""
        # Ensure data is numpy arrays
        try:
            x_data = np.asarray(x_data, dtype=float)
            y_data = np.asarray(y_data, dtype=float)

        except Exception as e:
            print(f"Error converting data to numpy arrays: {e}")
            return

        # Check if we have valid data
        if len(x_data) == 0 or len(y_data) == 0:
            return

        # Assign unique color for each channel
        if color is None:
            # Use the current color index and increment it
            color = self.colors[self.color_index % len(self.colors)]
            self.color_index += 1
            self._save_color_settings()  # Save after incrementing color index

        # Get line style
        line_style = self._get_line_style()
        line_width = self.line_width_spin.value()

        # Determine which axis to use based on curve count
        curve_count = len(self.curves)
        axis_to_use = self._get_axis_for_curve(curve_count)

        # Plot the data on the appropriate axis
        line, = axis_to_use.plot(x_data, y_data,
                                color=color,
                                linewidth=line_width,
                                linestyle=line_style,
                                label=name)

        # Store curve info with axis reference
        self.curves[name] = {
            'line': line,
            'axis': axis_to_use,
            'color': color
        }

        # Set axis labels and colors
        self._setup_axis_styling(axis_to_use, curve_count, color, name)


        # Update legend to include all curves from all axes
        self._update_legend()

        # Auto-range if enabled
        if self.auto_range_cb.isChecked():
            axis_to_use.relim()
            axis_to_use.autoscale()

        # Refresh the canvas
        self.canvas.draw()

    def _get_axis_for_curve(self, curve_index):
        """Get the appropriate axis for the given curve index."""
        # If single axis mode is forced, always use primary axis
        if self.force_single_axis:
            return self.ax

        # Auto-switch to single axis for 4+ channels to avoid clutter
        if self.total_curves >= 4:
            return self.ax

        # For 1-3 channels, use multi-axis approach
        if curve_index == 0:
            # First curve always uses primary axis
            return self.ax
        elif curve_index == 1:
            # Second curve uses secondary y-axis (right)
            if len(self.axes) < 2:
                ax2 = self.ax.twinx()
                self.axes.append(ax2)
            return self.axes[1]
        elif curve_index == 2:
            # Third curve uses tertiary y-axis (far right)
            if len(self.axes) < 3:
                ax3 = self.ax.twinx()
                # Reduced offset from 80 to 60 pixels since we have more space allocated
                ax3.spines['right'].set_position(('outward', 70))
                self.axes.append(ax3)
            return self.axes[2]
        else:
            # This shouldn't happen with our logic, but fallback to primary axis
            return self.ax

    def _setup_axis_styling(self, axis, curve_index, color, name):
        """Setup styling for the given axis."""
        if self.force_single_axis or self.total_curves >= 4:
            # In single axis mode (forced or auto for 4+ channels), use generic label
            # and black ticks
            if curve_index == 0:  # First curve sets the label
                axis.set_ylabel('Value', color='black')
                axis.tick_params(axis='y', labelcolor='black')
        else:
            # Multi-axis mode - color code each axis
            if curve_index == 0:
                # Primary axis (left)
                axis.set_ylabel(name, color=color)
                axis.tick_params(axis='y', labelcolor=color)
            elif curve_index == 1:
                # Secondary axis (right)
                axis.set_ylabel(name, color=color)
                axis.tick_params(axis='y', labelcolor=color)
            elif curve_index == 2:
                # Tertiary axis (far right)
                axis.set_ylabel(name, color=color)
                axis.tick_params(axis='y', labelcolor=color)
                axis.yaxis.label.set_color(color)

        # Use the checkbox to determine offset format
        use_offset = self.use_offset_cb.isChecked()
        axis.ticklabel_format(useOffset=use_offset)

    def _update_legend(self):
        """Update legend to include all curves from all axes."""
        if not self.curves:
            # No curves, clear legend
            self.ax.legend().set_visible(False) if self.ax.get_legend() else None
            return

        # Collect all lines and labels from all curves
        lines = []
        labels = []

        for curve_name, curve_info in self.curves.items():
            lines.append(curve_info['line'])
            labels.append(curve_name)

        # Create legend on primary axis with all lines
        legend = self.ax.legend(lines, labels, loc='upper left', fontsize=9)
        legend.set_frame_on(True)
        legend.get_frame().set_facecolor('white')
        legend.get_frame().set_alpha(0.9)
        legend.get_frame().set_edgecolor('gray')


    def _get_line_style(self):
        """Get current line style setting."""
        style_map = {
            "Solid": "-",
            "Dashed": "--",
            "Dotted": ":",
            "Points": "o-"
        }
        return style_map.get(self.line_style_combo.currentText(), "-")

    def clear(self):
        """Clear all plots."""

        # Clear all axes
        for axis in self.axes:
            axis.clear()

        # Remove extra axes (keep only primary)
        for i in range(len(self.axes) - 1, 0, -1):
            self.axes[i].remove()

        # Reset to single axis
        self.axes = [self.ax]

        # Reset primary axis
        self.ax.set_title(self.title)
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Value')
        self._set_grid_visibility()

        # Reapply subplot margins for multiple y-axes
        self.figure.subplots_adjust(left=0.1, right=0.75)

        # Clear tracking variables
        self.curves.clear()
        self.color_index = 0
        self._save_color_settings()  # Save after resetting color index

        # Clear legend
        if self.ax.get_legend():
            self.ax.get_legend().set_visible(False)

        self.canvas.draw()

    def _toggle_auto_range(self, enabled):
        """Toggle auto-range mode."""
        if enabled:
            for axis in self.axes:
                axis.relim()
                axis.autoscale()
            self.canvas.draw()

    def _set_grid_visibility(self):
        """Toggle grid visibility."""
        enabled = self.grid_cb.isChecked()
        if enabled:
            self.ax.grid(enabled, alpha=0.3)
        else:
            self.ax.grid(False)

        self.canvas.draw()

    def _toggle_offset_format(self, enabled):
        """Toggle offset format for tick labels."""
        # Update all existing axes with the new offset format
        for axis in self.axes:
            axis.ticklabel_format(useOffset=enabled)
        self.canvas.draw()

    def _update_line_width(self, width):
        """Update line width for all existing curves."""
        # Update the line width for all existing curves
        for curve_name, curve_info in self.curves.items():
            line = curve_info['line']
            line.set_linewidth(width)
        self.canvas.draw()

    def _update_line_style(self, style_text):
        """Update line style for all existing curves."""
        # Get the matplotlib linestyle from the text
        style_map = {
            "Solid": "-",
            "Dashed": "--",
            "Dotted": ":",
            "Points": "-"  # For points, keep solid line but add markers
        }
        line_style = style_map.get(style_text, "-")

        # Update the line style and markers for all existing curves
        for curve_name, curve_info in self.curves.items():
            line = curve_info['line']
            line.set_linestyle(line_style)

            # Set markers for Points style
            if style_text == "Points":
                line.set_marker('o')
                line.set_markersize(4)

        self.canvas.draw()

    def _toggle_single_axis(self, enabled):
        """Toggle single axis mode - forces all channels to use one y-axis."""
        self.force_single_axis = enabled

        # If we have existing curves, replot them with new axis mode
        if self.curves:
            # Store current channel data
            current_channels = {}
            for name, curve_info in self.curves.items():
                line = curve_info['line']
                x_data, y_data = line.get_data()
                current_channels[name] = (x_data, y_data)

            # Clear and replot with new mode
            self.clear()
            self.total_curves = len(current_channels)
            for name, (x_data, y_data) in current_channels.items():
                self.plot_data(x_data, y_data, name)

        self._set_plot_title()


    def reset_zoom(self):
        """Reset zoom to show all data."""
        for axis in self.axes:
            axis.relim()
            axis.autoscale()

        x_min, x_max = self.axes[0].get_xlim()
        self.x_limits_changed.emit(float(x_min), float(x_max))

        self.canvas.draw()

    def clear_plots(self):
        """Clear all plots - alias for clear method."""
        self.clear()

    def plot_dataseries(self, time_data, channel_data):
        """Plot data series vs. time."""
        self.clear()

        self.total_curves = len(channel_data)
        for channel_name, data in channel_data.items():
            self.plot_data(time_data, data, channel_name)

        self._set_plot_title()

    def _on_button_release(self, event):
        """Callback when a button release event occurs.
            We are really after an event when the mouse button is released after
            changing the zoom, but can't find one of those, so we trigger on any
            button release and put up with the extra redraws.
        """
        # TODO: have this method called only on a button release after zooming
        x_min, x_max = self.axes[0].get_xlim()
        self.x_limits_changed.emit(float(x_min), float(x_max))

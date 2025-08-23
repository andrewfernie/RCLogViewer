"""
Copyright Andrew Fernie, 2025

gps_3d_plot_panel.py

Provides a QWidget-based panel for displaying GPS trajectory data in 3D using matplotlib.
Features include interactive controls, color selection, ground projection, and view presets.
"""

import numpy as np
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QCheckBox, QSpinBox, QComboBox,
                              QGroupBox)
from PySide6.QtCore import QSettings
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure


class GPSXYZ3DPlotPanel(QWidget):
    """
    QWidget-based panel for displaying GPS XYZ trajectory data in 3D. The data plotted is in
    X/Y/Z coordinates that have been generated from GPS latitude, longitude, and altitude.

    Features:
        - Interactive controls for trajectory, markers, ground projection, line width, and colors.
        - View angle can be modified by dragging the plot with the mouse.
        - View presets (top, side, front, isometric).
        - Persistent color settings using QSettings.
        - If the user has used the zoom feature in the dataseries plot panel to examine a subset
          of the data, the 3D plot will show the subset in one color and the full dataset in
          another color. Colors are configurable via the control panel.

    Args:
        parent (QWidget, optional): Parent widget.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.figure = None
        self.canvas = None
        self.ax = None
        self.trajectory_line = None
        self.start_marker = None
        self.end_marker = None
        self.ground_projection = None

        self.gps_x_data = None
        self.gps_y_data = None
        self.gps_z_data = None
        self.gps_time_data = None
        self.time_mask = None

        self._setup_ui()

    def _setup_ui(self):
        """
        Set up the user interface, including plot canvas, controls, and color selectors.
        """
        layout = QVBoxLayout(self)

        # Create matplotlib figure and canvas with 3D projection
        self.figure = Figure(figsize=(12, 10), dpi=100, facecolor='white')
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111, projection='3d')

        # Set up the 3D plot
        self.ax.set_xlabel('GPS X (m)')
        self.ax.set_ylabel('GPS Y (m)')
        self.ax.set_zlabel('GPS Altitude (m)')
        self.ax.set_title('GPS 3D Trajectory')

        layout.addWidget(self.canvas)

        # Add navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)

        # Control panel
        controls_group = QGroupBox("GPS 3D Plot Controls")
        controls_layout = QVBoxLayout(controls_group)

        # First row of controls
        row1_layout = QHBoxLayout()

        # Show trajectory checkbox
        self.show_trajectory_cb = QCheckBox("Show Trajectory")
        self.show_trajectory_cb.setChecked(True)
        self.show_trajectory_cb.stateChanged.connect(self._update_display)
        row1_layout.addWidget(self.show_trajectory_cb)

        # Show start/end markers checkbox
        self.show_markers_cb = QCheckBox("Show Start/End Markers")
        self.show_markers_cb.setChecked(True)
        self.show_markers_cb.stateChanged.connect(self._update_display)
        row1_layout.addWidget(self.show_markers_cb)

        # Show altitude projection checkbox
        self.show_projection_cb = QCheckBox("Show Ground Projection")
        self.show_projection_cb.setChecked(True)
        self.show_projection_cb.stateChanged.connect(self._update_display)
        row1_layout.addWidget(self.show_projection_cb)

        row1_layout.addStretch()
        controls_layout.addLayout(row1_layout)

        # Second row of controls
        row2_layout = QHBoxLayout()

        # Line width control
        line_width_label = QLabel("Line Width:")
        row2_layout.addWidget(line_width_label)

        self.line_width_spin = QSpinBox()
        self.line_width_spin.setMinimum(1)
        self.line_width_spin.setMaximum(10)
        self.line_width_spin.setValue(2)
        self.line_width_spin.valueChanged.connect(self._update_display)
        row2_layout.addWidget(self.line_width_spin)

        # Color control
        color_label = QLabel("Trajectory Color:")
        row2_layout.addWidget(color_label)

        self.color_combo = QComboBox()
        self.color_combo.addItems([
            "Blue", "Red", "Green", "Orange", "Purple", "Brown", "Pink", "Gray"
        ])
        self.color_combo.currentTextChanged.connect(self._on_color_changed)
        row2_layout.addWidget(self.color_combo)

        # Ground projection color control
        ground_color_label = QLabel("Ground Projection Color:")
        row2_layout.addWidget(ground_color_label)

        self.ground_color_combo = QComboBox()
        self.ground_color_combo.addItems([
            "Light Gray", "Gray", "Black", "Light Blue", "Light Green", "Light Red",
            "Yellow", "Cyan"])

        self.ground_color_combo.currentTextChanged.connect(self._on_color_changed)
        row2_layout.addWidget(self.ground_color_combo)

        # Filtered trajectory color control
        filtered_trajectory_color_label = QLabel("Filtered Trajectory Color:")
        row2_layout.addWidget(filtered_trajectory_color_label)

        self.filtered_trajectory_color_combo = QComboBox()
        self.filtered_trajectory_color_combo.addItems([
            "Orange", "Red", "Green", "Blue", "Purple", "Brown", "Pink", "Gray"
        ])
        self.filtered_trajectory_color_combo.currentTextChanged.connect(self._on_color_changed)
        row2_layout.addWidget(self.filtered_trajectory_color_combo)

        row2_layout.addStretch()
        controls_layout.addLayout(row2_layout)

        # Third row - buttons
        row3_layout = QHBoxLayout()

        # Reset view button
        reset_view_btn = QPushButton("Reset View")
        reset_view_btn.clicked.connect(self.reset_view)
        row3_layout.addWidget(reset_view_btn)

        # View presets
        view_label = QLabel("View:")
        row3_layout.addWidget(view_label)

        top_view_btn = QPushButton("Top")
        top_view_btn.clicked.connect(lambda: self.set_view(90, -90))
        row3_layout.addWidget(top_view_btn)

        side_view_btn = QPushButton("Side")
        side_view_btn.clicked.connect(lambda: self.set_view(0, -90))
        row3_layout.addWidget(side_view_btn)

        front_view_btn = QPushButton("Front")
        front_view_btn.clicked.connect(lambda: self.set_view(0, 0))
        row3_layout.addWidget(front_view_btn)

        iso_view_btn = QPushButton("Isometric")
        iso_view_btn.clicked.connect(lambda: self.set_view(30, -45))
        row3_layout.addWidget(iso_view_btn)

        row3_layout.addStretch()
        controls_layout.addLayout(row3_layout)

        layout.addWidget(controls_group)

        # Store GPS data
        self.gps_x_data = None
        self.gps_y_data = None
        self.gps_z_data = None
        self.ground_projection = None

        # Initialize QSettings for persistence
        self.settings = QSettings('RCLogViewer', 'GPS3DPlotPanel')
        self._load_color_settings()

    def _get_color(self, color_name):
        """
        Convert color name to matplotlib color string.
        """
        color_map = {
            "Blue": "blue",
            "Red": "red",
            "Green": "green",
            "Orange": "orange",
            "Purple": "purple",
            "Brown": "brown",
            "Pink": "pink",
            "Gray": "gray"
        }
        return color_map.get(color_name, "blue")

    def _get_ground_color(self, color_name):
        """
        Convert ground projection color name to matplotlib color string.
        """
        color_map = {
            "Light Gray": "lightgray",
            "Gray": "gray",
            "Black": "black",
            "Light Blue": "lightblue",
            "Light Green": "lightgreen",
            "Light Red": "lightcoral",
            "Yellow": "yellow",
            "Cyan": "cyan"
        }
        return color_map.get(color_name, "lightgray")

    def _get_filtered_trajectory_color(self, color_name):
        """
        Convert filtered trajectory color name to matplotlib color string.
        """
        color_map = {
            "Blue": "blue",
            "Red": "red",
            "Green": "green",
            "Orange": "orange",
            "Purple": "purple",
            "Brown": "brown",
            "Pink": "pink",
            "Gray": "gray"
        }
        return color_map.get(color_name, "orange")

    def _save_color_settings(self):
        """
        Save color selections to QSettings for persistence.
        """
        self.settings.setValue('trajectory_color', self.color_combo.currentText())
        self.settings.setValue('ground_color', self.ground_color_combo.currentText())
        self.settings.setValue('filtered_trajectory_color',
                               self.filtered_trajectory_color_combo.currentText())

    def _load_color_settings(self):
        """
        Load color selections from QSettings for persistence.
        """
        saved_trajectory_color = self.settings.value('trajectory_color')
        if saved_trajectory_color:
            index = self.color_combo.findText(saved_trajectory_color)
            if index >= 0:
                self.color_combo.setCurrentIndex(index)

        saved_ground_color = self.settings.value('ground_color')
        if saved_ground_color:
            index = self.ground_color_combo.findText(saved_ground_color)
            if index >= 0:
                self.ground_color_combo.setCurrentIndex(index)

        saved_filtered_color = self.settings.value('filtered_trajectory_color')
        if saved_filtered_color:
            index = self.filtered_trajectory_color_combo.findText(saved_filtered_color)
            if index >= 0:
                self.filtered_trajectory_color_combo.setCurrentIndex(index)

    def _on_color_changed(self):
        """
        Handle color combo box changes and update display.
        """
        self._save_color_settings()
        self._update_display()

    def plot_gps_trajectory_3d(self, x_data, y_data, z_data, time_data):
        """
        Plot GPS trajectory from X, Y, and Z coordinate data.

        Args:
            x_data (array-like): GPS X coordinates
            y_data (array-like): GPS Y coordinates
            z_data (array-like): GPS Z coordinates (altitude)
            time_data (array-like): Time data for synchronization with main plot
        """
        # Store the data
        self.gps_x_data = np.asarray(x_data, dtype=float)
        self.gps_y_data = np.asarray(y_data, dtype=float)
        self.gps_z_data = np.asarray(z_data, dtype=float)
        self.gps_time_data = np.asarray(time_data, dtype=float)


        # Remove any NaN values
        valid_mask = ~(np.isnan(self.gps_x_data) | np.isnan(self.gps_y_data) |
                       np.isnan(self.gps_z_data))
        self.gps_x_data = self.gps_x_data[valid_mask]
        self.gps_y_data = self.gps_y_data[valid_mask]
        self.gps_z_data = self.gps_z_data[valid_mask]
        self.gps_time_data = self.gps_time_data[valid_mask]

        # Create a time mask for filtering. Initially, it has all values set to True
        self.time_mask = np.ones_like(self.gps_time_data, dtype=bool)

        if len(self.gps_x_data) == 0 or len(self.gps_y_data) == 0 or len(self.gps_z_data) == 0:
            return

        # Clear previous plot
        self.clear_plot()

        # Plot the trajectory
        self._update_display()

        # Auto-scale to show all data
        self.reset_view()

    def _update_display(self):
        """
        Update the display based on current settings and filters.
        """
        if (self.gps_x_data is None or self.gps_y_data is None or
            self.gps_z_data is None or len(self.gps_x_data) == 0):
            return

        # Clear the entire axes and redraw (safer for 3D plots)
        self.ax.clear()

        # Initialize axis settings and title
        self.ax.set_xlabel('GPS X (m)')
        self.ax.set_ylabel('GPS Y (m)')
        self.ax.set_zlabel('GPS Altitude (m)')
        self.ax.set_title('GPS 3D Trajectory')
        self.ax.grid(True, alpha=0.3)
        self.ax.set_aspect('equal', adjustable='box')

        # Reset line references
        self.trajectory_line = None
        self.start_marker = None
        self.end_marker = None
        self.ground_projection = None

        # Get current settings
        color = self._get_color(self.color_combo.currentText())

        filtered_trajectory_color = self._get_filtered_trajectory_color(
            self.filtered_trajectory_color_combo.currentText())

        ground_color = self._get_ground_color(self.ground_color_combo.currentText())

        line_width = self.line_width_spin.value()

        # Determine if there are any false values in self.time_mask, indicating that a
        # filter is applied
        is_filtered = not np.all(self.time_mask)

        if not is_filtered:
            # Plot the full trajectory
            if self.show_trajectory_cb.isChecked():
                self.ax.plot(self.gps_x_data, self.gps_y_data, self.gps_z_data,
                             color=color, linewidth=line_width,
                             label='GPS Trajectory')

            # Add start/end markers for full trajectory if enabled
            if self.show_markers_cb.isChecked():
                if len(self.gps_x_data) > 0:
                    self.ax.plot(self.gps_x_data[0], self.gps_y_data[0], self.gps_z_data[0],
                                 'go', markersize=8, label='Full Trajectory Start')
                if len(self.gps_x_data) > 1:
                    self.ax.plot(self.gps_x_data[-1], self.gps_y_data[-1], self.gps_z_data[-1],
                                 'rs', markersize=8, label='Full Trajectory End')

            # Plot ground projection if enabled
            if self.show_projection_cb.isChecked():
                min_z = self.gps_z_data.min()
                self.ground_projection = self.ax.plot(
                    self.gps_x_data, self.gps_y_data, min_z,
                    color=ground_color,
                    linewidth=1,
                    alpha=0.5,
                    label='Ground Projection'
                )

        else:
            if len(self.gps_x_data) > 0:
                self.ax.plot(self.gps_x_data, self.gps_y_data, self.gps_z_data,
                            color=color, linewidth=1, alpha=0.5,
                            label='Full Trajectory')

                filtered_x = self.gps_x_data[self.time_mask]
                filtered_y = self.gps_y_data[self.time_mask]
                filtered_z = self.gps_z_data[self.time_mask]

                if len(filtered_x) > 0:
                    # Get current color setting

                    self.ax.plot(filtered_x, filtered_y, filtered_z,
                                color=filtered_trajectory_color, linewidth=line_width,
                                label='Time-Filtered Segment')

                    # Add start/end markers for filtered segment if enabled
                    if self.show_markers_cb.isChecked():
                        if len(filtered_x) > 0:
                            self.ax.plot(filtered_x[0], filtered_y[0], filtered_z[0], 'go',
                                    markersize=8, label='Filtered Segment Start')
                        if len(filtered_x) > 1:
                            self.ax.plot(filtered_x[-1], filtered_y[-1], filtered_z[-1], 'rs',
                                    markersize=8, label='Filtered Segment End')

                    # Plot ground projection if enabled
                    if self.show_projection_cb.isChecked():
                        min_z = self.gps_z_data.min()
                        self.ground_projection = self.ax.plot(
                            filtered_x, filtered_y, min_z,
                            color=ground_color,
                            linewidth=1,
                            alpha=0.5,
                            label='Ground Projection'
                        )

        # Update legend
        self.ax.legend()

        # Refresh canvas
        self.canvas.draw()

    def clear_plot(self):
        """
        Clear the GPS 3D plot and reset axes.
        """
        self.ax.clear()
        self.ax.set_xlabel('GPS X (m)')
        self.ax.set_ylabel('GPS Y (m)')
        self.ax.set_zlabel('GPS Altitude (m)')
        self.ax.set_title('GPS 3D Trajectory')
        self.ax.grid(True, alpha=0.3)
        self.ax.set_aspect('equal', adjustable='box')

        # Reset line references
        self.trajectory_line = None
        self.start_marker = None
        self.end_marker = None
        self.ground_projection = None

        self.canvas.draw()

    def reset_view(self):
        """
        Reset view to show all data with automatic scaling and default angle.
        """
        if (self.gps_x_data is not None and self.gps_y_data is not None and
            self.gps_z_data is not None and len(self.gps_x_data) > 0):

            # Add some padding around the data
            x_range = self.gps_x_data.max() - self.gps_x_data.min()
            y_range = self.gps_y_data.max() - self.gps_y_data.min()
            z_range = self.gps_z_data.max() - self.gps_z_data.min()

            max_range = max(x_range, y_range, z_range)
            padding = max_range * 0.1

            # Center the data
            x_center = (self.gps_x_data.max() + self.gps_x_data.min()) / 2
            y_center = (self.gps_y_data.max() + self.gps_y_data.min()) / 2
            z_center = (self.gps_z_data.max() + self.gps_z_data.min()) / 2

            # Set equal aspect ratio by using the maximum range for all axes
            half_range = max_range / 2 + padding

            self.ax.set_xlim(x_center - half_range, x_center + half_range)
            self.ax.set_ylim(y_center - half_range, y_center + half_range)
            self.ax.set_zlim(z_center - half_range, z_center + half_range)

            # Set a nice default viewing angle
            self.ax.view_init(elev=30, azim=-45)

            self.canvas.draw()
        else:
            self.ax.autoscale()
            self.canvas.draw()


    def set_view(self, elevation, azimuth):
        """
        Set the 3D plot viewing angle.

        Args:
            elevation (float): Elevation angle.
            azimuth (float): Azimuth angle.
        """
        self.ax.view_init(elev=elevation, azim=azimuth)
        self.canvas.draw()

    def has_gps_3d_data(self):
        """
        Check if 3D GPS data is available for plotting.
        """
        return (self.gps_x_data is not None and self.gps_y_data is not None and
                self.gps_z_data is not None and len(self.gps_x_data) > 0)

    def sync_x_limits(self, x_min, x_max):
        """
        Synchronize x-axis limits with main plot panel and highlight relevant segment.

        Args:
            x_min (float): Minimum x-axis value (time)
            x_max (float): Maximum x-axis value (time)
        """

        # If we have time data, filter and highlight the relevant GPS trajectory segment
        if (self.gps_time_data is not None and
            self.gps_x_data is not None and
            self.gps_y_data is not None and
            self.gps_z_data is not None):

            # Find indices within the time range
            self.time_mask = (self.gps_time_data >= x_min) & (self.gps_time_data <= x_max)

            if np.any(self.time_mask):
                # Clear and replot with highlighting
                self._update_display()


    def setEnabled(self, enabled):
        """
        Enable or disable the GPS 3D plot panel.
        """
        super().setEnabled(enabled)
        if not enabled:
            self.clear_plot()

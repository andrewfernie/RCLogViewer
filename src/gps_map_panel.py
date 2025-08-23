"""
Copyright Andrew Fernie, 2025

gps_map_panel.py

Provides a QWidget-based panel for displaying GPS trajectory data on a 2D map using Folium and
Qt WebEngine. Features include interactive controls, color selection, time filtering,
persistent settings, and map tile selection.
"""
from typing import Iterable, List, Optional, Tuple
import numpy as np

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
)
from PySide6.QtCore import QSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

import folium
class GPS2DMap(QWidget):
    """
    QWidget-based panel for displaying GPS trajectory data on a 2D map using Folium.

    Features:
        - Interactive controls for map tiles, trajectory color, filtered color, and line width.
        - Selection between Open Street Map and ESRI satellite imagery datasets
        - If the user has used the zoom feature in the dataseries plot panel to examine a subset
          of the data, the plot will show the subset in one color and the full dataset in
          another color. Colors are configurable via the control panel.
        - Persistent color and style settings using QSettings.
        - Map rendering with Folium and display in Qt WebEngine.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the GPS2DMap widget and its UI components.
        """
        super().__init__(parent)
        self._zoom_factor: float = 1.0

        # GPS data arrays
        self.gps_lat_data: Optional[np.ndarray] = None
        self.gps_lon_data: Optional[np.ndarray] = None
        self.gps_time_data: Optional[np.ndarray] = None

        # Additional attributes initialized later
        self.time_mask: Optional[np.ndarray] = None
        self.center: List[float] = [0.0, 0.0]
        self.coords: List[Tuple[float, float]] = []
        self.m: Optional[folium.Map] = None

        # UI components (initialized in _setup_ui)
        self.tiles_combo: QComboBox
        self.trajectory_color_combo: QComboBox
        self.filtered_trajectory_color_combo: QComboBox
        self.line_width_combo: QComboBox
        self.reset_view_button: QPushButton
        self.web_view: QWebEngineView

        # Initialize QSettings for persistence
        self.settings: QSettings = QSettings('RCLogViewer', 'GPS2DMapPanel')

        self._setup_ui()

    def _setup_ui(self) -> None:
        """
        Set up the user interface, including map display, controls, and selectors.
        """
        layout = QVBoxLayout(self)

        # Web view that hosts the Folium map
        self.web_view = QWebEngineView()
        self.web_view.setZoomFactor(self._zoom_factor)
        layout.addWidget(self.web_view)

        # Controls row: imagery selector + (optional) zoom buttons
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Imagery:"))

        self.tiles_combo = QComboBox()
        self.tiles_combo.addItems(
            [
                "OpenStreetMap",
                "Esri Satellite",
            ]
        )
        self.tiles_combo.setCurrentText("OpenStreetMap")
        self.tiles_combo.currentTextChanged.connect(self._on_tiles_changed)
        controls_layout.addWidget(self.tiles_combo)

        # Trajectory Color selector
        controls_layout.addWidget(QLabel("Trajectory Color:"))

        self.trajectory_color_combo = QComboBox()
        self.trajectory_color_combo.addItems([
            "Blue", "Red", "Green", "Orange", "Purple", "Brown", "Pink", "Gray"
        ])
        self.trajectory_color_combo.setCurrentText("Blue")
        self.trajectory_color_combo.currentTextChanged.connect(self._on_color_changed)
        controls_layout.addWidget(self.trajectory_color_combo)

        # Filtered Trajectory Color selector
        controls_layout.addWidget(QLabel("Filtered Color:"))

        self.filtered_trajectory_color_combo = QComboBox()
        self.filtered_trajectory_color_combo.addItems([
            "Orange", "Red", "Green", "Blue", "Purple", "Brown", "Pink", "Gray"
        ])
        self.filtered_trajectory_color_combo.setCurrentText("Orange")
        self.filtered_trajectory_color_combo.currentTextChanged.connect(self._on_color_changed)
        controls_layout.addWidget(self.filtered_trajectory_color_combo)

        # Line Width selector
        controls_layout.addWidget(QLabel("Line Width:"))

        self.line_width_combo = QComboBox()
        self.line_width_combo.addItems(["1", "2", "3", "4", "5"])
        self.line_width_combo.setCurrentText("2")
        self.line_width_combo.currentTextChanged.connect(self._on_line_width_changed)
        controls_layout.addWidget(self.line_width_combo)

        # Reset View button
        self.reset_view_button = QPushButton("Reset View")
        self.reset_view_button.setToolTip("Reset zoom and center view on GPS track")
        self.reset_view_button.clicked.connect(self._on_reset_view)
        self.reset_view_button.setEnabled(False)  # Disabled until GPS data is loaded
        controls_layout.addWidget(self.reset_view_button)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        self._load_color_settings()

    def _get_trajectory_color(self, color_name: str) -> str:
        """
        Convert trajectory color name to folium color string.
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

    def _get_filtered_trajectory_color(self, color_name: str) -> str:
        """
        Convert filtered trajectory color name to folium color string.
        """
        color_map = {
            "Orange": "orange",
            "Red": "red",
            "Green": "green",
            "Blue": "blue",
            "Purple": "purple",
            "Brown": "brown",
            "Pink": "pink",
            "Gray": "gray"
        }
        return color_map.get(color_name, "orange")

    def _save_color_settings(self) -> None:
        """
        Save color and style selections to QSettings for persistence.
        """
        self.settings.setValue('trajectory_color', self.trajectory_color_combo.currentText())
        self.settings.setValue('filtered_trajectory_color',
                               self.filtered_trajectory_color_combo.currentText())
        self.settings.setValue('line_width', self.line_width_combo.currentText())

    def _load_color_settings(self) -> None:
        """
        Load color and style selections from QSettings for persistence.
        """
        saved_trajectory_color = self.settings.value('trajectory_color')
        if saved_trajectory_color:
            index = self.trajectory_color_combo.findText(saved_trajectory_color)
            if index >= 0:
                self.trajectory_color_combo.setCurrentIndex(index)

        saved_filtered_color = self.settings.value('filtered_trajectory_color')
        if saved_filtered_color:
            index = self.filtered_trajectory_color_combo.findText(saved_filtered_color)
            if index >= 0:
                self.filtered_trajectory_color_combo.setCurrentIndex(index)

        saved_line_width = self.settings.value('line_width')
        if saved_line_width:
            index = self.line_width_combo.findText(saved_line_width)
            if index >= 0:
                self.line_width_combo.setCurrentIndex(index)

    def _on_color_changed(self) -> None:
        """
        Handle color combo box changes and update display.
        """
        self._save_color_settings()
        self._update_display()

    def _on_line_width_changed(self) -> None:
        """
        Handle line width combo box changes and update display.
        """
        self._save_color_settings()
        self._update_display()

    # --- Public API ---
    def render_gps_path(self, latitudes: Iterable[float], longitudes: Iterable[float],
                        time_data: Iterable[float]) -> None:
        """
        Render a Folium map with the provided GPS path and optional filtered path.

        Args:
            latitudes (Iterable[float]): GPS latitude data.
            longitudes (Iterable[float]): GPS longitude data.
            time_data (Iterable[float]): Time data for synchronization.
        """
        self.gps_lat_data = np.asarray(latitudes, dtype=float) \
            if latitudes is not None else np.array([])
        self.gps_lon_data = np.asarray(longitudes, dtype=float) \
            if longitudes is not None else np.array([])
        self.gps_time_data = np.asarray(time_data, dtype=float) \
            if time_data is not None else np.array([])

        valid_mask_nan = ~(np.isnan(self.gps_lat_data) | np.isnan(self.gps_lon_data) |
                       np.isnan(self.gps_time_data))

        self.gps_lat_data = self.gps_lat_data[valid_mask_nan]
        self.gps_lon_data = self.gps_lon_data[valid_mask_nan]
        self.gps_time_data = self.gps_time_data[valid_mask_nan]

        # Filter out invalid GPS coordinates

        valid_mask_numeric = (self.gps_lat_data >= -90.0) & (self.gps_lat_data <= 90.0) & \
                           (self.gps_lon_data >= -180.0) & (self.gps_lon_data <= 180.0)

        self.gps_lat_data = self.gps_lat_data[valid_mask_numeric]
        self.gps_lon_data = self.gps_lon_data[valid_mask_numeric]
        self.gps_time_data = self.gps_time_data[valid_mask_numeric]

        # Create a time mask for filtering. Initially, it has all values set to True
        self.time_mask = np.ones_like(self.gps_time_data, dtype=bool)

        # Calculate center of the GPS path as the average of the latitude and longitude data
        if self.gps_lat_data is None or self.gps_lon_data is None:
            self.center = [0.0, 0.0]
        else:
            self.center = [
                (self.gps_lat_data.max() + self.gps_lat_data.min()) / 2,
                (self.gps_lon_data.max() + self.gps_lon_data.min()) / 2
            ]

        #create a list of coordinates
        self.coords = list(zip(self.gps_lat_data, self.gps_lon_data))

        # Clear previous plot
        self.clear()

        # Plot the trajectory
        self._update_display()

        # Fit bounds using the extents of the data points to be plotted
        sw_corner = [self.gps_lat_data.min(), self.gps_lon_data.min()]
        ne_corner = [self.gps_lat_data.max(), self.gps_lon_data.max()]
        self.m.fit_bounds([sw_corner, ne_corner])


    def _update_display(self) -> None:
        """
        Update the map display based on current settings and filters.
        """
        if self.gps_lat_data is None or self.gps_lon_data is None:
            return

        # Build Folium map with selected tiles
        self.m = folium.Map(location=self.center, zoom_start=18, control_scale=True,
                            zoom_control=True, tiles=None)
        tiles_name = self.tiles_combo.currentText()
        self._add_tiles_layer(self.m, tiles_name)


        # Get colors for the trajectory and filtered trajectory
        filtered_color = self._get_filtered_trajectory_color(
            self.filtered_trajectory_color_combo.currentText())

        trajectory_color = self._get_trajectory_color(
            self.trajectory_color_combo.currentText())

        # Get line width
        line_width = int(self.line_width_combo.currentText())

        # Determine if there are any false values in self.time_mask, indicating that a
        # filter is applied
        is_filtered = not np.all(self.time_mask)

        if not is_filtered:
            # Plot the full trajectory
            folium.PolyLine(self.coords, color=trajectory_color, weight=line_width, opacity=1.0
                            ).add_to(self.m)

             # Display markers for the start and finish of the full trajectory
            folium.Marker(location=self.coords[0], tooltip="Trajectory Start",
                          icon=folium.Icon(color="green")).add_to(self.m)

            if len(self.coords) > 1:
                folium.Marker(
                    location=self.coords[-1], tooltip="Trajectory End",
                    icon=folium.Icon(color="red")).add_to(self.m)
        else:
            # Plot the full trajectory with a narrow line
            folium.PolyLine(self.coords, color=trajectory_color, weight=1, opacity=0.8
                            ).add_to(self.m)

            # Display markers for the start and finish of the full trajectory
            folium.Marker(location=self.coords[0], tooltip="Full Trajectory Start",
                          icon=folium.Icon(color="green")).add_to(self.m)

            if len(self.coords) > 1:
                folium.Marker(
                    location=self.coords[-1], tooltip="Full Trajectory End",
                    icon=folium.Icon(color="red")).add_to(self.m)

            # Plot the filtered trajectory using the mask on the original data with
            # a different color and a thicker line
            filtered_coords = list(zip(self.gps_lat_data[self.time_mask],
                                     self.gps_lon_data[self.time_mask]))
            if filtered_coords:
                folium.PolyLine(filtered_coords, color=filtered_color, weight=line_width,
                                opacity=0.8).add_to(self.m)

                # Display markers for the start and finish of the filtered trajectory
                folium.Marker(location=filtered_coords[0], tooltip="Filtered Trajectory Start",
                              icon=folium.Icon(color="green")).add_to(self.m)

                if len(filtered_coords) > 1:
                    folium.Marker(
                        location=filtered_coords[-1], tooltip="Filtered Trajectory End",
                        icon=folium.Icon(color="red")).add_to(self.m)

        # Render and display
        html = self.m.get_root().render()
        self.web_view.setHtml(html)

        # Enable reset view button now that we have GPS data
        self.reset_view_button.setEnabled(True)

    # --- Internal helpers ---
    def _on_tiles_changed(self, _: str) -> None:
        """
        Handle map tile selection changes and update display.
        """
        # Re-render if we have previous coordinates
        self._update_display()

    def _on_reset_view(self) -> None:
        """
        Reset the map view to center on the GPS track with appropriate zoom.
        """
        self._update_display()

    def _add_tiles_layer(self, m: folium.Map, tiles_name: str) -> None:
        """
        Add the selected map tile layer to the Folium map.
        """
        if tiles_name == "OpenStreetMap":
            folium.TileLayer("OpenStreetMap").add_to(m)
        elif tiles_name == "Esri Satellite":
            folium.TileLayer(
                tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery"
                      "/MapServer/tile/{z}/{y}/{x}",
                attr=(
                    "Tiles &copy; Esri — Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, "
                    "Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community"
                ),
                name="Esri World Imagery",
            ).add_to(m)
        else:
            folium.TileLayer("OpenStreetMap").add_to(m)

    def clear(self) -> None:
        """
        Clear the map display and reset controls.
        """
        try:
            self.web_view.setHtml("")
        except Exception:
            pass

        self.reset_view_button.setEnabled(False)

    def cleanup(self) -> None:
        """
        Clean up resources before shutdown.
        """
        try:
            # Stop any ongoing page loads
            if hasattr(self.web_view, 'stop'):
                self.web_view.stop()

            # Clear the web view content
            if hasattr(self.web_view, 'setHtml'):
                self.web_view.setHtml("")

            # Process any pending events
            app = QApplication.instance()
            if app:
                app.processEvents()

            # Get and explicitly delete the web page
            if hasattr(self.web_view, 'page'):
                page = self.web_view.page()
                if page:
                    # Disconnect signals to avoid issues during cleanup
                    try:
                        page.disconnect()
                    except:
                        pass
                    # Delete the page explicitly
                    try:
                        page.deleteLater()
                        self.web_view.setPage(None)
                    except:
                        pass

            # Reset state variables
            self.reset_view_button.setEnabled(False)

        except Exception:
            pass

    def sync_x_limits(self, x_min: float, x_max: float) -> None:
        """
        Synchronize x-axis limits with main plot panel and highlight relevant segment.

        Args:
            x_min (float): Minimum x-axis value (time)
            x_max (float): Maximum x-axis value (time)
        """

        # If we have time data, filter and highlight the relevant GPS trajectory segment
        if (self.gps_time_data is not None and
            self.gps_lat_data is not None and
            self.gps_lon_data is not None ):

            # Find indices within the time range
            self.time_mask = (self.gps_time_data >= x_min) & (self.gps_time_data <= x_max)

            if np.any(self.time_mask):
                # Clear and replot with highlighting
                self._update_display()

    def closeEvent(self, event) -> None:
        """
        Handle close event and perform cleanup.
        """
        try:
            self.cleanup()
        except Exception:
            pass
        super().closeEvent(event)

    def __del__(self) -> None:
        """
        Destructor - ensure cleanup.
        """
        try:
            self.cleanup()
        except Exception:
            pass

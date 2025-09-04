"""
Copyright Andrew Fernie, 2025

Main application window for RC Log Viewer.

This module defines the MainWindow class, which orchestrates all GUI panels and user interactions
for viewing and analyzing RC log files. It integrates file management, data visualization, GPS
plotting, map display, and analysis features using PySide6, matplotlib, and folium.
"""

import os
import json
import tempfile
import subprocess
from typing import List

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QSplitter, QTabWidget, QSizePolicy, QInputDialog,
                               QFileDialog, QMessageBox, QProgressBar, QLabel,
                               QScrollArea, QApplication)

from PySide6.QtCore import Qt, QTimer, QThread
from PySide6.QtGui import QAction, QCloseEvent, QIcon

from file_panel import FilePanel
from folder_panel import FolderPanel
from channel_panel import ChannelPanel
from dataseries_plot_panel import DataSeriesPlotPanel
from gps_plot_panel import GPSXYPlotPanel
from gps_3d_plot_panel import GPSXYZ3DPlotPanel
from gps_map_panel import GPS2DMap
from analysis_panel import AnalysisPanel
from data_panel import DataPanel
from log_processor import LogProcessor


class MainWindow(QMainWindow):
    """
    Main application window for RC Log Viewer.

    This class manages the layout, menu actions, status bar, and all major panels for log file
    analysis. It coordinates file loading, data export, plotting, and GPS visualization features.
    """

    def __init__(self):
        """
        Initialize the main window and set up all panels, menus, and signals.
        """

        super().__init__()
        # Set application window icon
        icon_path = os.path.join(os.path.dirname(__file__), '../images/rclogviewer_icon.png')
        self.setWindowIcon(QIcon(icon_path))
        self.processor = LogProcessor()

        # Read the contents of the configuration file "rclogviewer_config.json"
        config_file_path = "rclogviewer_config.json"
        if os.path.exists(config_file_path):
            with open(config_file_path, "r") as config_file:
                config_string = config_file.read()
        else:
            config_string = ""

        self.config = json.loads(config_string)

        self.setWindowTitle("RC Log Viewer - PySide6")
        self.setGeometry(100, 100, 1400, 900)

        self._setup_ui()
        self._setup_menu()
        self._setup_status_bar()
        self._connect_signals()

        # Update UI state
        self._update_ui_state()

        # Restore last opened file
        # self._restore_last_file()

    def _setup_ui(self) -> None:
        """
        Set up the main UI layout, including splitters, panels, and tabs.
        """

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout(central_widget)

        # Create main splitter
        main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(main_splitter)

        # Left panel (file operations and channel selection)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # File panel
        self.file_panel = FilePanel()
        self.file_panel.setFixedHeight(300)
        left_layout.addWidget(self.file_panel)

        # Folder panel (recent folders)
        self.folder_panel = FolderPanel()
        self.folder_panel.setFixedHeight(200)
        left_layout.addWidget(self.folder_panel)

        # Channel panel
        self.channel_panel = ChannelPanel()
        left_layout.addWidget(self.channel_panel)

        # Create scroll area for the left panel
        scroll_area = QScrollArea()
        scroll_area.setWidget(left_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setMaximumWidth(350)

        main_splitter.addWidget(scroll_area)

        # Right panel (tabbed interface for plots and analysis)
        self.tab_widget = QTabWidget()

        # Plot tab
        self.plot_panel = DataSeriesPlotPanel()
        self.tab_widget.addTab(self.plot_panel, "Plot View")

        # GPS XY plot tab
        self.gps_plot_panel = GPSXYPlotPanel()
        self.tab_widget.addTab(self.gps_plot_panel, "GPS-XY")

        # GPS 3D plot tab
        self.gps_3d_plot_panel = GPSXYZ3DPlotPanel()
        self.tab_widget.addTab(self.gps_3d_plot_panel, "GPS-XYZ")

        # GPS 2D Map tab (using new GPS2DMap widget)
        self.gps_2d_map_panel = GPS2DMap()
        self.tab_widget.addTab(self.gps_2d_map_panel, "GPS Map")

        # Connect plot panel x-limits changes to GPS panels
        self.plot_panel.x_limits_changed.connect(
            self.gps_plot_panel.sync_x_limits)
        self.plot_panel.x_limits_changed.connect(
            self.gps_3d_plot_panel.sync_x_limits)
        self.plot_panel.x_limits_changed.connect(
            self.gps_2d_map_panel.sync_x_limits)

        # Analysis tab (comprehensive log analysis)
        self.analysis_panel = AnalysisPanel()
        self.tab_widget.addTab(self.analysis_panel, "Analysis")

        # Data tab (tabular data view)
        self.data_panel = DataPanel()
        self.tab_widget.addTab(self.data_panel, "Data View")

        main_splitter.addWidget(self.tab_widget)

        # Set splitter proportions
        main_splitter.setSizes([350, 1050])

    def _setup_menu(self) -> None:
        """
        Set up the application menus and connect actions to their respective handlers.
        """

        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        # Open action
        open_action = QAction("&Open Log File...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.setStatusTip("Open a log file")
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        # Export action
        export_action = QAction("&Export Data...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.setStatusTip("Export filtered data")
        export_action.triggered.connect(self._export_data)
        file_menu.addAction(export_action)

        # Export as KML action
        self.export_kml_action = QAction("Export as K&ML file...", self)
        self.export_kml_action.setStatusTip("Export GPS data to KML file")
        self.export_kml_action.triggered.connect(self._export_as_kml)
        # Disabled until GPS data is available
        self.export_kml_action.setEnabled(False)
        file_menu.addAction(self.export_kml_action)

        # View as KML action
        self.view_kml_action = QAction("View as &KML", self)
        self.view_kml_action.setShortcut("Ctrl+K")
        self.view_kml_action.setStatusTip(
            "Export GPS data to KML and open with default application")
        self.view_kml_action.triggered.connect(self._view_as_kml)
        # Disabled until GPS data is available
        self.view_kml_action.setEnabled(False)
        file_menu.addAction(self.view_kml_action)

        file_menu.addSeparator()

        # Exit action
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Exit application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        # Reset zoom action
        reset_zoom_action = QAction("&Reset Zoom", self)
        reset_zoom_action.setShortcut("Ctrl+R")
        reset_zoom_action.setStatusTip("Reset plot zoom")
        reset_zoom_action.triggered.connect(self.plot_panel.reset_zoom)
        view_menu.addAction(reset_zoom_action)

        # Clear plots action
        clear_plots_action = QAction("&Clear Plots", self)
        clear_plots_action.setShortcut("Ctrl+Shift+C")
        clear_plots_action.setStatusTip("Clear all plots")
        clear_plots_action.triggered.connect(self._clear_all_plots)
        view_menu.addAction(clear_plots_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        # About action
        about_action = QAction("&About", self)
        about_action.setStatusTip("About this application")
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_status_bar(self) -> None:
        """
        Set up the status bar with progress bar, status label, and file info label.
        """

        self.status_bar = self.statusBar()

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        # File info label
        self.file_info_label = QLabel("")
        self.status_bar.addPermanentWidget(self.file_info_label)

    def _connect_signals(self) -> None:
        """
        Connect signals between panels and update UI state when selections change.
        """

        # File panel signals
        self.file_panel.file_selected.connect(self._load_file)

        # Folder panel signals
        self.folder_panel.folder_selected.connect(self._show_folder_log_files)

        # Channel panel signals
        self.channel_panel.channels_selection_changed.connect(
            self._update_plot_selection)

    def _show_folder_log_files(self, folder_path: str):
        """Show a dialog listing log files in the selected folder and allow user to open one."""

        # List log files in the folder
        log_files = [f for f in os.listdir(folder_path)
                    if os.path.isfile(os.path.join(folder_path, f)) and f.lower().endswith(('.csv', '.tlog', '.bin'))]
        if not log_files:
            QMessageBox.information(self, "No Log Files", "No log files found in this folder.")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Log File",
            folder_path,
            "Log Files (*.csv *.tlog *.bin);;CSV Files (*.csv);;TLog Files (*.tlog);;bin Files (*.bin);;All Files (*)"
        )

        if file_path:
            self._load_file(file_path)
            # Add to Recent Files list
            self.file_panel._set_current_file(file_path)


    def _update_ui_state(self) -> None:
        """
        Update the enabled/disabled state of panels and menu actions based on data availability.
        Refreshes channel lists, analysis, data views, and GPS plots according to the loaded log
        file.
        """

        has_data = (self.processor.current_log is not None and
                    self.processor.current_log.processed_data is not None)

        # Update panels
        self.channel_panel.setEnabled(has_data)
        self.plot_panel.setEnabled(has_data)

        # Check for GPS data availability
        has_gps_data = (has_data and
                        'GPS.X (m)' in self.processor.current_log.channels and
                        'GPS.Y (m)' in self.processor.current_log.channels)
        self.tab_widget.setTabEnabled(
            self.tab_widget.indexOf(self.gps_plot_panel), has_gps_data)

        # Check for GPS 3D data availability (XY + altitude)
        # Look for various altitude column names
        altitude_columns = ['GPS alt (m)', 'GPS.alt (m)', 'GPS.Alt (m)', 'GPS_alt (m)',
                            'Altitude (m)', 'Alt (m)', 'altitude', 'GPS.Altitude',
                            'GPS Altitude']
        gps_alt_column = None
        if has_gps_data:
            for alt_col in altitude_columns:
                if alt_col in self.processor.current_log.channels:
                    gps_alt_column = alt_col
                    break

        has_gps_3d_data = has_gps_data and gps_alt_column is not None
        self.tab_widget.setTabEnabled(self.tab_widget.indexOf(
            self.gps_3d_plot_panel), has_gps_3d_data)

        # Check for GPS lat/lon data for 2D map
        has_gps_latlon_data = False
        lat_col = None
        lon_col = None
        if has_data:
            for ch in self.processor.current_log.channels:
                cl = ch.lower()
                if lat_col is None and ("latitude" in cl or cl.endswith("lat") or ".lat" in cl):
                    lat_col = ch
                if lon_col is None and ("longitude" in cl or cl.endswith("lon") or ".lon" in cl or ".lng" in cl):
                    lon_col = ch

            has_gps_latlon_data = lat_col is not None and lon_col is not None

        self.tab_widget.setTabEnabled(self.tab_widget.indexOf(self.gps_2d_map_panel),
                                      has_gps_latlon_data)

        # Enable/disable KML export based on GPS lat/lon data availability
        self.view_kml_action.setEnabled(has_gps_latlon_data)
        self.export_kml_action.setEnabled(has_gps_latlon_data)

        # Enable/disable plotting, analysis, and data panels based on data availability
        self.tab_widget.setTabEnabled(
            self.tab_widget.indexOf(self.plot_panel), has_data)
        self.tab_widget.setTabEnabled(
            self.tab_widget.indexOf(self.analysis_panel), has_data)
        self.tab_widget.setTabEnabled(
            self.tab_widget.indexOf(self.data_panel), has_data)

        if has_data:
            # Update channel list
            channels = self.processor.current_log.channels
            self.channel_panel.update_channels(channels, self.filetype_config)

            # Update analysis panel
            self.analysis_panel.update_analysis(self.processor.current_log)

            # Update data panel
            self.data_panel.update_data(self.processor.current_log)

            # Update GPS plot if GPS data is available
            self.tab_widget.setTabEnabled(
                self.tab_widget.indexOf(self.gps_plot_panel), False)
            self.gps_plot_panel.clear_plot()
            if has_gps_data:
                x_data_full = self.processor.get_channel_data('GPS.X (m)')
                y_data_full = self.processor.get_channel_data('GPS.Y (m)')
                time_data_full = self.processor.get_time_data()

                # Because each line (or message) in the input log file creates its own line in
                # the dataframe, and each line in the dataframe contains all channels, we can
                # end up with many duplicate points. So, create new arrays that only contain
                # values that are different from the previous values.
                x_data = []
                y_data = []
                time_data = []
                for i in range(len(x_data_full)):
                    if i == 0 or (x_data_full[i] != x_data_full[i - 1] or y_data_full[i] != y_data_full[i - 1]):
                        x_data.append(x_data_full[i])
                        y_data.append(y_data_full[i])
                        time_data.append(time_data_full[i])

                if x_data is not None and y_data is not None:
                    self.gps_plot_panel.plot_gps_trajectory(
                        x_data, y_data, time_data)
                    self.tab_widget.setTabEnabled(
                        self.tab_widget.indexOf(self.gps_plot_panel), True)

            # Update GPS 2D Map if lat/lon data is available
            self.tab_widget.setTabEnabled(
                self.tab_widget.indexOf(self.gps_2d_map_panel), False)
            self.gps_2d_map_panel.clear()
            if has_gps_latlon_data and lat_col and lon_col:
                latitudes_full = self.processor.get_channel_data(lat_col)
                longitudes_full = self.processor.get_channel_data(lon_col)
                time_data_full = self.processor.get_time_data()

                # Remove duplicate (repeated) points
                latitudes = []
                longitudes = []
                time_data = []
                for i in range(len(latitudes_full)):
                    if i == 0 or (latitudes_full[i] != latitudes_full[i - 1] or
                                  longitudes_full[i] != longitudes_full[i - 1]):
                        latitudes.append(latitudes_full[i])
                        longitudes.append(longitudes_full[i])
                        time_data.append(time_data_full[i])

                if latitudes is not None and longitudes is not None:
                    self.gps_2d_map_panel.render_gps_path(
                        latitudes, longitudes, time_data)
                    self.tab_widget.setTabEnabled(
                        self.tab_widget.indexOf(self.gps_2d_map_panel), True)

            # Update GPS 3D plot if GPS 3D data is available
            self.tab_widget.setTabEnabled(
                self.tab_widget.indexOf(self.gps_3d_plot_panel), False)
            self.gps_3d_plot_panel.clear_plot()
            if has_gps_3d_data:
                x_data_full = self.processor.get_channel_data('GPS.X (m)')
                y_data_full = self.processor.get_channel_data('GPS.Y (m)')
                z_data_full = self.processor.get_channel_data(gps_alt_column)
                time_data_full = self.processor.get_time_data()

                # Remove duplicate (repeated) points
                x_data = []
                y_data = []
                z_data = []
                time_data = []
                for i in range(len(x_data_full)):
                    if i == 0 or (x_data_full[i] != x_data_full[i - 1]
                                  or y_data_full[i] != y_data_full[i - 1]
                                  or z_data_full[i] != z_data_full[i - 1]):
                        x_data.append(x_data_full[i])
                        y_data.append(y_data_full[i])
                        z_data.append(z_data_full[i])
                        time_data.append(time_data_full[i])

                if x_data is not None and y_data is not None and z_data is not None:
                    self.gps_3d_plot_panel.plot_gps_trajectory_3d(
                        x_data, y_data, z_data, time_data)
                    self.tab_widget.setTabEnabled(
                        self.tab_widget.indexOf(self.gps_3d_plot_panel), True)

            # Update status
            metadata = self.processor.current_log.metadata
            duration = metadata.get('duration', 0)
            info_text = f"Samples: {metadata.get('num_samples', 0)} | "
            info_text += f"Channels: {metadata.get('num_channels', 0)} | "
            info_text += f"Duration: {duration:.2f}s ({duration/60:.0f}:{duration % 60:02.0f})"
            self.file_info_label.setText(info_text)
        else:
            self.channel_panel.clear()
            self.plot_panel.clear_plots()
            self.gps_plot_panel.clear_plot()
            self.gps_3d_plot_panel.clear_plot()
            self.gps_2d_map_panel.clear()
            self.analysis_panel.update_analysis(None)  # Clear analysis
            self.data_panel.update_data(None)  # Clear data view
            self.file_info_label.setText("")

    def _open_file(self):
        """Open file dialog and load selected file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Log File",
            "",
            "Log Files (*.csv *.tlog *.bin);;All Files (*)"
        )

        if file_path:
            self._load_file(file_path)

    def _load_file(self, file_path: str) -> None:
        """
        Load the selected log file and update all relevant panels and UI elements.

        This method is called when a file is opened either through the menu or directly
        from the file panel. It handles the file loading process, error reporting, and
        UI updates upon successful or failed loading.

        Args:
            file_path (str): The path to the log file to be loaded.
        """

        try:
            self.status_label.setText("Loading file...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 100)
            QApplication.processEvents()  # Allow UI to update

            def progress_callback(percent):
                self.progress_bar.setValue(int(percent))
                QApplication.processEvents()

            # Load the file
            success = self.processor.load_file(
                file_path, self.config, progress_callback)

            if success:
                self.status_label.setText("File loaded successfully")
                self.filetype = file_path.split('.')[-1].lower()

                # Add folder to FolderPanel
                import os
                folder_path = os.path.dirname(file_path)
                self.folder_panel.add_folder(folder_path)

                if self.filetype == 'csv':
                    self.filetype_config = self.config["csv_file"]
                elif self.filetype == 'tlog':
                    self.filetype_config = self.config["tlog_file"]
                elif self.filetype == 'bin':
                    self.filetype_config = self.config["bin_file"]

                self._update_ui_state()
                QTimer.singleShot(
                    3000, lambda: self.status_label.setText("Ready"))
            else:
                self.status_label.setText("Failed to load file")
                self.filetype = ""
                QMessageBox.warning(
                    self,
                    "Load Error",
                    "Failed to load the selected file. Please check the file format."
                )
                QTimer.singleShot(
                    3000, lambda: self.status_label.setText("Ready"))
        except Exception as e:
            self.status_label.setText("Failed to load file")
            QMessageBox.warning(
                self,
                "Load Error",
                f"Failed to load the selected file: {str(e)}"
            )
            QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
        finally:
            self.progress_bar.setVisible(False)

    def _update_plot_selection(self, selected_channels: List[str]):
        """Update plot to show only selected channels."""
        if self.processor.current_log is None:
            return

        # Clear current plots
        self.plot_panel.clear_plots()

        # If no channels selected, just clear
        if not selected_channels:
            self.status_label.setText("All channels deselected")
            QTimer.singleShot(1000, lambda: self.status_label.setText("Ready"))
            return

        # Plot all selected channels
        time_data = self.processor.get_time_data()
        if time_data is None:
            return

        channel_data = {}
        for channel in selected_channels:
            data = self.processor.get_channel_data(channel)
            if data is not None:
                channel_data[channel] = data

        if channel_data:
            self.plot_panel.plot_dataseries(time_data, channel_data)
            if len(selected_channels) == 1:
                self.status_label.setText(f"Plotted: {selected_channels[0]}")
            else:
                self.status_label.setText(
                    f"Plotted {len(channel_data)} channels")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Ready"))

    def _export_data(self) -> None:
        """Export filtered data to CSV."""
        if self.processor.current_log is None:
            QMessageBox.information(
                self, "No Data", "No log file is currently loaded.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if file_path:
            # Get selected channels from channel panel
            selected_channels = self.channel_panel.get_selected_channels()

            success = self.processor.export_filtered_data(
                file_path,
                channels=selected_channels if selected_channels else None
            )

            if success:
                QMessageBox.information(
                    self, "Export Complete", f"Data exported to {file_path}")
            else:
                QMessageBox.warning(self, "Export Error",
                                    "Failed to export data.")

    def _export_as_kml(self) -> None:
        """
        Export the current GPS data to a KML file.

        This method prompts the user for a file location and name, then generates a KML file
        containing the GPS track data. The KML file can be opened in mapping applications
        like Google Earth.

        If the export is successful, the KML file is saved to the specified location.

        Args:
            None
        """

        if self.processor.current_log is None:
            QMessageBox.information(
                self, "No Data", "No log file is currently loaded.")
            return

        # Generate default filename based on current log file
        default_filename = ""
        if hasattr(self.processor.current_log, 'file_path') and \
           self.processor.current_log.file_path:
            # Get the base filename without extension and add .kml
            base_name = os.path.splitext(os.path.basename(str(
                self.processor.current_log.file_path)))[0]
            default_filename = f"{base_name}.kml"
        else:
            default_filename = "gps_track.kml"

        # Prompt user for save location
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export KML File",
            default_filename,
            "KML Files (*.kml);;All Files (*)"
        )

        if file_path:
            # Ensure .kml extension
            if not file_path.lower().endswith('.kml'):
                file_path += '.kml'

            # Use the existing _generate_kml_file method
            self._generate_kml_file(file_path)

    def _view_as_kml(self) -> None:
        """
        Export the current GPS data to a KML file and open it in the default application.

        This method generates a KML file containing the GPS track data and attempts to open
        the file in the default mapping application (e.g., Google Earth). The KML file is
        generated in a temporary location and deleted after use.

        If the export or opening fails, an error message is displayed.

        Args:
            None
        """

        try:
            # Get a unique temporary filename without keeping the file open
            fd, temp_base_path = tempfile.mkstemp()
            os.close(fd)  # Close the file descriptor immediately
            # Remove the empty file created by mkstemp
            os.remove(temp_base_path)
            temp_path = f"{temp_base_path}.kml"

            # Generate KML file
            self._generate_kml_file(temp_path)

            # Open with default application
            if os.name == 'nt':  # Windows
                os.startfile(temp_path)
            elif os.name == 'posix':  # macOS and Linux
                if os.uname().sysname == 'Darwin':  # macOS
                    subprocess.run(['open', temp_path])
                else:  # Linux
                    subprocess.run(['xdg-open', temp_path])

            self.status_label.setText(f"KML exported and opened: {temp_path}")
            QTimer.singleShot(5000, lambda: self.status_label.setText("Ready"))

        except Exception as e:
            QMessageBox.warning(self, "KML Export Error",
                                f"Failed to export or open KML file: {str(e)}")

    def _generate_kml_file(self, filename: str) -> None:
        """
        Generate a KML file from the current GPS data.

        This method creates a KML file containing the GPS track data, including optional
        altitude information. The generated KML file can be used to visualize the GPS track
        in mapping applications like Google Earth.

        The method detects latitude, longitude, and altitude columns in the current log data
        and uses this information to create the KML content. If the required data is missing
        or invalid, an error message is displayed.

        Args:
            filename (str): The path to the file where the KML content will be saved.

        Raises:
            ValueError: If no valid GPS coordinates are found.
        """

        if self.processor.current_log is None:
            QMessageBox.warning(
                self, "No Data", "No log file is currently loaded.")
            return

        # Find GPS lat/lon columns and altitude column
        lat_col = None
        lon_col = None
        alt_col = None
        for ch in self.processor.current_log.channels:
            cl = ch.lower()
            if lat_col is None and ("latitude" in cl or cl.endswith("lat") or ".lat" in cl):
                lat_col = ch
            if lon_col is None and ("longitude" in cl or cl.endswith("lon") or ".lon" in cl or ".lng" in cl):
                lon_col = ch
            if alt_col is None and ("gps alt" in cl or "gps.alt" in cl or "altitude" in cl
                                    or cl.endswith("alt")):
                alt_col = ch

        if not lat_col or not lon_col:
            QMessageBox.warning(self,
                                "No GPS Data", "No latitude/longitude data found in the log file.")
            return

        # Get GPS data
        latitudes = self.processor.get_channel_data(lat_col)
        longitudes = self.processor.get_channel_data(lon_col)
        altitudes = None

        if alt_col:
            altitudes = self.processor.get_channel_data(alt_col)

        if latitudes is None or longitudes is None:
            QMessageBox.warning(self, "Data Error",
                                "Failed to retrieve GPS coordinate data.")
            return

        if len(latitudes) == 0 or len(longitudes) == 0:
            QMessageBox.warning(self, "No GPS Data",
                                "GPS coordinate data is empty.")
            return

        try:
            # Create KML content
            kml_content = self._generate_kml_content(latitudes, longitudes,
                                                     lat_col, lon_col,
                                                     altitudes, alt_col)

            # Create KML file
            with open(filename, 'w', encoding='utf-8') as kml_file:
                kml_file.write(kml_content)

            self.status_label.setText(f"KML exported to: {filename}")
            QTimer.singleShot(5000, lambda: self.status_label.setText("Ready"))

        except Exception as e:
            QMessageBox.warning(self, "KML Export Error",
                                f"Failed to export or open KML file: {str(e)}")

    def _generate_kml_content(self, latitudes, longitudes,
                              lat_col_name, lon_col_name,
                              altitudes=None, alt_col_name=None):
        """Generate KML content from GPS coordinates with optional altitude data."""
        # Filter valid coordinates
        valid_coords = []
        data_length = min(len(latitudes), len(longitudes))
        if altitudes is not None:
            data_length = min(data_length, len(altitudes))

        # Because each line (or message) in the input log file creates its own line in the dataframe, and
        # each line in the dataframe contains all channels, we can end up with many duplicate points.
        # While there doesn't seem to be a defined limit to the number of points in a kml file, eventually
        # the programs that render the kml (e.g. Google Earth) will refuse to display it.  So, we only keep
        # the last unique point for each (lat, lon, alt) combination.
        last_lat = None
        last_lon = None
        last_alt = None

        for i in range(data_length):
            try:
                lat = float(latitudes[i])
                lon = float(longitudes[i])
                if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                    # Include altitude if available
                    if altitudes is not None:
                        try:
                            alt = float(altitudes[i])
                            # KML uses lon,lat,alt order
                            if lat != last_lat or lon != last_lon or alt != last_alt:
                                valid_coords.append((lon, lat, alt))
                                last_lat = lat
                                last_lon = lon
                                last_alt = alt

                        except (ValueError, TypeError):
                            # Default altitude to 0 if invalid
                            alt = 0
                            if lat != last_lat or lon != last_lon or alt != last_alt:
                                valid_coords.append((lon, lat, alt))
                                last_lat = lat
                                last_lon = lon
                                last_alt = alt
                    else:
                        # Default altitude to 0 if no alt. data
                        alt = 0
                        if lat != last_lat or lon != last_lon or alt != last_alt:
                            valid_coords.append((lon, lat, alt))
                            last_lat = lat
                            last_lon = lon
                            last_alt = alt

            except (ValueError, TypeError):
                continue

        if not valid_coords:
            raise ValueError("No valid GPS coordinates found")

        # Generate KML content
        description = "GPS track exported from RC Log Viewer"
        if altitudes is not None and alt_col_name:
            description += f" with altitude data from {alt_col_name}"

        kml_header = f'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>RC Log GPS Track</name>
    <description>{description}</description>
    <Style id="trackStyle">
      <LineStyle>
        <color>ff0000ff</color>
        <width>3</width>
      </LineStyle>
    </Style>
    <Style id="startStyle">
      <IconStyle>
        <color>ff00ff00</color>
        <Icon>
          <href>http://maps.google.com/mapfiles/kml/pushpin/grn-pushpin.png</href>
        </Icon>
      </IconStyle>
    </Style>
    <Style id="endStyle">
      <IconStyle>
        <color>ff0000ff</color>
        <Icon>
          <href>http://maps.google.com/mapfiles/kml/pushpin/red-pushpin.png</href>
        </Icon>
      </IconStyle>
    </Style>'''

        # Start marker
        start_marker = f'''
    <Placemark>
      <name>Start</name>
      <description>Track start point</description>
      <styleUrl>#startStyle</styleUrl>
      <Point>
        <coordinates>{valid_coords[0][0]},{valid_coords[0][1]},{valid_coords[0][2]}</coordinates>
      </Point>
    </Placemark>'''

        # End marker (if more than one point)
        end_marker = ""
        if len(valid_coords) > 1:
            end_marker = f'''
    <Placemark>
      <name>End</name>
      <description>Track end point</description>
      <styleUrl>#endStyle</styleUrl>
      <Point>
        <coordinates>{valid_coords[-1][0]},{valid_coords[-1][1]},{valid_coords[-1][2]}</coordinates>
      </Point>
    </Placemark>'''

        # Track line with altitude
        coordinates_str = " ".join(
            [f"{lon},{lat},{alt}" for lon, lat, alt in valid_coords])
        track_description = f"GPS track from {lat_col_name} and {lon_col_name}"
        if altitudes is not None and alt_col_name:
            track_description += f" with altitude from {alt_col_name}"

        track_line = f'''
    <Placemark>
      <name>GPS Track</name>
      <description>{track_description}</description>
      <styleUrl>#trackStyle</styleUrl>
      <LineString>
        <altitudeMode>absolute</altitudeMode>
        <coordinates>{coordinates_str}</coordinates>
      </LineString>
    </Placemark>'''

        kml_footer = '''
  </Document>
</kml>'''

        return kml_header + start_marker + end_marker + track_line + kml_footer

    def _clear_all_plots(self):
        """Clear all plots in all plot panels."""
        self.channel_panel.deselect_all()
        self.plot_panel.clear_plots()
        self.gps_plot_panel.clear_plot()
        self.gps_3d_plot_panel.clear_plot()
        self.gps_2d_map_panel.clear()

    def _restore_last_file(self):
        """Restore the last opened file on application startup."""
        try:
            last_file = self.file_panel.get_last_opened_file()
            if last_file:
                # Load the file automatically
                self._load_file(last_file)
        except Exception:
            # If restore fails, just continue without loading
            pass

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About RC Log Viewer",
            "<h3>RC Log Viewer</h3>"
            "<p>Version 1.1.0</p>"
            "<p>A tool for analyzing FrSky Ethos and Ardupilot log files.</p>"
            "<p>Built with PySide6, NumPy, Pandas, and Matplotlib.</p>"
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle the close event for the main window."""

        # Clean up GPS map panel first (WebEngine needs special handling)
        try:
            if hasattr(self, 'gps_2d_map_panel') and self.gps_2d_map_panel:
                self.gps_2d_map_panel.cleanup()
        except Exception:
            pass

        # Clean up data panel (no longer has background threads)
        try:
            if hasattr(self, 'data_panel') and self.data_panel:
                self.data_panel.cleanup()
        except Exception:
            pass

        # Clean up any child threads that might exist
        try:
            child_threads = self.findChildren(QThread)
            for thread in child_threads:
                if thread and thread.isRunning():
                    thread.requestInterruption()
                    if not thread.wait(300):
                        thread.terminate()
                        thread.wait(100)
        except Exception:
            pass  # Ignore cleanup errors

        # Accept the close event and call parent
        event.accept()
        super().closeEvent(event)

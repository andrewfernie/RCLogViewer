"""
Copyright Andrew Fernie, 2025

Analysis Panel for the RC Log Viewer.
Provides statistical analysis and insights from log data.
"""
from typing import Optional
import os
import traceback
import numpy as np
import pandas as pd


from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QTextEdit,
    QComboBox,
    QPushButton,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget
)
from PySide6.QtCore import Signal


class AnalysisPanel(QWidget):
    """Analysis panel for log data analysis and statistics.

    This widget provides a multi-tabbed interface for analyzing RC flight log data,
    offering statistical insights, flight performance metrics, and channel-specific
    analysis. It automatically processes log data to extract meaningful information
    for flight analysis and troubleshooting.

    Features:
        - General Statistics: File info, duration, sample rates, channel statistics
        - Flight Analysis: GPS tracking, speed, altitude, distance calculations
        - Channel Analysis: Individual channel behavior, statistics, and trends
        - Export functionality for analysis results
        - Real-time analysis updates when new data is loaded
        - Error handling and validation for data integrity

    Tabs:
        1. Statistics: General log file information and channel statistics table
        2. Flight Analysis: GPS-based flight metrics and control surface analysis
        3. Channel Analysis: Detailed analysis of individual data channels

    """

    # Signal emitted when analysis is updated
    analysis_updated = Signal(dict)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_log = None
        self.analysis_results = {}

        self.file_name_label = QLabel()
        self.duration_label = QLabel()
        self.samples_label = QLabel()
        self.channels_label = QLabel()
        self.sample_rate_label = QLabel()
        self.file_size_label = QLabel()

        self.stats_table = QTableWidget()
        self.gps_distance_label = QLabel()
        self.gps_max_speed_label = QLabel()
        self.gps_avg_speed_label = QLabel()
        self.gps_max_altitude_label = QLabel()
        self.gps_altitude_gain_label = QLabel()
        self.gps_home_distance_label = QLabel()
        self.control_analysis_text = QTextEdit()
        self.channel_analysis_text = QTextEdit()
        self.channel_combo = QComboBox()
        self.refresh_button = QPushButton()
        self.export_button = QPushButton()

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # Create tab widget for different analysis categories
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Statistics tab
        self._create_statistics_tab()

        # Flight analysis tab
        self._create_flight_analysis_tab()

        # Channel analysis tab
        self._create_channel_analysis_tab()

        # Control buttons
        self._create_control_buttons(layout)

    def _create_statistics_tab(self) -> None:
        """Create the general statistics tab."""
        stats_widget = QWidget()
        layout = QVBoxLayout(stats_widget)

        # Summary information
        summary_group = QGroupBox("Log Summary")
        summary_layout = QGridLayout(summary_group)

        # Create labels for summary info
        self.file_name_label = QLabel("File: --")
        self.duration_label = QLabel("Duration: --")
        self.samples_label = QLabel("Samples: --")
        self.channels_label = QLabel("Channels: --")
        self.sample_rate_label = QLabel("Avg Sample Rate: --")
        self.file_size_label = QLabel("File Size: --")

        summary_layout.addWidget(QLabel("File:"), 0, 0)
        summary_layout.addWidget(self.file_name_label, 0, 1)
        summary_layout.addWidget(QLabel("Duration:"), 1, 0)
        summary_layout.addWidget(self.duration_label, 1, 1)
        summary_layout.addWidget(QLabel("Samples:"), 2, 0)
        summary_layout.addWidget(self.samples_label, 2, 1)
        summary_layout.addWidget(QLabel("Channels:"), 3, 0)
        summary_layout.addWidget(self.channels_label, 3, 1)
        summary_layout.addWidget(QLabel("Sample Rate:"), 4, 0)
        summary_layout.addWidget(self.sample_rate_label, 4, 1)
        summary_layout.addWidget(QLabel("File Size:"), 5, 0)
        summary_layout.addWidget(self.file_size_label, 5, 1)

        layout.addWidget(summary_group)

        # Channel statistics table
        stats_group = QGroupBox("Channel Statistics")
        stats_layout = QVBoxLayout(stats_group)

        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(6)
        self.stats_table.setHorizontalHeaderLabels(["Channel", "Min", "Max", "Mean",
                                                    "Std Dev", "Range"])
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        stats_layout.addWidget(self.stats_table)

        layout.addWidget(stats_group)

        self.tab_widget.addTab(stats_widget, "Statistics")

    def _create_flight_analysis_tab(self) -> None:
        """Create the flight-specific analysis tab."""
        flight_widget = QWidget()
        layout = QVBoxLayout(flight_widget)

        # GPS Analysis
        gps_group = QGroupBox("GPS Analysis")
        gps_layout = QGridLayout(gps_group)

        self.gps_distance_label = QLabel("Total Distance: --")
        self.gps_max_speed_label = QLabel("Max Speed: --")
        self.gps_avg_speed_label = QLabel("Avg Speed: --")
        self.gps_max_altitude_label = QLabel("Max Altitude: --")
        self.gps_altitude_gain_label = QLabel("Altitude Gain: --")
        self.gps_home_distance_label = QLabel("Max Distance from Home: --")

        gps_layout.addWidget(QLabel("Total Distance:"), 0, 0)
        gps_layout.addWidget(self.gps_distance_label, 0, 1)
        gps_layout.addWidget(QLabel("Max Speed:"), 1, 0)
        gps_layout.addWidget(self.gps_max_speed_label, 1, 1)
        gps_layout.addWidget(QLabel("Avg Speed:"), 2, 0)
        gps_layout.addWidget(self.gps_avg_speed_label, 2, 1)
        gps_layout.addWidget(QLabel("Max Altitude:"), 3, 0)
        gps_layout.addWidget(self.gps_max_altitude_label, 3, 1)
        gps_layout.addWidget(QLabel("Altitude Gain:"), 4, 0)
        gps_layout.addWidget(self.gps_altitude_gain_label, 4, 1)
        gps_layout.addWidget(QLabel("Max Distance from Home:"), 5, 0)
        gps_layout.addWidget(self.gps_home_distance_label, 5, 1)

        layout.addWidget(gps_group)

        # Control Analysis
        control_group = QGroupBox("Control Analysis")
        control_layout = QVBoxLayout(control_group)

        self.control_analysis_text = QTextEdit()
        self.control_analysis_text.setReadOnly(True)
        self.control_analysis_text.setMaximumHeight(200)
        control_layout.addWidget(self.control_analysis_text)

        layout.addWidget(control_group)

        layout.addStretch()
        self.tab_widget.addTab(flight_widget, "Flight Analysis")

    def _create_channel_analysis_tab(self) -> None:
        """Create the channel-specific analysis tab."""
        channel_widget = QWidget()
        layout = QVBoxLayout(channel_widget)

        # Channel selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Analyze Channel:"))

        self.channel_combo = QComboBox()
        self.channel_combo.currentTextChanged.connect(self._analyze_selected_channel)
        selector_layout.addWidget(self.channel_combo)

        selector_layout.addStretch()
        layout.addLayout(selector_layout)

        # Channel analysis results
        self.channel_analysis_text = QTextEdit()
        self.channel_analysis_text.setReadOnly(True)
        layout.addWidget(self.channel_analysis_text)

        self.tab_widget.addTab(channel_widget, "Channel Analysis")

    def _create_control_buttons(self, parent_layout: QVBoxLayout) -> None:
        """Create control buttons."""
        button_layout = QHBoxLayout()

        self.refresh_button = QPushButton("Refresh Analysis")
        self.refresh_button.clicked.connect(self.refresh_analysis)
        button_layout.addWidget(self.refresh_button)

        self.export_button = QPushButton("Export Analysis")
        self.export_button.clicked.connect(self._export_analysis)
        button_layout.addWidget(self.export_button)

        button_layout.addStretch()
        parent_layout.addLayout(button_layout)

    def update_analysis(self, log_data) -> None:
        """Update analysis with new log data."""
        self.current_log = log_data

        if log_data is None:
            self._clear_analysis()
            return

        try:
            # Update general statistics
            self._update_general_stats()

            # Update channel statistics
            self._update_channel_stats()

            # Update flight analysis
            self._update_flight_analysis()

            # Update channel selector
            self._update_channel_selector()

            # Emit signal
            self.analysis_updated.emit(self.analysis_results)

        except Exception as e:
            print(f"Analysis Panel - Error: {str(e)}")
            traceback.print_exc()
            self._show_error(f"Analysis failed: {str(e)}")

    def _update_general_stats(self) -> None:
        """Update general statistics."""

        if not self.current_log:
            print("No current_log")
            return

        if not hasattr(self.current_log, 'processed_data'):
            print("No processed_data attribute")
            return

        if self.current_log.processed_data is None:
            print("processed_data is None")
            return

        if not hasattr(self.current_log, 'metadata'):
            print("No metadata attribute")
            return

        metadata = self.current_log.metadata

        # File name - get from current_log.file_path instead of metadata
        if hasattr(self.current_log, 'file_path') and self.current_log.file_path:
            file_name = os.path.basename(str(self.current_log.file_path))
            self.file_name_label.setText(file_name)
        else:
            self.file_name_label.setText("--")

        # Basic information
        duration = metadata.get('duration', 0)
        samples = metadata.get('num_samples', 0)
        channels = metadata.get('num_channels', 0)

        self.duration_label.setText(f"Duration: {duration:.2f}s "
                                    f"({duration/60:.0f}:{duration%60:02.0f})")
        self.samples_label.setText(f"{samples:,}")
        self.channels_label.setText(f"{channels}")

        if duration > 0:
            sample_rate = samples / duration
            self.sample_rate_label.setText(f"{sample_rate:.1f} Hz")
        else:
            self.sample_rate_label.setText("--")

        # File size (if available)
        if hasattr(self.current_log, 'file_path') and self.current_log.file_path:
            try:
                size_bytes = os.path.getsize(str(self.current_log.file_path))
                if size_bytes < 1024:
                    size_str = f"{size_bytes} B"
                elif size_bytes < 1024**2:
                    size_str = f"{size_bytes/1024:.1f} KB"
                else:
                    size_str = f"{size_bytes/(1024**2):.1f} MB"
                self.file_size_label.setText(size_str)
            except:
                self.file_size_label.setText("--")
        else:
            self.file_size_label.setText("--")

    def _update_channel_stats(self) -> None:
        """Update channel statistics table."""
        if (not self.current_log or
            not hasattr(self.current_log, 'processed_data') or
            self.current_log.processed_data is None or
            self.current_log.processed_data.empty):
            self.stats_table.setRowCount(0)
            return

        df = self.current_log.processed_data
        numeric_columns = df.select_dtypes(include=[np.number]).columns

        self.stats_table.setRowCount(len(numeric_columns))

        for i, column in enumerate(numeric_columns):
            if column.lower() == 'time':  # Skip time column for statistics
                continue

            try:
                data = df[column].dropna()
                if len(data) == 0:
                    continue

                min_val = data.min()
                max_val = data.max()
                mean_val = data.mean()
                std_val = data.std()
                range_val = max_val - min_val

                self.stats_table.setItem(i, 0, QTableWidgetItem(column))
                self.stats_table.setItem(i, 1, QTableWidgetItem(f"{min_val:.3f}"))
                self.stats_table.setItem(i, 2, QTableWidgetItem(f"{max_val:.3f}"))
                self.stats_table.setItem(i, 3, QTableWidgetItem(f"{mean_val:.3f}"))
                self.stats_table.setItem(i, 4, QTableWidgetItem(f"{std_val:.3f}"))
                self.stats_table.setItem(i, 5, QTableWidgetItem(f"{range_val:.3f}"))

            except Exception:
                continue

        self.stats_table.resizeColumnsToContents()

    def _update_flight_analysis(self) -> None:
        """Update flight-specific analysis."""
        if (not self.current_log or
            not hasattr(self.current_log, 'processed_data') or
            self.current_log.processed_data is None or
            self.current_log.processed_data.empty):
            self._clear_flight_analysis()
            return

        df = self.current_log.processed_data

        # GPS Analysis
        self._analyze_gps_data(df)

        # Control Analysis
        self._analyze_control_data(df)

    def _analyze_gps_data(self, df: pd.DataFrame) -> None:
        """Analyze GPS-related data."""
        # Look for GPS columns
        lat_col = None
        lon_col = None
        alt_col = None

        for col in df.columns:
            col_lower = col.lower()
            if 'latitude' in col_lower or col_lower.endswith('lat'):
                lat_col = col
            elif 'longitude' in col_lower or col_lower.endswith('lon') or col_lower.endswith('lng'):
                lon_col = col
            elif 'alt' in col_lower and 'gps' in col_lower:
                alt_col = col

        if lat_col and lon_col:
            try:
                # Convert to numeric and drop NaN values
                lats = pd.to_numeric(df[lat_col], errors='coerce').dropna()
                lons = pd.to_numeric(df[lon_col], errors='coerce').dropna()

                if len(lats) > 1 and len(lons) > 1:
                    # Ensure we have the same number of lat/lon points
                    min_len = min(len(lats), len(lons))
                    lats = lats.iloc[:min_len]
                    lons = lons.iloc[:min_len]

                    # Calculate distances and speeds
                    distances = self._calculate_distances(lats.values, lons.values)
                    total_distance = np.sum(distances)

                    # Calculate speeds (assuming time column exists)
                    if 'Time' in df.columns or 'time' in df.columns:
                        time_col = 'Time' if 'Time' in df.columns else 'time'
                        # Convert time to numeric and drop NaN values
                        times = pd.to_numeric(df[time_col], errors='coerce').dropna()
                        if len(times) > 1:
                            dt = np.diff(times)
                            speeds = distances[1:] / dt[:len(distances)-1]  # m/s
                            speeds = speeds * 3.6  # Convert to km/h
                            # Filter out invalid speeds
                            valid_speeds = speeds[(speeds > 0) & (speeds < 1000)]
                            if len(valid_speeds) > 0:
                                max_speed = np.max(valid_speeds)
                                avg_speed = np.mean(valid_speeds)

                                self.gps_max_speed_label.setText(f"{max_speed:.1f} km/h")
                                self.gps_avg_speed_label.setText(f"{avg_speed:.1f} km/h")

                    self.gps_distance_label.setText(f"{total_distance:.1f} m")

                    # Home distance (distance from first point)
                    if len(lats) > 0 and len(lons) > 0:
                        home_distances = self._calculate_distances(
                            np.full_like(lats, lats.iloc[0]),
                            np.full_like(lons, lons.iloc[0]),
                            lats.values,
                            lons.values
                        )
                        max_home_distance = np.max(home_distances)
                        self.gps_home_distance_label.setText(f"{max_home_distance:.1f} m")

            except Exception as e:
                print(f"GPS analysis error: {e}")

        # Altitude analysis
        if alt_col:
            try:
                # Convert to numeric and drop NaN values
                alts = pd.to_numeric(df[alt_col], errors='coerce').dropna()
                if len(alts) > 0:
                    max_alt = alts.max()
                    min_alt = alts.min()
                    alt_gain = max_alt - min_alt

                    self.gps_max_altitude_label.setText(f"{max_alt:.1f} m")
                    self.gps_altitude_gain_label.setText(f"{alt_gain:.1f} m")
            except Exception:
                pass

    def _calculate_distances(self, lat1, lon1, lat2=None, lon2=None):
        """Calculate distances between GPS coordinates using Haversine formula."""
        if lat2 is None:
            lat2 = lat1[1:]
            lat1 = lat1[:-1]
        if lon2 is None:
            lon2 = lon1[1:]
            lon1 = lon1[:-1]

        # Convert to radians
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        r = 6371000  # Earth's radius in meters

        return c * r

    def _analyze_control_data(self, df: pd.DataFrame) -> None:
        """Analyze control input data."""
        control_analysis = []

        # Look for common control channels
        control_channels = []
        for col in df.columns:
            col_lower = col.lower()
            if any(term in col_lower for term in ['rudder', 'aileron', 'elevator', 'throttle',
                                                  'stick', 'ch']):
                control_channels.append(col)

        if control_channels:
            control_analysis.append("Control Channel Analysis:")
            control_analysis.append("=" * 30)

            for channel in control_channels[:8]:  # Limit to first 8 channels
                try:
                    data = df[channel].dropna()
                    if len(data) > 0:
                        range_val = data.max() - data.min()
                        activity = np.std(data) / range_val if range_val > 0 else 0

                        control_analysis.append(f"\n{channel}:")
                        control_analysis.append(f"  Range: {data.min():.1f} to {data.max():.1f}")
                        control_analysis.append(f"  Activity: {'High' if activity > 0.3 else'Medium' if activity > 0.1 else 'Low'}")

                except Exception:
                    continue
        else:
            control_analysis.append("No control channels detected.")

        self.control_analysis_text.setPlainText("\n".join(control_analysis))

    def _update_channel_selector(self) -> None:
        """Update the channel selector combo box."""
        self.channel_combo.clear()

        if (self.current_log and
            hasattr(self.current_log, 'processed_data') and
            self.current_log.processed_data is not None and
            not self.current_log.processed_data.empty):
            channels = [col for col in self.current_log.processed_data.columns
                       if col.lower() != 'time']
            self.channel_combo.addItems(channels)

    def _analyze_selected_channel(self, channel_name: str) -> None:
        """Analyze the selected channel."""
        if (not channel_name or
            not self.current_log or
            not hasattr(self.current_log, 'processed_data') or
            self.current_log.processed_data is None or
            self.current_log.processed_data.empty):
            self.channel_analysis_text.clear()
            return

        try:
            df = self.current_log.processed_data
            if channel_name not in df.columns:
                return

            data = df[channel_name].dropna()
            if len(data) == 0:
                self.channel_analysis_text.setPlainText("No valid data in selected channel.")
                return

            analysis = []
            analysis.append(f"Channel: {channel_name}")
            analysis.append("=" * (len(channel_name) + 9))
            analysis.append("\nBasic Statistics:")
            analysis.append(f"  Count: {len(data):,}")
            analysis.append(f"  Min: {data.min():.4f}")
            analysis.append(f"  Max: {data.max():.4f}")
            analysis.append(f"  Mean: {data.mean():.4f}")
            analysis.append(f"  Median: {data.median():.4f}")
            analysis.append(f"  Std Dev: {data.std():.4f}")
            analysis.append(f"  Range: {data.max() - data.min():.4f}")

            # Percentiles
            analysis.append("\nPercentiles:")
            for p in [25, 50, 75, 90, 95, 99]:
                analysis.append(f"  {p}th: {np.percentile(data, p):.4f}")

            # Data quality
            total_samples = len(df)
            missing_samples = total_samples - len(data)
            analysis.append("\nData Quality:")
            analysis.append("  Valid samples: {len(data):,} "
                            f"({len(data)/total_samples*100:.1f}%)")
            analysis.append(f"  Missing samples: {missing_samples:,} "
                            f"({missing_samples/total_samples*100:.1f}%)")

            # Activity analysis
            if len(data) > 1:
                changes = np.abs(np.diff(data))
                avg_change = np.mean(changes)
                max_change = np.max(changes)
                analysis.append("\nActivity Analysis:")
                analysis.append(f"  Average change: {avg_change:.4f}")
                analysis.append(f"  Maximum change: {max_change:.4f}")
                if avg_change < data.std() * 0.1:
                    analysis.append("  Stability: High")
                elif avg_change < data.std() * 0.5:
                    analysis.append("  Stability: Medium")
                else:
                    analysis.append("  Stability: Low")

            self.channel_analysis_text.setPlainText("\n".join(analysis))

        except Exception as e:
            self.channel_analysis_text.setPlainText(f"Analysis failed: {str(e)}")

    def _clear_analysis(self) -> None:
        """Clear all analysis displays."""
        self.duration_label.setText("--")
        self.samples_label.setText("--")
        self.channels_label.setText("--")
        self.sample_rate_label.setText("--")
        self.file_size_label.setText("--")

        self.stats_table.setRowCount(0)

        self._clear_flight_analysis()

        self.channel_combo.clear()
        self.channel_analysis_text.clear()

    def _clear_flight_analysis(self) -> None:
        """Clear flight analysis displays."""
        self.gps_distance_label.setText("--")
        self.gps_max_speed_label.setText("--")
        self.gps_avg_speed_label.setText("--")
        self.gps_max_altitude_label.setText("--")
        self.gps_altitude_gain_label.setText("--")
        self.gps_home_distance_label.setText("--")

        self.control_analysis_text.clear()

    def refresh_analysis(self) -> None:
        """Refresh the current analysis."""
        if self.current_log:
            self.update_analysis(self.current_log)

    def _export_analysis(self) -> None:
        """Export analysis results to text file."""
        # This would open a file dialog and save analysis results
        # Implementation would depend on requirements
        pass

    def _show_error(self, message: str) -> None:
        """Show error message."""
        self.channel_analysis_text.setPlainText(f"Error: {message}")

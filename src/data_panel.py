"""
Copyright Andrew Fernie, 2025

Data Panel for the RC Log Viewer.

This module provides the DataPanel widget, a tabular data viewer
with filtering, search, and pagination capabilities. It's designed
for efficient viewing and analysis of large RC flight log datasets.

Key Components:
    DataPanel: Main widget class for tabular data viewing and management

Features:
    - Paginated data display for large datasets
    - Real-time search across all columns
    - Column-specific filtering with numeric/text differentiation
    - Customizable rows per page
    - Data export functionality to CSV format
    - Selection tracking with signal emission
    - Responsive UI with progress indicators
    - Memory-efficient data handling

Dependencies:
    - PySide6.QtWidgets: UI components for table display and controls
    - PySide6.QtCore: Signals, timers, and core Qt functionality
    - PySide6.QtGui: Font and visual styling support
    - pandas: Data manipulation and filtering operations
    - numpy: Numerical operations and data validation
    - typing: Type hints for code documentation

Primary Use Case:
    RC flight log analysis applications where users need to view, search,
    and analyze tabular datasets.

Integration Points:
    - Receives log data from LogProcessor components
    - Emits selection events to other analysis components
    - Coordinates with main application for data state management
    - Provides export functionality for filtered datasets
"""
from typing import Optional, List
import pandas as pd
import numpy as np

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QSpinBox,
    QCheckBox,
    QProgressBar,
    QMessageBox,
    QApplication
)
from PySide6.QtCore import Signal, QTimer
from PySide6.QtGui import QFont


class DataPanel(QWidget):
    """Tabular data viewer with filtering and search capabilities.

    This widget provides an interface for viewing and analyzing datasets in tabular
    format. It features pagination for memory efficiency, real-time search capabilities,
    column-specific filtering, and data export functionality.



    """

    # Signal emitted when data selection changes
    data_selected = Signal(dict)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_log = None
        self.filtered_data = None
        self.current_page = 0
        self.rows_per_page = 1000
        self.total_rows = 0
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._apply_search)

        self.search_box = None
        self.column_combo = None
        self.rows_spinbox = None
        self.numeric_only_checkbox = None
        self.refresh_button = None
        self.export_button = None
        self.progress_bar = None
        self.data_table = None

        self.status_label = None
        self.prev_button = None
        self.prev_button = None
        self.page_label = None
        self.page_spinbox = None
        self.next_button = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # Control panel
        self._create_control_panel(layout)

        # Data table
        self._create_data_table(layout)

        # Status and pagination
        self._create_status_panel(layout)

    def _create_control_panel(self, parent_layout: QVBoxLayout) -> None:
        """Create the control panel with filters and search."""
        control_group = QGroupBox("Data Controls")
        control_layout = QGridLayout(control_group)

        # Search box
        control_layout.addWidget(QLabel("Search:"), 0, 0)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search in all columns...")
        self.search_box.textChanged.connect(self._on_search_changed)
        control_layout.addWidget(self.search_box, 0, 1, 1, 2)

        # Column filter
        control_layout.addWidget(QLabel("Filter Column:"), 1, 0)
        self.column_combo = QComboBox()
        self.column_combo.addItem("All Columns")
        self.column_combo.currentTextChanged.connect(self._on_filter_changed)
        control_layout.addWidget(self.column_combo, 1, 1)

        # Rows per page
        control_layout.addWidget(QLabel("Rows per page:"), 1, 2)
        self.rows_spinbox = QSpinBox()
        self.rows_spinbox.setMinimum(100)
        self.rows_spinbox.setMaximum(10000)
        self.rows_spinbox.setValue(1000)
        self.rows_spinbox.setSingleStep(100)
        self.rows_spinbox.valueChanged.connect(self._on_rows_per_page_changed)
        control_layout.addWidget(self.rows_spinbox, 1, 3)

        # Show/hide columns
        control_layout.addWidget(QLabel("Show numeric only:"), 2, 0)
        self.numeric_only_checkbox = QCheckBox()
        self.numeric_only_checkbox.stateChanged.connect(self._on_numeric_filter_changed)
        control_layout.addWidget(self.numeric_only_checkbox, 2, 1)

        # Refresh button
        self.refresh_button = QPushButton("Refresh Data")
        self.refresh_button.clicked.connect(self.refresh_data)
        control_layout.addWidget(self.refresh_button, 2, 2)

        # Export button
        self.export_button = QPushButton("Export Visible Data")
        self.export_button.clicked.connect(self._export_data)
        control_layout.addWidget(self.export_button, 2, 3)

        parent_layout.addWidget(control_group)

    def _create_data_table(self, parent_layout: QVBoxLayout) -> None:
        """Create the main data table."""
        table_group = QGroupBox("Log Data")
        table_layout = QVBoxLayout(table_group)

        # Progress bar for loading
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        table_layout.addWidget(self.progress_bar)

        # Data table
        self.data_table = QTableWidget()
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.data_table.setSortingEnabled(True)

        # Set font for better readability
        font = QFont("Consolas", 9)
        self.data_table.setFont(font)

        # Connect selection change
        self.data_table.itemSelectionChanged.connect(self._on_selection_changed)

        table_layout.addWidget(self.data_table)
        parent_layout.addWidget(table_group)

    def _create_status_panel(self, parent_layout: QVBoxLayout) -> None:
        """Create status and pagination panel."""
        status_layout = QHBoxLayout()

        # Status label
        self.status_label = QLabel("No data loaded")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        # Pagination controls
        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self._prev_page)
        self.prev_button.setEnabled(False)
        status_layout.addWidget(self.prev_button)

        self.page_label = QLabel("Page 1 of 1")
        status_layout.addWidget(self.page_label)

        # Page number spinbox (new control)
        self.page_spinbox = QSpinBox()
        self.page_spinbox.setMinimum(1)
        self.page_spinbox.setMaximum(1)
        self.page_spinbox.setValue(1)
        self.page_spinbox.setEnabled(False)
        self.page_spinbox.valueChanged.connect(self._on_page_spinbox_changed)
        status_layout.addWidget(QLabel("Go to page:"))
        status_layout.addWidget(self.page_spinbox)

        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self._next_page)
        self.next_button.setEnabled(False)
        status_layout.addWidget(self.next_button)

        parent_layout.addLayout(status_layout)

    def update_data(self, log_data) -> None:
        """Update the data panel with new log data."""
        self.current_log = log_data

        if log_data is None:
            self._clear_data()
            return

        # Check if log data has processed_data
        if (not hasattr(log_data, 'processed_data') or
            log_data.processed_data is None or
            log_data.processed_data.empty):
            self._clear_data()
            self.status_label.setText("No processed data available")
            return

        try:
            self.filtered_data = log_data.processed_data.copy()
            self.total_rows = len(self.filtered_data)
            self.current_page = 0

            # Update column filter
            self._update_column_filter()

            # Load first page
            self._load_current_page()

            # Update status
            self._update_status()

        except Exception as e:
            self._show_error(f"Error loading data: {str(e)}")

    def _clear_data(self) -> None:
        """Clear all data from the table."""
        self.data_table.clear()
        self.data_table.setRowCount(0)
        self.data_table.setColumnCount(0)
        self.status_label.setText("No data loaded")
        self.page_label.setText("Page 1 of 1")
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self.column_combo.clear()
        self.column_combo.addItem("All Columns")

    def _update_column_filter(self) -> None:
        """Update the column filter combo box."""
        current_length = self.column_combo.count()
        if current_length > 0:
            self.column_combo.clear()

        self.column_combo.addItem("All Columns")

        if self.filtered_data is not None:
            columns = list(self.filtered_data.columns)
            self.column_combo.addItems(columns)

    def _load_current_page(self) -> None:
        """Load the current page of data synchronously."""
        if self.filtered_data is None or self.filtered_data.empty:
            return

        try:
            # Show progress bar
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            QApplication.processEvents()  # Allow UI to update

            # Calculate start and end rows
            start_row = self.current_page * self.rows_per_page
            end_row = min(start_row + self.rows_per_page, len(self.filtered_data))

            # Get subset of data
            subset = self.filtered_data.iloc[start_row:end_row]

            # Prepare headers and data
            headers = list(subset.columns)
            rows = []

            total_rows = len(subset)
            for i, (_, row) in enumerate(subset.iterrows()):
                # Convert all values to strings for display
                row_data = []
                for value in row:
                    if pd.isna(value):
                        row_data.append("")
                    elif isinstance(value, float):
                        row_data.append(f"{value:.6f}")
                    else:
                        row_data.append(str(value))

                rows.append(row_data)

                # Update progress every 100 rows and process events
                if i % 100 == 0:
                    progress = int((i / total_rows) * 100)
                    self.progress_bar.setValue(progress)
                    QApplication.processEvents()

            # Final progress update
            self.progress_bar.setValue(100)
            QApplication.processEvents()

            # Load data into table
            self._load_data_to_table(rows, headers)

        except Exception as e:
            self._show_error(f"Error loading data: {str(e)}")
        finally:
            # Hide progress bar
            self.progress_bar.setVisible(False)

    def _load_data_to_table(self, rows: List[List[str]], headers: List[str]) -> None:
        """Load data into the table widget."""
        # Set up table
        self.data_table.setRowCount(len(rows))
        self.data_table.setColumnCount(len(headers))
        self.data_table.setHorizontalHeaderLabels(headers)

        # Populate table
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                item = QTableWidgetItem(value)
                self.data_table.setItem(i, j, item)

        # Resize columns to content
        self.data_table.resizeColumnsToContents()

        # Update status
        self._update_status()

    def _on_search_changed(self) -> None:
        """Handle search text change with debouncing."""
        self.search_timer.stop()
        self.search_timer.start(500)  # 500ms delay

    def _apply_search(self) -> None:
        """Apply search filter to data."""
        if self.current_log is None or self.current_log.processed_data is None:
            return

        search_text = self.search_box.text().strip().lower()

        if not search_text:
            # No search - show all data
            self.filtered_data = self.current_log.processed_data.copy()
        else:
            # Apply search filter
            mask = pd.Series([False] * len(self.current_log.processed_data))

            for column in self.current_log.processed_data.columns:
                # Convert column to string and search
                col_str = self.current_log.processed_data[column].astype(str).str.lower()
                mask = mask | col_str.str.contains(search_text, na=False)

            self.filtered_data = self.current_log.processed_data[mask].copy()

        self.total_rows = len(self.filtered_data)
        self.current_page = 0
        self._load_current_page()

    def _on_filter_changed(self) -> None:
        """Handle column filter change."""
        self._apply_column_filter()

    def _apply_column_filter(self) -> None:
        """Apply column filter."""
        if self.current_log is None or self.current_log.processed_data is None:
            return

        selected_column = self.column_combo.currentText()

        if selected_column == "All Columns" or not selected_column:
            self.filtered_data = self.current_log.processed_data.copy()
        else:
            # Validate that the selected column exists
            if selected_column not in self.current_log.processed_data.columns:
                self.filtered_data = self.current_log.processed_data.copy()
                return

            # Show only selected column plus any time column
            columns_to_show = [selected_column]

            # Add time column if it exists and isn't already selected
            time_cols = [col for col in self.current_log.processed_data.columns
                        if 'time' in col.lower() and col != selected_column]
            if time_cols:
                columns_to_show.insert(0, time_cols[0])

            # Filter out any empty strings or invalid columns
            columns_to_show = [col for col in columns_to_show if col and col in
                               self.current_log.processed_data.columns]

            if columns_to_show:
                self.filtered_data = self.current_log.processed_data[columns_to_show].copy()
            else:
                self.filtered_data = self.current_log.processed_data.copy()

        self.total_rows = len(self.filtered_data)
        self.current_page = 0
        self._load_current_page()

    def _on_numeric_filter_changed(self) -> None:
        """Handle numeric only filter change."""
        if self.current_log is None or self.current_log.processed_data is None:
            return

        if self.numeric_only_checkbox.isChecked():
            # Show only numeric columns
            numeric_cols = self.current_log.processed_data.select_dtypes(
                include=[np.number]).columns
            if len(numeric_cols) > 0:
                self.filtered_data = self.current_log.processed_data[numeric_cols].copy()
            else:
                self.filtered_data = pd.DataFrame()  # Empty if no numeric columns
        else:
            # Show all columns
            self.filtered_data = self.current_log.processed_data.copy()

        self.total_rows = len(self.filtered_data)
        self.current_page = 0
        self._update_column_filter()
        self._load_current_page()

    def _on_rows_per_page_changed(self) -> None:
        """Handle rows per page change."""
        self.rows_per_page = self.rows_spinbox.value()
        self.current_page = 0
        self._load_current_page()

    def _prev_page(self) -> None:
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self._load_current_page()

    def _next_page(self) -> None:
        """Go to next page."""
        max_page = (self.total_rows - 1) // self.rows_per_page
        if self.current_page < max_page:
            self.current_page += 1
            self._load_current_page()

    def _on_page_spinbox_changed(self) -> None:
        """Handle page number change from spinbox."""
        page = self.page_spinbox.value() - 1
        max_page = (self.total_rows - 1) // self.rows_per_page
        if 0 <= page <= max_page:
            self.current_page = page
            self._load_current_page()

    def _update_status(self) -> None:
        """Update status and pagination controls."""
        if self.total_rows == 0:
            self.status_label.setText("No data to display")
            self.page_label.setText("Page 1 of 1")
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)
            self.page_spinbox.setEnabled(False)
            self.page_spinbox.setMinimum(1)
            self.page_spinbox.setMaximum(1)
            self.page_spinbox.setValue(1)
            return

        # Calculate pagination info
        start_row = self.current_page * self.rows_per_page + 1
        end_row = min((self.current_page + 1) * self.rows_per_page, self.total_rows)
        max_page = (self.total_rows - 1) // self.rows_per_page + 1
        current_page_display = self.current_page + 1

        # Update labels
        self.status_label.setText(f"Showing rows {start_row:,} to {end_row:,} "
                                  f"of {self.total_rows:,}")
        self.page_label.setText(f"Page {current_page_display} of {max_page}")

        # Update spinbox
        self.page_spinbox.setEnabled(True)
        self.page_spinbox.setMinimum(1)
        self.page_spinbox.setMaximum(max_page)
        self.page_spinbox.setValue(current_page_display)

        # Update button states
        self.prev_button.setEnabled(self.current_page > 0)
        self.next_button.setEnabled(self.current_page < max_page - 1)

    def _on_selection_changed(self) -> None:
        """Handle table selection change."""
        selected_items = self.data_table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            # Get row data
            row_data = {}
            for col in range(self.data_table.columnCount()):
                header = self.data_table.horizontalHeaderItem(col).text()
                item = self.data_table.item(row, col)
                row_data[header] = item.text() if item else ""

            self.data_selected.emit(row_data)

    def refresh_data(self) -> None:
        """Refresh the current data display."""
        if self.current_log:
            self.update_data(self.current_log)

    def _export_data(self) -> None:
        """Export currently visible data to CSV."""
        if self.filtered_data is None or self.filtered_data.empty:
            QMessageBox.information(self, "Export", "No data to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data",
            "exported_data.csv",
            "CSV Files (*.csv);;All Files (*)"
        )

        if file_path:
            try:
                self.filtered_data.to_csv(file_path, index=False)
                QMessageBox.information(self, "Export", "Data exported successfully to "
                                        f"{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export data: {str(e)}")

    def _show_error(self, message: str) -> None:
        """Show error message."""
        QMessageBox.critical(self, "Error", message)
        self.progress_bar.setVisible(False)

    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            # Stop the search timer
            if hasattr(self, 'search_timer') and self.search_timer is not None:
                if self.search_timer.isActive():
                    self.search_timer.stop()
        except (RuntimeError, TypeError, AttributeError):
            # Ignore errors during shutdown
            pass

    def closeEvent(self, event) -> None:
        """Handle widget close event."""
        try:
            self.cleanup()
        except Exception:
            pass  # Ignore any errors during cleanup
        super().closeEvent(event)

    def __del__(self) -> None:
        """Destructor - ensure cleanup."""
        try:
            self.cleanup()
        except Exception:
            pass  # Ignore any errors during cleanup

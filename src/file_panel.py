"""
Copyright Andrew Fernie, 2025

file_panel.py

Provides a QWidget-based panel for selecting, opening, and managing log files.
Features include recent file tracking, file options, and persistent settings.
"""
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QListWidget, QGroupBox, QFileDialog,
                              QCheckBox)
from PySide6.QtCore import Signal, QSettings

class FilePanel(QWidget):
    """
    Panel for file operations and recent files.

    Allows users to select log files, view and open recent files, and configure file loading
    options. Settings are persisted using QSettings.

    Signals:
        file_selected (str): Emitted when a file is selected or opened.
    """

    file_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.recent_files = []
        self.current_file = None
        self.settings = QSettings("RadioControl", "RCLogViewer")

        self._setup_ui()
        self._load_recent_files()

    def _setup_ui(self):
        """
        Set up the user interface for file selection, recent files, and file options.
        """
        layout = QVBoxLayout(self)

        # File selection group
        file_group = QGroupBox("File Selection")
        file_layout = QVBoxLayout(file_group)

        # Open file button
        self.open_button = QPushButton("Open Log File...")
        self.open_button.clicked.connect(self._open_file_dialog)
        file_layout.addWidget(self.open_button)

        # Current file display
        current_layout = QHBoxLayout()
        current_layout.addWidget(QLabel("Current File:"))
        self.current_file_label = QLabel("None")
        self.current_file_label.setWordWrap(True)
        self.current_file_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        current_layout.addWidget(self.current_file_label, 1)
        file_layout.addLayout(current_layout)

        layout.addWidget(file_group)

        # Recent files group
        recent_group = QGroupBox("Recent Files")
        recent_layout = QVBoxLayout(recent_group)

        self.recent_list = QListWidget()
        self.recent_list.itemDoubleClicked.connect(self._load_recent_file)
        recent_layout.addWidget(self.recent_list)

        # Clear recent files button
        clear_button = QPushButton("Clear Recent")
        clear_button.clicked.connect(self._clear_recent_files)
        recent_layout.addWidget(clear_button)

        layout.addWidget(recent_group)


    def _open_file_dialog(self):
        """
        Open a file dialog for the user to select a log file. Updates current file and emits
        file_selected.
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Log File",
            "",
            "Log Files (*.csv *.tlog);;CSV Files (*.csv);;TLog Files (*.tlog);;bin Files (*.bin);;All Files (*)"
        )

        if file_path:
            self._set_current_file(file_path)
            self.file_selected.emit(file_path)

    def _load_recent_file(self, item):
        """
        Load a file from the recent files list when double-clicked. Updates current file and
        emits file_selected.
        """
        file_path = item.text()
        if Path(file_path).exists():
            self._set_current_file(file_path)
            self.file_selected.emit(file_path)
        else:
            # Remove non-existent file from recent list
            self._remove_from_recent(file_path)

    def _set_current_file(self, file_path):
        """
        Set the current file, update the UI, and add to recent files.
        """
        self.current_file = file_path
        file_name = Path(file_path).name
        self.current_file_label.setText(file_name)
        self.current_file_label.setToolTip(file_path)

        # Add to recent files
        self._add_to_recent(file_path)

        # Save current file to settings
        self._save_current_file(file_path)

    def _add_to_recent(self, file_path):
        """
        Add a file to the recent files list, ensuring uniqueness and limiting to 10 entries.
        """
        # Remove if already exists
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)

        # Add to beginning
        self.recent_files.insert(0, file_path)

        # Limit to 10 recent files
        if len(self.recent_files) > 10:
            self.recent_files = self.recent_files[:10]

        self._update_recent_list()
        self._save_recent_files()

    def _remove_from_recent(self, file_path):
        """
        Remove a file from the recent files list.
        """
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
            self._update_recent_list()
            self._save_recent_files()

    def _update_recent_list(self):
        """
        Update the recent files list widget to reflect current recent files.
        """
        self.recent_list.clear()
        for file_path in self.recent_files:
            if Path(file_path).exists():
                self.recent_list.addItem(file_path)

    def _clear_recent_files(self):
        """
        Clear all recent files from the list and settings.
        """
        self.recent_files.clear()
        self.recent_list.clear()
        self._save_recent_files()

    def _load_recent_files(self):
        """
        Load recent files from persistent settings.
        """
        try:
            # Load recent files from QSettings
            recent_files = self.settings.value("recent_files", [])

            # Ensure it's a list (QSettings might return different types)
            if isinstance(recent_files, str):
                recent_files = [recent_files] if recent_files else []
            elif not isinstance(recent_files, list):
                recent_files = []

            # Filter out non-existent files and limit to 10
            self.recent_files = []
            for file_path in recent_files:
                if isinstance(file_path, str) and Path(file_path).exists():
                    self.recent_files.append(file_path)
                if len(self.recent_files) >= 10:
                    break

            self._update_recent_list()

        except Exception:
            # If loading fails, start with empty list
            self.recent_files = []

    def _save_recent_files(self):
        """
        Save the recent files list to persistent settings.
        """
        try:
            # Save recent files to QSettings
            self.settings.setValue("recent_files", self.recent_files)
            self.settings.sync()  # Ensure data is written to disk
        except Exception:
            # If saving fails, just continue (non-critical)
            pass

    def _save_current_file(self, file_path):
        """
        Save the current file path to persistent settings.
        """
        try:
            self.settings.setValue("current_file", file_path)
            self.settings.sync()
        except Exception:
            pass

    def _load_current_file(self):
        """
        Load and restore the last opened file from persistent settings.
        """
        try:
            current_file = self.settings.value("current_file", "")
            if current_file and Path(current_file).exists():
                self.current_file = current_file
                file_name = Path(current_file).name
                self.current_file_label.setText(file_name)
                self.current_file_label.setToolTip(current_file)
                return current_file
        except Exception:
            pass
        return None

    def get_last_opened_file(self):
        """
        Get the last opened file from persistent settings.
        """
        return self._load_current_file()

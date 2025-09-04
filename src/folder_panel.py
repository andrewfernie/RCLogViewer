"""
Copyright Andrew Fernie, 2025

folder_panel.py

Provides a QWidget-based panel for selecting and managing recent folders used for log files.
Features include recent folder tracking and persistent settings.
"""
from pathlib import Path
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QListWidget, QGroupBox)
from PySide6.QtCore import Signal, QSettings


class FolderPanel(QWidget):
    """
    Panel for recent folders used to open log files.

    Allows users to view and open recent folders. Settings are persisted using QSettings.

    Signals:
            folder_selected (str): Emitted when a folder is selected or opened.
    """

    folder_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.recent_folders = []
        self.settings = QSettings("RadioControl", "RCLogViewer")

        self._setup_ui()
        self._load_recent_folders()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Folder selection group
        folder_group = QGroupBox("Recent Folders")
        folder_layout = QVBoxLayout(folder_group)

        # Recent folders list
        self.recent_list = QListWidget()
        self.recent_list.itemDoubleClicked.connect(self._select_recent_folder)
        folder_layout.addWidget(self.recent_list)

        # Clear recent folders button
        clear_button = QPushButton("Clear Recent Folders")
        clear_button.clicked.connect(self._clear_recent_folders)
        folder_layout.addWidget(clear_button)

        layout.addWidget(folder_group)

    def add_folder(self, folder_path):
        """
        Add a folder to the recent folders list, ensuring uniqueness and limiting to 10 entries.
        """
        folder_path = str(folder_path)
        if folder_path in self.recent_folders:
            self.recent_folders.remove(folder_path)
        self.recent_folders.insert(0, folder_path)
        if len(self.recent_folders) > 10:
            self.recent_folders = self.recent_folders[:10]
        self._update_recent_list()
        self._save_recent_folders()

    def _select_recent_folder(self, item):
        folder_path = item.text()
        if Path(folder_path).exists():
            self.folder_selected.emit(folder_path)
        else:
            self._remove_from_recent(folder_path)

    def _remove_from_recent(self, folder_path):
        if folder_path in self.recent_folders:
            self.recent_folders.remove(folder_path)
            self._update_recent_list()
            self._save_recent_folders()

    def _update_recent_list(self):
        self.recent_list.clear()
        for folder_path in self.recent_folders:
            if Path(folder_path).exists():
                self.recent_list.addItem(folder_path)

    def _clear_recent_folders(self):
        self.recent_folders.clear()
        self.recent_list.clear()
        self._save_recent_folders()

    def _load_recent_folders(self):
        try:
            recent_folders = self.settings.value("recent_folders", [])
            if isinstance(recent_folders, str):
                recent_folders = [recent_folders] if recent_folders else []
            elif not isinstance(recent_folders, list):
                recent_folders = []
            self.recent_folders = []
            for folder_path in recent_folders:
                if isinstance(folder_path, str) and Path(folder_path).exists():
                    self.recent_folders.append(folder_path)
                if len(self.recent_folders) >= 10:
                    break
            self._update_recent_list()
        except Exception:
            self.recent_folders = []

    def _save_recent_folders(self):
        try:
            self.settings.setValue("recent_folders", self.recent_folders)
            self.settings.sync()
        except Exception:
            pass

    def get_last_opened_folder(self):
        if self.recent_folders:
            return self.recent_folders[0]
        return None

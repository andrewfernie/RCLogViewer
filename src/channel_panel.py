"""
Copyright Andrew Fernie, 2025

Channel panel for selecting and managing data channels for plotting.

Key Components:
    ChannelPanel: Main widget class for channel selection and management

Dependencies:
    - PySide6.QtWidgets: UI components (QWidget, QListWidget, QLineEdit, etc.)
    - PySide6.QtCore: Signals, Qt constants, and core functionality
    - typing: Type hints for better code documentation and IDE support

Primary Use Case:
    CSV file analysis applications where users need to select specific
    data channels from loaded log files for visualization, analysis, or
    export operations.

Integration Points:
    - Receives channel lists from log processing components
    - Emits selection changes to plotting and analysis components
    - Coordinates with main application window for UI state management
"""

from typing import List, Optional
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QGroupBox,
                               QLineEdit, QTreeWidget, QTreeWidgetItem)
from PySide6.QtCore import Signal, Qt


class ChannelPanel(QWidget):
    """Interactive panel for channel selection and management in log data analysis.

    This widget provides a user-friendly interface for selecting and managing data
    channels from loaded log files. It features real-time filtering, multi-selection
    capabilities, and automatic updates when new log data is loaded. The panel
    automatically excludes system channels like Date, Time, DateTime, and GPS clock
    to focus on actual data channels relevant for analysis.

    Excluded Channels:
        Plotting against time is based on an elapsed time channel created during log
        file processing. There is no need to plot other time or date channels so the
        following system channels are automatically filtered out:
        - "Date": Date information (handled separately)
        - "Time": Time stamps (handled separately)
        - "DateTime": Combined date/time (handled separately)
        - "GPS clock()": GPS timing data (not user-selectable)

    """

    # New signal for real-time selection changes
    channels_selection_changed = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.channels: List[str] = []

        # UI components (initialized in _setup_ui)
        self.search_edit: QLineEdit
        self.channel_tree: QTreeWidget

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # Channel selection group
        selection_group = QGroupBox("Channel Selection")
        selection_layout = QVBoxLayout(selection_group)

        # Search/filter
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Filter:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Type to filter channels...")
        self.search_edit.textChanged.connect(self._filter_channels)
        search_layout.addWidget(self.search_edit)
        selection_layout.addLayout(search_layout)

        # Channel tree (replaces channel_list)
        self.channel_tree = QTreeWidget()
        self.channel_tree.setHeaderHidden(True)
        self.channel_tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.channel_tree.itemChanged.connect(self._on_channel_state_changed)
        selection_layout.addWidget(self.channel_tree)

        # Select/deselect buttons
        select_layout = QHBoxLayout()
        select_all_button = QPushButton("Select All")
        select_all_button.clicked.connect(self._select_all)
        select_layout.addWidget(select_all_button)
        deselect_all_button = QPushButton("Deselect All")
        deselect_all_button.clicked.connect(self.deselect_all)
        select_layout.addWidget(deselect_all_button)
        selection_layout.addLayout(select_layout)

        layout.addWidget(selection_group)


    def update_channels(self, channels: List[str], config_object) -> None:
        """Update the list of available channels."""
        self.channels = channels
        self.config_object = config_object
        self._populate_channel_list()

    def _populate_channel_list(self) -> None:
        """Populate the channel tree widget with grouped branches."""
        self.channel_tree.clear()

        filter_text = self.search_edit.text().lower()
        excluded_channels = {"Date", "Time", "DateTime", "GPS clock()", "ElapsedTime"}
        filtered_channels = [
            ch for ch in self.channels if ch not in excluded_channels]
        if not filtered_channels:
            return

        # The "config_object" argument includes an array "channel_groups" that defines the
        # grouping of channels.
        channel_groups = self.config_object.get("channel_groups", {})


        # Iterate through each channel group defined in the config.
        for group_name in channel_groups:
            group_item = QTreeWidgetItem([group_name])
            group_item.setFlags(group_item.flags() | Qt.ItemIsUserCheckable)
            # For each channel group
            # iterate through all channels looking for a channel name that starts with the
            # channel group followed by a ".". Add checkboxes for these channels to the
            # channel tree.
            for ch in filtered_channels:
                if ch.startswith(f"{group_name}."):
                    child = QTreeWidgetItem([ch])
                    child.setCheckState(0, Qt.Unchecked)
                    group_item.addChild(child)

            if group_item.childCount() > 0:
                self.channel_tree.addTopLevelItem(group_item)

        # If there are any channels whose names do not start with a group name, and which do not
        # start with "TIME.",add them in a group "OTHER". But, we skip the "TIME." channels.
        other_channels = [
            ch for ch in filtered_channels if (not ch.startswith("TIME") and
                                               not any(ch.startswith(f"{group_name}.")
                                                       for group_name in channel_groups))]
        if other_channels:
            other_item = QTreeWidgetItem(["OTHER"])
            other_item.setFlags(other_item.flags() | Qt.ItemIsUserCheckable)
            for ch in other_channels:
                child = QTreeWidgetItem([ch])
                child.setCheckState(0, Qt.Unchecked)
                other_item.addChild(child)
            self.channel_tree.addTopLevelItem(other_item)

    def _filter_channels(self) -> None:
        """Filter channels based on search text."""
        self._populate_channel_list()

    def _on_channel_state_changed(self, _) -> None:
        """Handle channel checkbox state change."""
        selected_channels = self.get_selected_channels()
        self.channels_selection_changed.emit(selected_channels)

    def _select_all(self) -> None:
        """Select all visible channels."""
        def set_all_checked(item):
            for i in range(item.childCount()):
                child = item.child(i)
                child.setCheckState(0, Qt.Checked)
            item.setCheckState(0, Qt.Checked)

        for i in range(self.channel_tree.topLevelItemCount()):
            set_all_checked(self.channel_tree.topLevelItem(i))

        selected_channels = self.get_selected_channels()
        self.channels_selection_changed.emit(selected_channels)

    def deselect_all(self) -> None:
        """Deselect all channels."""
        def set_all_unchecked(item):
            for i in range(item.childCount()):
                child = item.child(i)
                child.setCheckState(0, Qt.Unchecked)
            item.setCheckState(0, Qt.Unchecked)

        for i in range(self.channel_tree.topLevelItemCount()):
            set_all_unchecked(self.channel_tree.topLevelItem(i))

        selected_channels = self.get_selected_channels()
        self.channels_selection_changed.emit(selected_channels)

    def get_selected_channels(self) -> List[str]:
        """Get list of currently selected channels."""
        selected = []

        def collect_checked(item):
            for i in range(item.childCount()):
                child = item.child(i)
                if child.checkState(0) == Qt.Checked:
                    selected.append(child.text(0))
            if item.childCount() == 0 and item.checkState(0) == Qt.Checked:
                selected.append(item.text(0))

        for i in range(self.channel_tree.topLevelItemCount()):
            collect_checked(self.channel_tree.topLevelItem(i))

        return selected

    def clear(self) -> None:
        """Clear all channels."""
        self.channels = []
        self.channel_tree.clear()

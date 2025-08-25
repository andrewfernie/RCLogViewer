#!/usr/bin/env python3
"""
Copyright Andrew Fernie, 2025

RC Log Viewer - Application Entry Point

This module serves as the primary entry point for the RC Log Viewer application which
can be used to view and analyze log files recorded by FrSky radio control
transmitters using the Ethos operating system as well as Ardupilot TLOG data files.
The log files contain telemetry data such as GPS coordinates, battery voltage, current,
and other flight parameters. The specific data columns vary depending on the model setup
and the sensors used.

Technical Architecture:
    Framework: PySide6 (Qt6) for cross-platform GUI functionality
    Data Processing: pandas and numpy for efficient telemetry data handling
    GPS Processing: pyproj for coordinate system transformations
    Visualization: matplotlib for plotting, Folium/Leaflet for interactive maps
    Web Integration: QWebEngineView for interactive map displays using Folium

Application Structure:
    main.py: Application entry point and system configuration
    src/main_window.py: Primary application window and UI orchestration
    src/log_processor.py: Core data processing and analysis engine
    src/*_panel.py: Specialized UI panels for different analysis views
    src/analysis.py: Mathematical analysis utilities and algorithms

System Requirements:
    - Python 3.8+ with PySide6 framework
    - Cross-platform support: Windows, macOS, Linux
    - Network: Optional for map tile downloads in GPS visualization

Integration Notes:
    - Compatible with telemetry data from
        - FrSky Ethos radio systems
        - Ardupilot TLOG files
    - Extensible architecture for additional data source support

Example Usage:
    # Direct execution from command line
    python main.py

Version Information:
    Version: 1.0.0 - Initial release
"""

import sys
from pathlib import Path

# Add src directory to Python path for modular source organization
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from PySide6.QtWidgets import QApplication
from main_window import MainWindow


def main():
    """
    Initialize and launch the RC Log Viewer application.

    This function serves as the primary application entry point, handling all
    aspects of application initialization from Qt framework setup through
    main window creation and event loop management.

    Application Metadata:
        Name: "RC Log Viewer"
            - Used for window titles and system integration
            - Appears in taskbar and application switching interfaces
            - Referenced in system settings and preferences

        Version: 1.0.0"
            - Major version for first release
            - Used for compatibility checking and user feedback
            - Referenced in about dialogs and error reporting

        Organization: "RadioControl"
            - Groups application with related RC analysis tools
            - Used for settings storage and application identification

    Return Codes:
        int: Application exit code (0 for success, 1 for errors)

        0: Successful application execution and normal termination
            - User closed application through normal interface
            - All operations completed successfully
            - Proper resource cleanup performed

        1: Application error requiring early termination
            - Critical initialization failure
            - Unhandled exception during execution
            - System resource limitations preventing operation

    """
    # Initialize Qt application with system integration
    app = QApplication(sys.argv)

    # Configure application metadata for system integration
    app.setApplicationName("RC Log Viewer")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("RadioControl")

    # Apply modern, cross-platform visual style
    app.setStyle("Fusion")

    # Create and display main application window
    window = MainWindow()
    window.show()

    try:
        # Start Qt event loop and process user interactions
        exit_code = app.exec()
    except Exception:
        # Handle any unhandled exceptions gracefully
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    # Execute main function and pass exit code to system
    result = main()
    sys.exit(result)

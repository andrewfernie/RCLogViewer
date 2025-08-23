#!/usr/bin/env python3
"""
Copyright Andrew Fernie, 2025

Setup script for RC Log Viewer PySide6.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_path.exists():
    requirements = requirements_path.read_text().strip().split('\n')
    requirements = [req.strip() for req in requirements if req.strip() and not req.startswith('#')]

setup(
    name="rc-log-viewer-pyside",
    version="1.0.0",
    author="Andrew Fernie",
    author_email="andrewjfernie@gmail.com",
    description="An application for viewing and analyzing RC log files",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/andrewfernie/RCLogViewer",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: GPL V3 License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Visualization",
        "Topic :: System :: Logging",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-qt>=4.0",
            "black>=22.0",
            "flake8>=4.0",
            "mypy>=0.900",
        ],
        "analysis": [
            "scipy>=1.9.0",
            "scikit-learn>=1.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "rc-log-viewer=main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.txt", "*.md"],
    },
)

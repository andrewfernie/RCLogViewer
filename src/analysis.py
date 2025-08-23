"""
Utility functions for data analysis and processing.

This module provides helper methods for data smoothing and statistical analysis.

Functions:
    Data Smoothing:
        smooth_data(): Apply various smoothing algorithms to noisy data
            - Moving average for simple noise reduction
            - Savitzky-Golay filter for preserving features
            - Low-pass filtering for frequency-based smoothing

    Statistical Analysis:
        calculate_statistics(): Comprehensive statistical measures
            - Basic stats: mean, std, min, max, median
            - Distribution stats: quartiles, range, RMS
            - Advanced stats: skewness, kurtosis (with scipy)

Dependencies:
    Required:
        - numpy: Core numerical operations
        - typing: Type hint support
        - scipy: Advanced signal processing and statistics
            - Used for: Savitzky-Golay filter, butter filter, peak detection
            - Fallbacks: Simple alternatives when not available

Usage Examples:
    Basic smoothing:
        smoothed = smooth_data(noisy_data, window_size=10, method='savgol')

    Statistical analysis:
        stats = calculate_statistics(channel_data)
        print(f"Mean: {stats['mean']}, Std: {stats['std']}")

Algorithm Details:
    Smoothing Methods:
        - Moving Average: Simple convolution with uniform kernel
        - Savitzky-Golay: Polynomial fitting for feature preservation
        - Low-pass Filter: Butterworth filter with configurable cutoff

"""
from typing import Dict
import numpy as np
from scipy.signal import savgol_filter

def smooth_data(data: np.ndarray, window_size: int = 5, method: str = 'moving_average'
                ) -> np.ndarray:
    """
    Smooth data using various methods.

    Args:
        data: Input data array
        window_size: Size of smoothing window
        method: Smoothing method ('moving_average', 'savgol', 'lowpass')

    Returns:
        Smoothed data array
    """
    if len(data) < window_size:
        return data

    if method == 'moving_average':
        # Simple moving average
        kernel = np.ones(window_size) / window_size
        return np.convolve(data, kernel, mode='same')

    elif method == 'savgol':
        # Savitzky-Golay filter
        try:
            return savgol_filter(data, window_size, 3)
        except ImportError:
            # Fallback to moving average
            return smooth_data(data, window_size, 'moving_average')

    elif method == 'lowpass':
        # Low-pass filter
        try:
            from scipy.signal import butter, filtfilt
            nyquist = 0.5 * 100  # Assume 100 Hz sample rate
            cutoff = 10  # 10 Hz cutoff
            b, a = butter(4, cutoff / nyquist, btype='low')
            return filtfilt(b, a, data)
        except ImportError:
            # Fallback to moving average
            return smooth_data(data, window_size, 'moving_average')

    else:
        return data


def calculate_statistics(data: np.ndarray) -> Dict[str, float]:
    """
    Calculate comprehensive statistics for a data array.

    Args:
        data: Input data array

    Returns:
        Dictionary of statistics
    """
    clean_data = data[~np.isnan(data)]

    if len(clean_data) == 0:
        return {
            'count': 0,
            'mean': np.nan,
            'std': np.nan,
            'min': np.nan,
            'max': np.nan,
            'median': np.nan,
            'q25': np.nan,
            'q75': np.nan,
            'range': np.nan,
            'rms': np.nan,
            'skewness': np.nan,
            'kurtosis': np.nan
        }

    stats = {
        'count': len(clean_data),
        'mean': float(np.mean(clean_data)),
        'std': float(np.std(clean_data)),
        'min': float(np.min(clean_data)),
        'max': float(np.max(clean_data)),
        'median': float(np.median(clean_data)),
        'q25': float(np.percentile(clean_data, 25)),
        'q75': float(np.percentile(clean_data, 75)),
        'range': float(np.max(clean_data) - np.min(clean_data)),
        'rms': float(np.sqrt(np.mean(clean_data ** 2)))
    }

    # Calculate skewness and kurtosis if scipy is available
    try:
        from scipy.stats import skew, kurtosis
        stats['skewness'] = float(skew(clean_data))
        stats['kurtosis'] = float(kurtosis(clean_data))
    except ImportError:
        stats['skewness'] = np.nan
        stats['kurtosis'] = np.nan

    return stats

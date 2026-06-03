"""Signal processing helpers used by live and offline plots."""

from __future__ import annotations

import numpy as np

try:
    from scipy.signal import butter, filtfilt
except ModuleNotFoundError:
    butter = None
    filtfilt = None


def rms_signal(data: np.ndarray, window_size: int = 50) -> np.ndarray:
    """Return moving RMS values for each channel in a 2D channel x sample array."""
    if data.size == 0:
        return data.copy()

    window_size = max(1, int(window_size))
    kernel = np.ones(window_size, dtype=np.float64) / window_size
    squared = np.square(data)
    return np.sqrt(
        np.apply_along_axis(lambda row: np.convolve(row, kernel, mode="same"), 1, squared)
    )


def bandpass_filter(
    data: np.ndarray,
    sample_rate: float = 1000.0,
    lowcut: float = 20.0,
    highcut: float = 450.0,
    order: int = 4,
) -> np.ndarray:
    """Return a Butterworth band-pass filtered copy of channel x sample data."""
    if data.size == 0:
        return data.copy()

    if butter is None or filtfilt is None:
        return _fallback_filter(data)

    nyquist = sample_rate * 0.5
    low = max(0.001, lowcut / nyquist)
    high = min(0.999, highcut / nyquist)
    if low >= high:
        return data.copy()

    b_coeff, a_coeff = butter(order, [low, high], btype="band")
    min_samples = max(len(a_coeff), len(b_coeff)) * 3
    if data.shape[1] <= min_samples:
        return data.copy()

    return filtfilt(b_coeff, a_coeff, data, axis=1)


def _fallback_filter(data: np.ndarray, window_size: int = 25) -> np.ndarray:
    """Small NumPy-only fallback used when SciPy is not installed yet."""
    if data.shape[1] < window_size:
        return data.copy()

    kernel = np.ones(window_size, dtype=np.float64) / window_size
    baseline = np.apply_along_axis(lambda row: np.convolve(row, kernel, mode="same"), 1, data)
    return data - baseline


def process_signal(data: np.ndarray, mode: str, sample_rate: float = 1000.0) -> np.ndarray:
    """Apply the selected display mode to channel x sample data."""
    normalized_mode = mode.lower()
    if normalized_mode == "rms":
        return rms_signal(data)
    if normalized_mode == "filtered":
        return bandpass_filter(data, sample_rate=sample_rate)
    return data.copy()

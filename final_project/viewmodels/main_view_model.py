"""Main ViewModel for application state, TCP polling, and plot data."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal

try:
    from ..services.TCP_client_service import EMGTCPClient
    from ..services.TCP_server_service import EMGTCPServer
    from ..services.signal_processing import process_signal
except ImportError:
    package_root = Path(__file__).resolve().parents[1]
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    from services.TCP_client_service import EMGTCPClient
    from services.TCP_server_service import EMGTCPServer
    from services.signal_processing import process_signal


class MainViewModel(QObject):
    """Connect GUI actions to TCP data and processed plot-ready buffers.

    The ViewModel is the middle layer of the MVVM structure:
    - the View calls methods such as `connect_to_server()` and `set_channel()`;
    - the services do the low-level socket and signal-processing work;
    - this class stores application state and emits Qt signals for the View.
    """

    # Status text shown at the bottom of the GUI.
    status_changed = Signal(str)

    # Live plot payload:
    #   1. all processed channels for the optional all-channel view
    #   2. the currently selected processed channel for the main live plot
    #   3. current stream time in seconds for the x-axis labels
    live_data_changed = Signal(object, object, float)

    # Processed full recording used by the Matplotlib offline plot.
    offline_data_changed = Signal(object)

    # Button-state signals for client and local server controls.
    connection_changed = Signal(bool)
    server_running_changed = Signal(bool)

    CHANNEL_COUNT = 32

    def __init__(self) -> None:
        super().__init__()
        self.status_text = "Disconnected."
        self.sample_rate = 1000.0
        # Keep ten seconds of live data because the VisPy plot displays a
        # ten-second window. If this buffer is shorter, the plot necessarily
        # leaves part of the canvas empty.
        self.live_window_samples = int(self.sample_rate * 10)
        self.selected_channel = 0
        self.signal_mode = "Original"
        self.recorded_data = np.empty((self.CHANNEL_COUNT, 0), dtype=np.float64)

        # The client receives data from a TCP server. The View never touches
        # this service directly; it only asks the ViewModel to connect.
        self.tcp_client = EMGTCPClient()
        self.tcp_client.status_updated.connect(self._set_status)

        # The local server lets the user start the exercise stream inside this
        # GUI instead of opening a second terminal.
        self.tcp_server = EMGTCPServer()
        self.tcp_server.status_updated.connect(self._set_status)
        self.tcp_server.running_changed.connect(self.server_running_changed)

        # The timer keeps network reading non-blocking. Every timeout drains all
        # currently available socket bytes, appends decoded samples to the
        # recording buffer, and emits fresh plot data.
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(30)
        self.poll_timer.timeout.connect(self._poll_tcp)

    def connect_to_server(self, host: str, port_text: str) -> None:
        """Connect to TCP server and start receiving automatically."""
        port = self._parse_port(port_text)
        if port is None:
            return

        # A new connection starts a new recording. Existing offline data is kept
        # only when the user disconnects from an active stream.
        self.disconnect_from_server(announce=False)
        self.recorded_data = np.empty((self.CHANNEL_COUNT, 0), dtype=np.float64)
        self.tcp_client.host = host.strip() or "localhost"
        self.tcp_client.port = port
        self.tcp_client.connect()

        if self.tcp_client.is_connected:
            self.poll_timer.start()
            self.connection_changed.emit(True)
            self._emit_current_live_data()
        else:
            self.connection_changed.emit(False)

    def start_tcp_server(self, host: str, port_text: str) -> None:
        """Start the local TCP server from the GUI."""
        port = self._parse_port(port_text)
        if port is None:
            return
        self.tcp_server.start(host, port)

    def stop_tcp_server(self) -> None:
        """Stop the local TCP server."""
        self.tcp_server.stop()

    def disconnect_from_server(self, announce: bool = True) -> None:
        """Stop polling and close the socket if needed."""
        self.poll_timer.stop()
        if self.tcp_client.is_connected or self.tcp_client.client_socket is not None:
            self.tcp_client.disconnect()
        elif announce:
            self._set_status("Already disconnected.")
        self.connection_changed.emit(False)
        self.offline_data_changed.emit(self._processed_recording())

    def set_channel(self, channel_number: int) -> None:
        """Update selected channel. The public number is one-based."""
        if 1 <= channel_number <= self.CHANNEL_COUNT:
            # The GUI shows channels as 1..32, while NumPy arrays are indexed
            # as 0..31. Store the zero-based index internally.
            self.selected_channel = channel_number - 1

            # Re-emit immediately so switching channels updates the plot even
            # before the next network packet arrives.
            self._emit_current_live_data()
            self.offline_data_changed.emit(self._processed_recording())
        else:
            self._set_status("Invalid channel. Choose a value from 1 to 32.")

    def set_signal_mode(self, mode: str) -> None:
        """Update processing mode for live and offline displays."""
        if mode not in {"Original", "RMS", "Filtered"}:
            self._set_status("Invalid signal mode.")
            return
        self.signal_mode = mode
        self._emit_current_live_data()
        self.offline_data_changed.emit(self._processed_recording())

    def request_offline_plot(self) -> None:
        """Ask the view to redraw offline data or show a friendly status message."""
        if self.recorded_data.shape[1] == 0:
            self._set_status("No recorded data available for offline plotting.")
            return
        self.offline_data_changed.emit(self._processed_recording())

    def _poll_tcp(self) -> None:
        """Read available TCP data and publish it to the plots."""
        self.tcp_client.receive_data()
        if not self.tcp_client.is_connected:
            self.poll_timer.stop()
            self.connection_changed.emit(False)

        # `get_latest_data()` returns only newly decoded samples and clears the
        # client-side transfer buffer. `recorded_data` is the persistent copy
        # used for live and offline plotting.
        new_data = self.tcp_client.get_latest_data()
        if new_data.shape[1] == 0:
            return

        self.recorded_data = np.concatenate((self.recorded_data, new_data), axis=1)
        self._emit_current_live_data()

    def _emit_current_live_data(self) -> None:
        """Process current buffers and emit the data needed by live views."""
        if self.recorded_data.shape[1] == 0:
            empty = np.empty((self.CHANNEL_COUNT, 0), dtype=np.float64)
            self.live_data_changed.emit(empty, empty, 0.0)
            return

        # Only send the most recent live window to VisPy. The full recording
        # remains in `recorded_data` for offline inspection.
        live_data = self.recorded_data[:, -self.live_window_samples :]
        processed = process_signal(live_data, self.signal_mode, self.sample_rate)
        current_time = self.recorded_data.shape[1] / self.sample_rate
        self.live_data_changed.emit(processed, processed[self.selected_channel], current_time)

    def _processed_recording(self) -> np.ndarray:
        return process_signal(self.recorded_data, self.signal_mode, self.sample_rate)

    def _set_status(self, message: str) -> None:
        self.status_text = message
        self.status_changed.emit(message)

    def _parse_port(self, port_text: str) -> int | None:
        try:
            port = int(port_text)
            if port <= 0 or port > 65535:
                raise ValueError
            return port
        except ValueError:
            self._set_status("Invalid TCP port. Enter a number from 1 to 65535.")
            return None

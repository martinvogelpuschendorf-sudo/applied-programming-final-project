"""Main ViewModel for application state, TCP polling, and plot data."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import QMetaObject, QObject, Qt, QThread, QTimer, Signal, Slot

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


class TCPAcquisitionWorker(QObject):
    """Read TCP packets on a dedicated Qt thread and emit immutable chunks.

    MainViewModel owns this object but moves it to ``_tcp_thread``. The View
    asks MainViewModel to connect/disconnect; MainViewModel forwards those
    requests through ``_tcp_connect_requested`` and ``_tcp_disconnect_requested``.
    Completed packet batches return to MainViewModel through ``data_received``.
    """

    status_updated = Signal(str)
    connection_changed = Signal(bool)
    data_received = Signal(object)
    metadata_changed = Signal(float, int)

    def __init__(self) -> None:
        """Create an idle worker; the socket is opened later by ``start``."""
        super().__init__()
        self._client: EMGTCPClient | None = None
        self._timer: QTimer | None = None
        self._last_channel_count = 0

    @Slot(str, int)
    def start(self, host: str, port: int) -> None:
        """Open the TCP client and start polling it inside this worker thread."""
        self.stop()
        self._client = EMGTCPClient(host, port)
        self._client.status_updated.connect(self.status_updated)
        self._client.connect()
        self._last_channel_count = 0

        if not self._client.is_connected:
            self.connection_changed.emit(False)
            return

        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._poll)
        self._timer.start()
        self.connection_changed.emit(True)

    @Slot()
    def stop(self) -> None:
        """Stop polling and close the socket before the worker/thread exits."""
        if self._timer is not None:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
        if self._client is not None:
            self._client.disconnect()
            self._client = None
        self.connection_changed.emit(False)

    def _poll(self) -> None:
        """Drain available socket bytes and emit any complete EMG sample chunk."""
        if self._client is None:
            return

        self._client.receive_data()

        if hasattr(self._client, "get_latest_live_data"):
            new_data = self._client.get_latest_live_data()
        else:
            new_data = self._client.get_latest_data()
        if new_data.shape[1] > 0:
            chunk = np.ascontiguousarray(new_data, dtype=np.float64)
            chunk.setflags(write=False)
            self._emit_stream_metadata(chunk)
            self.data_received.emit(chunk)

        if not self._client.is_connected:
            if self._timer is not None:
                self._timer.stop()
            self.connection_changed.emit(False)

    def _emit_stream_metadata(self, chunk: np.ndarray) -> None:
        """Publish packet-shape metadata inferred from the raw TCP stream."""
        channel_count = int(chunk.shape[0])
        if channel_count != self._last_channel_count:
            self._last_channel_count = channel_count
            self.metadata_changed.emit(float(MainViewModel.EXERCISE_SAMPLE_RATE), channel_count)


class OfflineProcessingWorker(QObject):
    """Prepare offline plot data away from the GUI thread.

    MainView asks MainViewModel for an offline plot. MainViewModel snapshots the
    immutable recording chunks and emits ``_offline_processing_requested`` to
    this worker. The worker filters/slices/downsamples the data, then emits a
    request-id-tagged payload back through ``finished``.
    """

    finished = Signal(int, object)

    @Slot(int, object, str, float, object, object, float, int)
    def process(
        self,
        request_id: int,
        recording_chunks: object,
        mode: str,
        sample_rate: float,
        channel_indices: object,
        visible_duration_seconds: object,
        visible_window_start_seconds: float,
        max_points_per_channel: int,
    ) -> None:
        """Transform a recording snapshot into a small, render-ready payload."""
        chunks = list(recording_chunks)
        selected = [int(index) for index in channel_indices]
        payload = self._empty_payload(request_id, sample_rate)

        if not chunks or not selected:
            self.finished.emit(request_id, payload)
            return

        recording = np.concatenate(chunks, axis=1)
        valid_indices = [
            channel_index
            for channel_index in selected
            if 0 <= channel_index < recording.shape[0]
        ]
        if not valid_indices or recording.shape[1] == 0:
            self.finished.emit(request_id, payload)
            return

        recording_duration = recording.shape[1] / sample_rate

        if visible_duration_seconds is None:
            start_sample = 0
            end_sample = recording.shape[1]
            process_start_sample = start_sample
            process_end_sample = end_sample
            output_start_sample = start_sample
            output_end_sample = end_sample
        else:
            visible_samples = max(2, int(float(visible_duration_seconds) * sample_rate))
            max_start_sample = max(0, recording.shape[1] - visible_samples)
            start_sample = min(
                max_start_sample,
                max(0, int(float(visible_window_start_seconds) * sample_rate)),
            )
            end_sample = min(recording.shape[1], start_sample + visible_samples)
            filter_padding_samples = int(sample_rate * 2.0) if mode == "Filtered" else 100
            prefetch_samples = visible_samples
            output_start_sample = max(0, start_sample - prefetch_samples)
            output_end_sample = min(recording.shape[1], end_sample + prefetch_samples)
            process_start_sample = max(0, output_start_sample - filter_padding_samples)
            process_end_sample = min(recording.shape[1], output_end_sample + filter_padding_samples)

        selected_data = recording[valid_indices, process_start_sample:process_end_sample]
        processed = process_signal(selected_data, mode, sample_rate)
        crop_start = output_start_sample - process_start_sample
        crop_end = crop_start + (output_end_sample - output_start_sample)
        visible_data = processed[:, crop_start:crop_end]
        x_values = np.arange(output_start_sample, output_end_sample, dtype=np.float64) / sample_rate
        visible_data, x_values = self._downsample(visible_data, x_values, max_points_per_channel)

        visible_data = np.ascontiguousarray(visible_data, dtype=np.float64)
        visible_data.setflags(write=False)
        x_values = np.ascontiguousarray(x_values, dtype=np.float64)
        x_values.setflags(write=False)

        payload = {
            "request_id": request_id,
            "data": visible_data,
            "channel_indices": valid_indices,
            "x_values": x_values,
            "recording_duration_seconds": recording_duration,
            "sample_rate": sample_rate,
        }
        self.finished.emit(request_id, payload)

    @staticmethod
    def _empty_payload(request_id: int, sample_rate: float) -> dict[str, object]:
        """Return a valid empty result for no-data or no-channel requests."""
        empty_data = np.empty((0, 0), dtype=np.float64)
        empty_x = np.empty(0, dtype=np.float64)
        empty_data.setflags(write=False)
        empty_x.setflags(write=False)
        return {
            "request_id": request_id,
            "data": empty_data,
            "channel_indices": [],
            "x_values": empty_x,
            "recording_duration_seconds": 0.0,
            "sample_rate": sample_rate,
        }

    def _downsample(
        self,
        data: np.ndarray,
        x_values: np.ndarray,
        max_points_per_channel: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Limit Matplotlib input size while preserving matching x/y samples."""
        if data.shape[1] <= max_points_per_channel:
            return data, x_values
        stride = max(1, int(np.ceil(data.shape[1] / max_points_per_channel)))
        return data[:, ::stride], x_values[::stride]


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
    stream_metadata_changed = Signal(float, int)

    # Worker-prepared offline plot payload. The request id lets MainView ignore
    # late results after the user changes mode, channels, or time window.
    offline_data_changed = Signal(int, object)

    # Button-state signals for client and local server controls.
    connection_changed = Signal(bool)
    server_running_changed = Signal(bool)

    _tcp_connect_requested = Signal(str, int)
    _tcp_disconnect_requested = Signal()
    _offline_processing_requested = Signal(int, object, str, float, object, object, float, int)

    CHANNEL_COUNT = 32
    EXERCISE_SAMPLE_RATE = 2000.0

    def __init__(self) -> None:
        """Create app state, services, and worker threads used by the View."""
        super().__init__()
        self.status_text = "Disconnected."
        # The provided exercise TCP server streams raw packets only. It does
        # not send metadata, so the app uses the exercise recording rate here.
        self.sample_rate = self.EXERCISE_SAMPLE_RATE
        # Keep enough live data for the selected rolling display window. If
        # this buffer is shorter than the visible duration, the plot
        # necessarily leaves part of the canvas empty until enough samples have
        # arrived.
        self.live_window_samples = int(self.sample_rate * 10)
        self.selected_channel = 0
        self.signal_mode = "Filtered"
        self._recording_chunks: list[np.ndarray] = []
        self.recorded_sample_count = 0
        self.stream_channel_count = self.CHANNEL_COUNT
        self.live_raw_data = np.empty((self.stream_channel_count, 0), dtype=np.float64)
        self._latest_offline_request_id = 0
        self._offline_job_in_flight = False
        self._pending_offline_request: tuple[object, ...] | None = None
        self._is_tcp_connected = False
        self.tcp_host = "localhost"
        self.tcp_port = 12345

        # The local server lets the user start the exercise stream inside this
        # GUI instead of opening a second terminal.
        self.tcp_server = EMGTCPServer()
        self.tcp_server.status_updated.connect(self._set_status)
        self.tcp_server.running_changed.connect(self.server_running_changed)

        # TCP reading owns a socket and timer, so it lives off the GUI thread.
        # Its signals cross back to this ViewModel using Qt queued delivery.
        self._tcp_thread = QThread(self)
        self._tcp_worker = TCPAcquisitionWorker()
        self._tcp_worker.moveToThread(self._tcp_thread)
        self._tcp_thread.finished.connect(self._tcp_worker.deleteLater)
        self._tcp_worker.status_updated.connect(self._set_status)
        self._tcp_worker.connection_changed.connect(self._handle_tcp_connection_changed)
        self._tcp_worker.data_received.connect(self._handle_tcp_data)
        self._tcp_worker.metadata_changed.connect(self._handle_stream_metadata)
        self._tcp_connect_requested.connect(self._tcp_worker.start)
        self._tcp_disconnect_requested.connect(self._tcp_worker.stop)
        self._tcp_thread.start()

        # Offline processing may filter a large recording; keeping it in its
        # own thread prevents tab switches and scroll changes from freezing Qt.
        self._offline_thread = QThread(self)
        self._offline_worker = OfflineProcessingWorker()
        self._offline_worker.moveToThread(self._offline_thread)
        self._offline_thread.finished.connect(self._offline_worker.deleteLater)
        self._offline_processing_requested.connect(self._offline_worker.process)
        self._offline_worker.finished.connect(self._handle_offline_result)
        self._offline_thread.start()

    def connect_to_server(self, host: str, port_text: str) -> None:
        """Reset recording state and ask the TCP worker to connect."""
        port = self._parse_port(port_text)
        if port is None:
            return

        # A new connection starts a new recording. Existing offline data is kept
        # only when the user disconnects from an active stream.
        self.disconnect_from_server(announce=False)
        self._recording_chunks.clear()
        self.recorded_sample_count = 0
        self.live_raw_data = np.empty((self.CHANNEL_COUNT, 0), dtype=np.float64)
        self.stream_channel_count = self.CHANNEL_COUNT
        self.tcp_host = host.strip() or "localhost"
        self.tcp_port = port
        self._tcp_connect_requested.emit(self.tcp_host, self.tcp_port)
        self._emit_current_live_data()

    @Slot(float, int)
    def _handle_stream_metadata(self, sample_rate: float, channel_count: int) -> None:
        """Update display/plot metadata inferred from packet shape.

        The course server sends only float64 sample packets, not sampling-rate
        metadata. ``sample_rate`` therefore carries the protocol default.
        """
        if np.isfinite(sample_rate) and sample_rate > 0:
            self.sample_rate = float(sample_rate)
        self.stream_channel_count = max(0, int(channel_count))
        self.live_window_samples = max(2, int(10 * self.sample_rate))
        self.stream_metadata_changed.emit(self.sample_rate, self.stream_channel_count)

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
        """Ask the TCP worker to stop and notify the View about disconnected UI state."""
        self._tcp_disconnect_requested.emit()
        if announce and not self._is_tcp_connected:
            self._set_status("Already disconnected.")
        self.connection_changed.emit(False)

    def set_channel(self, channel_number: int) -> None:
        """Update selected channel. The public number is one-based."""
        if 1 <= channel_number <= self.CHANNEL_COUNT:
            # The GUI shows channels as 1..32, while NumPy arrays are indexed
            # as 0..31. Store the zero-based index internally.
            self.selected_channel = channel_number - 1

            # Re-emit immediately so switching channels updates the plot even
            # before the next network packet arrives.
            self._emit_current_live_data()
        else:
            self._set_status("Invalid channel. Choose a value from 1 to 32.")

    def set_signal_mode(self, mode: str) -> None:
        """Update processing mode for live and offline displays."""
        if mode not in {"Original", "RMS", "Filtered"}:
            self._set_status("Invalid signal mode.")
            return
        self.signal_mode = mode
        self._emit_current_live_data()

    def set_live_window_seconds(self, seconds: float) -> None:
        """Update how much recent data is processed for the live plots."""
        self.live_window_samples = max(2, int(float(seconds) * self.sample_rate))
        self.live_raw_data = self._recent_recording_window(self.live_window_samples)
        self._emit_current_live_data()

    def request_offline_plot(self) -> None:
        """Compatibility hook for older callers that only need the no-data status."""
        if self.recorded_sample_count == 0:
            self._set_status("No recorded data available for offline plotting.")
            return

    def request_offline_processing(
        self,
        mode: str,
        channel_indices: list[int],
        visible_duration_seconds: float | None,
        visible_window_start_seconds: float,
        max_points_per_channel: int = 6000,
    ) -> int:
        """Queue an asynchronous offline processing job and return its request id.

        MainView stores the returned id. When ``offline_data_changed`` arrives,
        the View renders only if the ids still match. If another offline job is
        already running, this method keeps only the newest pending request.
        """
        self._latest_offline_request_id += 1
        request_id = self._latest_offline_request_id
        if self.recorded_sample_count == 0:
            self.offline_data_changed.emit(
                request_id,
                OfflineProcessingWorker._empty_payload(request_id, self.sample_rate),
            )
            return request_id

        request = (
            request_id,
            tuple(self._recording_chunks),
            mode,
            self.sample_rate,
            list(channel_indices),
            visible_duration_seconds,
            visible_window_start_seconds,
            max_points_per_channel,
        )
        if self._offline_job_in_flight:
            self._pending_offline_request = request
        else:
            self._start_offline_request(request)
        return request_id

    def _start_offline_request(self, request: tuple[object, ...]) -> None:
        """Mark the worker busy and dispatch a prepared request tuple."""
        self._offline_job_in_flight = True
        self._offline_processing_requested.emit(*request)

    @Slot(object)
    def _handle_tcp_data(self, new_data: object) -> None:
        """Receive worker chunks, update recording cache, and publish live data."""
        chunk = np.asarray(new_data, dtype=np.float64)
        if chunk.ndim != 2 or chunk.shape[1] == 0:
            return

        if chunk.shape[0] != self.stream_channel_count:
            self.stream_channel_count = chunk.shape[0]
            self.stream_metadata_changed.emit(self.sample_rate, self.stream_channel_count)
        if self.live_raw_data.shape[0] != chunk.shape[0]:
            self.live_raw_data = np.empty((chunk.shape[0], 0), dtype=np.float64)

        self._recording_chunks.append(chunk)
        self.recorded_sample_count += chunk.shape[1]
        self.live_raw_data = np.concatenate((self.live_raw_data, chunk), axis=1)[
            :, -self.live_window_samples :
        ]
        self._emit_current_live_data()

    @Slot(bool)
    def _handle_tcp_connection_changed(self, is_connected: bool) -> None:
        """Forward worker connection state to MainView button/status handlers."""
        self._is_tcp_connected = is_connected
        self.connection_changed.emit(is_connected)

    def _recent_recording_window(self, sample_count: int) -> np.ndarray:
        """Return the newest raw samples without concatenating the full recording."""
        if not self._recording_chunks:
            return np.empty((self.stream_channel_count, 0), dtype=np.float64)

        selected_chunks: list[np.ndarray] = []
        remaining = sample_count
        for chunk in reversed(self._recording_chunks):
            if remaining <= 0:
                break
            selected_chunks.append(chunk[:, -remaining:])
            remaining -= chunk.shape[1]

        selected_chunks.reverse()
        return np.concatenate(selected_chunks, axis=1)[:, -sample_count:]

    def _emit_current_live_data(self) -> None:
        """Process current buffers and emit the data needed by live views."""
        if self.live_raw_data.shape[1] == 0:
            empty = np.empty((self.stream_channel_count, 0), dtype=np.float64)
            self.live_data_changed.emit(empty, empty, 0.0)
            return

        # Only send the most recent live window to VisPy. The full recording
        # remains as immutable chunks for offline inspection.
        live_data = self.live_raw_data[:, -self.live_window_samples :]
        processed = process_signal(live_data, self.signal_mode, self.sample_rate)
        current_time = self.recorded_sample_count / self.sample_rate
        selected_channel = min(self.selected_channel, processed.shape[0] - 1)
        self.live_data_changed.emit(processed, processed[selected_channel], current_time)

    @Slot(int, object)
    def _handle_offline_result(self, request_id: int, payload: object) -> None:
        """Forward only the newest completed offline payload to MainView."""
        self._offline_job_in_flight = False
        if request_id != self._latest_offline_request_id:
            self._start_pending_offline_request()
            return
        self.offline_data_changed.emit(request_id, payload)
        self._start_pending_offline_request()

    def _start_pending_offline_request(self) -> None:
        """Run the newest request that arrived while the worker was busy."""
        if self._pending_offline_request is None:
            return
        request = self._pending_offline_request
        self._pending_offline_request = None
        self._start_offline_request(request)

    def _set_status(self, message: str) -> None:
        """Store and emit status text consumed by the footer label in MainView."""
        self.status_text = message
        self.status_changed.emit(message)

    def _parse_port(self, port_text: str) -> int | None:
        """Validate user-entered TCP port text before worker/server use."""
        try:
            port = int(port_text)
            if port <= 0 or port > 65535:
                raise ValueError
            return port
        except ValueError:
            self._set_status("Invalid TCP port. Enter a number from 1 to 65535.")
            return None

    def shutdown(self) -> None:
        """Stop worker threads before Qt destroys their QObjects."""
        if self._tcp_thread.isRunning():
            QMetaObject.invokeMethod(
                self._tcp_worker,
                "stop",
                Qt.ConnectionType.BlockingQueuedConnection,
            )
            self._tcp_thread.quit()
            self._tcp_thread.wait(1500)
        if self._offline_thread.isRunning():
            self._offline_thread.quit()
            self._offline_thread.wait(1500)

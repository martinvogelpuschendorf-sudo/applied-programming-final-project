"""Local TCP server service for launching the exercise stream from the GUI."""

from __future__ import annotations

import pickle
import socket
import threading
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, Signal


class EMGTCPServer(QObject):
    """Small TCP server that streams 32 x 18 float64 EMG packets.

    This service mirrors the exercise server but is controlled from the GUI.
    It loads the provided `data/recording.pkl` from the project folder. If that
    file is missing, the server can still listen for clients but will not stream
    data.
    """

    status_updated = Signal(str)
    running_changed = Signal(bool)
    recording_available_changed = Signal(bool)

    CHANNELS = 32
    SAMPLES_PER_PACKET = 18

    def __init__(self, host: str = "localhost", port: int = 12345) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self.sampling_rate = 1000.0
        self.server_socket: socket.socket | None = None
        self.clients: list[socket.socket] = []
        self.running = False
        self.has_recording_data = False
        self._accept_thread: threading.Thread | None = None
        self._windows = self._load_default_windows()

    def start(self, host: str, port: int) -> bool:
        """Start accepting TCP clients on host:port."""
        if self.running:
            self.status_updated.emit("TCP server is already running.")
            return True

        self.host = host.strip() or "localhost"
        self.port = port

        try:
            # The socket listens for client connections. SO_REUSEADDR makes it
            # less annoying to restart the server during development because
            # the OS can reuse the same port sooner.
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(0.5)
        except OSError as error:
            self.server_socket = None
            self.status_updated.emit(f"Could not start TCP server: {error}")
            self.running_changed.emit(False)
            return False

        self.running = True

        # Accepting clients blocks, so it must run outside the Qt GUI thread.
        # The thread is daemonized so it cannot keep Python alive after exit.
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()
        if self.has_recording_data:
            self.status_updated.emit(f"TCP server started on {self.host}:{self.port}.")
        else:
            self.status_updated.emit(
                "TCP server started, but data/recording.pkl was not found. "
                "Server is not sending data."
            )
        self.running_changed.emit(True)
        self.recording_available_changed.emit(self.has_recording_data)
        return True

    def stop(self) -> None:
        """Stop the server and close all connected clients."""
        if not self.running and self.server_socket is None:
            self.status_updated.emit("TCP server is already stopped.")
            self.running_changed.emit(False)
            return

        # Setting `running` to False tells both the accept loop and all client
        # streaming loops to exit as soon as possible.
        self.running = False
        if self.server_socket is not None:
            try:
                self.server_socket.close()
            except OSError:
                pass
            self.server_socket = None

        for client in list(self.clients):
            try:
                client.close()
            except OSError:
                pass
        self.clients.clear()

        self.status_updated.emit("TCP server stopped.")
        self.running_changed.emit(False)
        self.recording_available_changed.emit(self.has_recording_data)

    def _accept_loop(self) -> None:
        """Accept clients and start one streaming thread per client."""
        while self.running and self.server_socket is not None:
            try:
                client_socket, _address = self.server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            self.clients.append(client_socket)

            # Each connected client receives the same packet stream. This keeps
            # the server simple and lets the GUI reconnect without restarting
            # the whole application.
            client_thread = threading.Thread(
                target=self._stream_to_client,
                args=(client_socket,),
                daemon=True,
            )
            client_thread.start()

    def _stream_to_client(self, client_socket: socket.socket) -> None:
        """Send packet windows repeatedly until the client or server stops."""
        if not self._windows:
            try:
                while self.running:
                    time.sleep(0.2)
            finally:
                if client_socket in self.clients:
                    self.clients.remove(client_socket)
                try:
                    client_socket.close()
                except OSError:
                    pass
            return

        sleep_time = self.SAMPLES_PER_PACKET / self.sampling_rate
        try:
            while self.running:
                for window in self._windows:
                    if not self.running:
                        break

                    # The client expects exactly 32 * 18 float64 values in C
                    # order, so every packet is converted to that format before
                    # sending.
                    client_socket.sendall(window.astype(np.float64).tobytes(order="C"))
                    time.sleep(sleep_time)
        except OSError:
            pass
        finally:
            if client_socket in self.clients:
                self.clients.remove(client_socket)
            try:
                client_socket.close()
            except OSError:
                pass

    def _load_default_windows(self) -> list[np.ndarray]:
        """Load real exercise data from the project-local recording file."""
        recording_path = self._default_recording_path()
        if recording_path is not None:
            try:
                with recording_path.open("rb") as file:
                    recording = pickle.load(file)
                signal = np.asarray(recording["biosignal"], dtype=np.float64)[: self.CHANNELS]
                self.sampling_rate = float(
                    recording.get("device_information", {}).get("sampling_frequency", 1000.0)
                )
                windows = self._windows_from_signal(signal)
                self.has_recording_data = bool(windows)
                self.status_updated.emit(f"Loaded TCP recording from {recording_path}.")
                return windows
            except Exception as error:
                self.status_updated.emit(f"Could not load recording.pkl: {error}")

        self.has_recording_data = False
        self.status_updated.emit("Missing data/recording.pkl. TCP server will not send data.")
        return []

    def _windows_from_signal(self, signal: np.ndarray) -> list[np.ndarray]:
        """Convert a recording array into 32 x 18 packet windows."""
        if signal.ndim == 3:
            return [
                signal[:, :, index].astype(np.float64)
                for index in range(signal.shape[2])
                if signal[:, :, index].shape == (self.CHANNELS, self.SAMPLES_PER_PACKET)
            ]

        if signal.ndim == 2:
            sample_count = signal.shape[1] - signal.shape[1] % self.SAMPLES_PER_PACKET
            trimmed = signal[:, :sample_count]
            return [
                trimmed[:, start : start + self.SAMPLES_PER_PACKET].astype(np.float64)
                for start in range(0, sample_count, self.SAMPLES_PER_PACKET)
            ]

        return []

    def _synthetic_windows(self) -> list[np.ndarray]:
        """Generate deterministic test EMG-like waves for local demos."""
        duration_seconds = 30
        sample_count = int(self.sampling_rate * duration_seconds)
        time_axis = np.arange(sample_count, dtype=np.float64) / self.sampling_rate
        data = np.empty((self.CHANNELS, sample_count), dtype=np.float64)
        for channel in range(self.CHANNELS):
            frequency = 8.0 + channel * 0.7
            amplitude = 0.5 + channel * 0.02
            data[channel] = amplitude * np.sin(2 * np.pi * frequency * time_axis)
            data[channel] += 0.08 * np.sin(2 * np.pi * 50.0 * time_axis)
        return self._windows_from_signal(data)

    def _default_recording_path(self) -> Path | None:
        """Return the repo-local recording path, with legacy fallbacks."""
        current = Path(__file__).resolve()
        package_root = current.parents[1]
        candidates = [package_root / "data" / "recording.pkl"]
        for parent in current.parents:
            candidates.append(parent / "recording.pkl")
            candidates.append(parent / "Applied-Programming-2026" / "recording.pkl")
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

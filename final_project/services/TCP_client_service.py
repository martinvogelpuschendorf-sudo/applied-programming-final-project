import socket
import numpy as np
from PySide6.QtCore import QObject, Signal


class EMGTCPClient(QObject):
    status_updated = Signal(str)
    # Used to notify the ViewModel of current connection status or error messages
    data_ready = Signal()
    # Used to notify the ViewModel that new packets have been reconstructed and are ready for plotting
    no_data_warning = Signal(str)

    def __init__(self, host='localhost', port=12345):
        super().__init__()
        self.host = host
        self.port = port

        self.client_socket = None
        self.is_connected = False


        # Buffer Design
        self.byte_buffer = bytearray()
        self.TARGET_BYTES = 4608

        self.all_packets = []
        self.live_pointer = 0

    # Connection Control (TCP communication)
    def connect(self):

        if self.is_connected:
            return True
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.host, self.port))
            self.client_socket.setblocking(False)

            self.is_connected = True
            self.status_updated.emit("Connected successfully to server.")
            return True

        except Exception as e:
            self.is_connected = False
            if self.client_socket is not None:
                try:
                    self.client_socket.close()
                except Exception:
                    pass
                self.client_socket = None

            self.status_updated.emit(f"Connection failed: {e}")
            return False

    def disconnect(self):
        if not self.is_connected:
            return

        self.is_connected = False
        if self.client_socket is not None:
            try:
                self.client_socket.close()
            except Exception:
                pass
            self.client_socket = None
        self.status_updated.emit("Client disconnected. Playback finished.")  # Notify front-end of secure disconnection

    # Data Retrieval & Streaming Interface (TCP communication)
    def receive_data(self):
        if not self.is_connected or self.client_socket is None:
            return

        while True:
            try:
                new_bytes = self.client_socket.recv(4096)

                if not new_bytes:
                    self.status_updated.emit(
                        "Server finished playback. Disconnecting...")
                    self._extract_packets()
                    self.disconnect()
                    return

                self.byte_buffer.extend(new_bytes)

            except BlockingIOError:
                break
            except Exception as e:
                self.status_updated.emit(
                    f"Read error: {e}")
                self._extract_packets()
                self.disconnect()
                return

        self._extract_packets()


    # Packet Processing (Packet reconstruction)
    def _extract_packets(self):
        has_new_data = False

        while len(self.byte_buffer) >= self.TARGET_BYTES:
            packet_bytes = self.byte_buffer[:self.TARGET_BYTES]
            del self.byte_buffer[:self.TARGET_BYTES]

            packet = np.frombuffer(packet_bytes, dtype=np.float64).reshape(32, 18)

            self.all_packets.append(packet)
            has_new_data = True

        if has_new_data:
            self.data_ready.emit()

    # Data Streaming API (Buffering / Core Buffer Management)
    def get_latest_live_data(self):
        """
        For VisPy rolling time window
        Returns all new data segments accumulated since the last read and advances the read pointer.
        """
        current_len = len(self.all_packets)
        if self.live_pointer >= current_len:
            return np.empty((32, 0), dtype=np.float64)

        new_segments = self.all_packets[self.live_pointer:current_len]
        self.live_pointer = current_len
        return np.concatenate(new_segments, axis=1)

    def get_all_offline_data(self):
        """
        For Matplotlib offline analysis & signal processing called after disconnecting.
        Returns the complete, non-fragmented raw historical data from connection start to stop.
        """
        if not self.all_packets:  # Error handling: Raise an exception if no data was recorded before stopping
            self.no_data_warning.emit("No data recorded. Plot cannot be generated.")
            return np.empty((32, 0), dtype=np.float64)

        return np.concatenate(self.all_packets, axis=1)

    def clear_buffers(self):
        self.all_packets.clear()
        self.live_pointer = 0
        self.byte_buffer.clear()

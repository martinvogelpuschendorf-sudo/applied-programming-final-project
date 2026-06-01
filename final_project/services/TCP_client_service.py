import socket
import numpy as np
from PySide6.QtCore import QObject, Signal


class EMGTCPClient(QObject):
    status_updated = Signal(str)

    def __init__(self, host='localhost', port=12345):
        super().__init__()
        self.host = host
        self.port = port

        self.client_socket = None
        self.is_connected = False

        # Buffering: Use a dynamic bytearray to temporarily pool incoming streaming data
        self.byte_buffer = bytearray()

        self.data_buffer = np.empty((32, 0), dtype=np.float64)

        # Packet Reconstruction Specification
        self.TARGET_BYTES = 4608

    def connect(self):
        """Connect to the TCP server and configure non-blocking state."""
        if self.is_connected:
            return

        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.host, self.port))

            # Set the socket to non-blocking mode to seamlessly integrate with GUI event loops
            self.client_socket.setblocking(False)

            self.is_connected = True
            self.status_updated.emit("Connected successfully to server.")
        except Exception as e:
            self.is_connected = False
            self.status_updated.emit(f"Connection failed: {e}")

    def disconnect(self):
        """Securely close the active network socket and reset connection states."""
        self.is_connected = False
        if self.client_socket is not None:
            try:
                self.client_socket.close()
            except Exception:
                pass
            self.client_socket = None
        self.status_updated.emit("Client disconnected. Playback finished.")

    def receive_data(self):

        # If disconnected, return immediately and do not attempt auto-reconnect (Exercise Specification)
        if not self.is_connected or self.client_socket is None:
            return

        # Continuous read loop to drain the network interface buffer completely
        while True:
            try:
                new_bytes = self.client_socket.recv(4096)

                # ROBUSTNESS: Handle 'Connection is lost' (Server closed the connection after playback)
                if not new_bytes:
                    self.status_updated.emit("Server finished playback. Disconnecting...")
                    self.disconnect()
                    return

                self.byte_buffer.extend(new_bytes)

            except BlockingIOError:
                # No more data is available in the network socket right now.
                break
            except Exception as e:
                self.status_updated.emit(f"Read error: {e}")
                self.disconnect()
                return

        self._extract_packets()

    def _extract_packets(self):

        packets = []

        # Packet Reconstruction (Handling Clumping & Fragmentation)
        # Keep slicing complete frames as long as the pool holds enough bytes
        while len(self.byte_buffer) >= self.TARGET_BYTES:
            packet_bytes = self.byte_buffer[:self.TARGET_BYTES]

            del self.byte_buffer[:self.TARGET_BYTES]

            packet = np.frombuffer(packet_bytes, dtype=np.float64)

            packet = packet.reshape(32, 18)

            packets.append(packet)

        if len(packets) == 0:
            return

        new_data = np.concatenate(packets, axis=1)

        self.data_buffer = np.concatenate((self.data_buffer, new_data), axis=1)

    def get_latest_data(self):

        current_data = self.data_buffer

        self.data_buffer = np.empty((32, 0), dtype=np.float64)
        return current_data
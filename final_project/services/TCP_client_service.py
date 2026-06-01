import socket
import numpy as np
import threading
from collections import deque
# Import PySide6 core components for cross-thread communication using the Signal mechanism
from PySide6.QtCore import QObject, Signal


class EMGTCPClient(QObject):
    """
    EMGTCPClient handles backend network communication in an isolated thread.
    It inherits from QObject to natively utilize PySide6's Signals and Slots mechanism,
    allowing thread-safe communication between this network service and the GUI/ViewModel.
    """

    # Signal emitted to transmit status updates or error messages as strings to the UI layer
    status_updated = Signal(str)

    # Signal emitted to notify the ViewModel whenever a new data frame has been successfully reconstructed
    data_ready = Signal()

    def __init__(self, host='localhost', port=12345):
        """
        Initializes the client with target connection parameters and sets up the internal data structure.
        """
        super().__init__()
        self.host = host
        self.port = port
        self.running = False
        self.client_socket = None

        # 【Buffering】
        # A collections.deque is used as a First-In-First-Out (FIFO) data cache buffer.
        # It is inherently thread-safe for rapid appends and pops from opposite ends,
        # allowing the network thread to push data while the GUI thread pulls it concurrently.
        # maxlen prevents memory leaks by discarding the oldest data if the GUI stops rendering.
        self.data_buffer = deque(maxlen=10000)

        # 【Packet Reconstruction Specification】
        # Target data frame size calculation based on the server's data payload:
        # 32 channels * 18 samples per packet = 576 data points (numerical values).
        # Since the server converts the matrix using np.float64, each value occupies exactly 8 bytes.
        # Total required bytes per complete frame = 576 * 8 = 4608 bytes.
        self.TARGET_BYTES = 4608

    def start(self):
        """
        Spawns and initiates the background worker thread dedicated to network reception.
        This prevents blocking the PySide6 main GUI thread, keeping the user interface highly responsive.
        """
        if self.running:
            return  # Prevent spawning multiple redundant threads if called repeatedly
        self.running = True

        # Target the internal execution loop and configure it as a background daemon thread
        self.recv_thread = threading.Thread(target=self._receive_loop)
        self.recv_thread.daemon = True  # Allows the thread to exit automatically when the main application closes
        self.recv_thread.start()

    def _receive_loop(self):
        """
        The core network reception worker loop. Executes in a separate thread,
        handling connection states, low-level socket streams, and packet parsing.
        """
        # Initialize a standard IPv4, TCP streaming socket
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # 【ROBUSTNESS: Handle 'Server is not running' / 'Wrong port entered'】
        # Configure a connection timeout threshold (10 seconds) so that client_socket.connect()
        # does not freeze indefinitely if the target server is down or unreachable.
        self.client_socket.settimeout(10.0)

        try:
            # Attempt to establish a network connection with the server
            self.client_socket.connect((self.host, self.port))

            # Revert the socket to blocking mode after a successful connection to ensure stable data reception
            self.client_socket.settimeout(None)
            self.status_updated.emit("Connected successfully to server.")

            # Temporary internal byte array pool acting as an accumulator for fragmented network streams
            raw_data_pool = bytearray()

            while self.running:
                # Receive a raw data chunk from the TCP stream. 4096 bytes is a standard socket buffer chunk size.
                packet = self.client_socket.recv(4096)

                # 【ROBUSTNESS: Handle 'Connection is lost'】
                # In standard TCP sockets, receiving an empty byte object (b'') indicates that
                # the remote server has initiated a graceful shutdown or dropped the connection.
                if not packet:
                    self.status_updated.emit("Connection lost: Server closed the connection.")
                    break

                # Append the newly arrived byte chunk to the data accumulation pool
                raw_data_pool.extend(packet)

                # 【Packet Reconstruction (Handling Clumping & Fragmentation)】
                # Because TCP is a continuous byte-stream protocol, individual network packets might get grouped
                # together ('clumping/packet-sticking') or chopped up into sub-fragments ('fragmentation').
                # This loop continuously extracts chunks only when a guaranteed full data frame is present.
                while len(raw_data_pool) >= self.TARGET_BYTES:
                    # Slice exactly 4608 bytes from the front of the accumulation pool
                    frame_bytes = raw_data_pool[:self.TARGET_BYTES]
                    # Discard the extracted bytes from the pool, shifting the remaining stream forward
                    del raw_data_pool[:self.TARGET_BYTES]

                    # Deserialize the binary buffer back into a structured NumPy array of type float64
                    # and reshape it to match the original dimension grid of (32 channels, 18 samples)
                    matrix_data = np.frombuffer(frame_bytes, dtype=np.float64).reshape(32, 18)

                    # 【CORE REQUIREMENT 3: Append to Buffer Cache】
                    self.data_buffer.append(matrix_data)

                    # Broadcast to the ViewModel that a fresh data frame is available for rendering
                    self.data_ready.emit()

                    # Catch specific standard operating system/network execution anomalies
        except (OSError, ConnectionRefusedError, socket.timeout) as error:
            # Catches: 1) Connection refused (Server down), 2) Incorrect port mapping, 3) Timeout expiry
            self.status_updated.emit(f"Could not connect: {error}")

        except Exception as e:
            # General fallback exception handling block to prevent catastrophic application crashes
            self.status_updated.emit(f"Unexpected error: {e}")

        finally:
            # Guarantee that cleanup operations run and resources release upon loop exit
            self.stop()

    def get_latest_data(self):
        """
        Public API interface allowing the GUI or ViewModel thread to safely drain
        all accumulated data blocks from the internal buffer for processing or plotting.

        Returns:
            list: A list containing reconstructed NumPy matrices, each shaped as (32, 18).
        """
        data_list = []
        # Flush the thread-safe deque and move all elements into a temporary list array
        while self.data_buffer:
            data_list.append(self.data_buffer.popleft())

        # 【ROBUSTNESS: Handle 'No data available for offline plotting'】
        # Detects if an analysis task was requested while the network client is inactive and the cache is blank
        if not data_list and not self.running:
            self.status_updated.emit("Warning: No data available in buffer.")

        return data_list

    def stop(self):
        """
        Gracefully terminates the background operation thread and securely tear down active network sockets.
        """
        self.running = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass  # Ignore secondary errors during resource teardown
            self.client_socket = None
        print("Client stopped.")



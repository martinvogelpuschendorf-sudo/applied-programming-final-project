## Model Component: EMGTCPClient Specification

The `EMGTCPClient` class handles the core **TCP communication, packet reconstruction, and buffering** for the EMG pipeline. It provides a non-blocking network client that isolates low-level data streaming from the PySide6 GUI event loop.

### Core Architecture & API List

Here is the list of functions implemented in the class `EMGTCPClient` and how they work:

#### 1. `def __init__(self, host='localhost', port=12345)`
* **What it does:** Initializes the client configuration, internal streaming byte buffers, and separate caching pools for live and offline data tracking.
* **Specification:** * Defines `self.TARGET_BYTES = 4608` ($32 \text{ channels} \times 18 \text{ samples} \times 8 \text{ bytes (float64)}$) as the strict alignment threshold for packet reconstruction.
  * Implements a high-performance Python list (`self.all_packets`) for cumulative storage to prevent memory allocation bottlenecks caused by frequent NumPy concatenation.

#### 2. `def connect(self)`
* **What it does:** Establishes a TCP connection to the server and immediately flips the socket into **Non-blocking Mode** (`self.client_socket.setblocking(False)`).
* **Note:** This ensures that when the network interface is queried for data, it returns instantly instead of hanging, effectively preventing the GUI thread from freezing.

#### 3. `def receive_data(self)`
* **What it does:** Acts as the automated streaming core. This must be continuously driven inside a background thread or a `QTimer` loop. It drains all raw binary data currently pooled inside the network socket buffer.
* **Robustness:** * If the server finishes playing the data file and closes the connection, this function detects the empty frame, cleanly shuts down the socket via `disconnect()`, and halts further operations.
  * It automatically handles streaming clumping and fragmentation by appending newly sliced raw bytes into an internal `byte_buffer`. Once enough bytes are accumulated, it reconstructs them into standard `(32, 18)` NumPy matrices.

#### 4. `def get_latest_live_data(self)`
* **What it does (For VisPy Live Plotting):** This is the high-performance retrieval interface for real-time visualization. It fetches all newly accumulated packets since the last query and advances an internal index pointer to clear the live view state.
* **Return Value:** A concatenated NumPy array with a shape of `(32, N)`, where `32` represents the fixed EMG channels and `N` represents the total number of samples collected during this specific timer chunk.

#### 5. `def get_all_offline_data(self)`
* **What it does (For Offline Matplotlib & Processing):** This is the historical data retrieval interface. It allows offline inspection after streaming completes by returning the complete recording from the moment of connection to disconnection.
* **Note:** Unlike the live data interface, this function **does not delete** or clear the internal storage, preserving the intact data matrix for filtering and RMS calculation.
* **Return Value:** A complete NumPy array with a shape of `(32, Total Samples)`.

#### 6. `def disconnect(self)`
* **What it does:** Safely tears down active network connections, closes the socket stream, and resets internal boolean flags.

---

* **For Real-time Plotting Pipeline:** Connect ViewModel slot to the `data_ready` signal emitted by this client. Within your `QTimer` or thread polling cycle, call `get_latest_live_data()` to grab the latest signal segment without losing past records.
* **For Signal Analysis Pipeline :** After calling `disconnect()` or upon receiving the "Server finished playback" status notification, call `get_all_offline_data()` to export the raw, unaltered history dataset straight into your filter algorithms and Matplotlib figure widgets.
Here is the list of functions implemented in the class EMGTCPClient and how they work:

### 1. `def __init__(self, host='localhost', port=12345)`
* **What it does:** Initializes the client config, internal streaming byte buffers, and NumPy data storage cache.
* **Specification:** Defines `self.TARGET_BYTES = 4608` (32 channels x 18 samples x 8 bytes) as the strict data alignment threshold for incoming packages.

---

### 2. `def connect(self)`
* **What it does:** Establishes a connection to the server and immediately flips the socket into Non-blocking Mode (`self.client_socket.setblocking(False)`).
* **Note:** This ensures that when we query the network card for data, it returns instantly instead of hanging or blocking the GUI.

---

### 3. `def receive_data(self)`
* **What it does:** This must be called inside `QTimer` loop. It drains all raw binary data currently pooled inside the network socket buffer.
* **Robustness:** * If the server finishes playing the file and closes the connection, this function detects it, cleanly shuts down the socket via `disconnect()`, and halts data processing.
  * It automatically appends newly sliced binary blocks into an internal `byte_buffer` to handle streaming fragmentation.

---

### 4. `def get_latest_data(self)` 
* **What it does:** This is the extraction interface for the GUI / ViewModel. Call this function to fetch all accumulated metrics and clear the internal cache to prepare for the next timer cycle.
* **Return Value:** A concatenated NumPy array with a shape of `(32, N)`, where `32` represents the EMG channels and `N` represents the total number of samples collected during this timer chunk.

---

### 5. `def disconnect(self)`
* **What it does:** Safely tears down active network connections and resets internal boolean flags.
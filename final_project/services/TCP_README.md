# TCP Communication Notes

This application is designed to connect to the provided exercise TCP server as
a TCP client. The GUI also includes a built-in local TCP demo server, but that
server is only a convenience feature for local testing and demos.

## Intended Project Workflow

Use this workflow when testing against the provided exercise server:

1. Start the provided exercise TCP server outside this GUI.
2. Enter the server host and port in the GUI.
3. Click `Connect TCP Client`.
4. The app receives 32-channel EMG packets and displays them live.
5. After disconnecting, the recorded data remains available in the Offline tab.

The connect action only connects the TCP client. It does not automatically start
the built-in local demo server.

## Built-In Local Demo Server

The app also contains `EMGTCPServer` in `TCP_server_service.py`. This server is
started only when the user clicks `Start Demo TCP Server`.

This built-in server is not required by the final project specification. It is
included so the app can be demonstrated or debugged without launching the
provided exercise server separately.

If you enter a different free port, such as `12346`, and explicitly start the
built-in demo server there, the GUI client can connect successfully because both
the local server and client are using the same selected port.

For grading or requirement-focused testing, use the provided exercise server as
the server source and treat the built-in server as a local fallback.

## Current GUI Behavior

- `Start Demo TCP Server` starts or stops the built-in local demo server on the
  selected host and port.
- `Connect TCP Client` connects only the client to the selected host and port.
- The connect action no longer starts the demo server automatically.
- A changed port works only if an external server or the explicitly started
  local demo server is listening on that port.

## EMGTCPClient

`EMGTCPClient` handles the client-side TCP connection and packet reconstruction.
It is currently owned by `TCPAcquisitionWorker` in the ViewModel layer so socket
polling runs outside the GUI thread.

### `__init__(host='localhost', port=12345)`

Initializes the client endpoint, byte buffers, decoded sample buffer, and packet
size configuration.

The expected packet size is:

```text
32 channels x 18 samples x 8 bytes = 4608 bytes
```

### `connect()`

Opens the TCP socket and switches it to non-blocking mode. Non-blocking mode is
important because socket reads should never freeze the GUI.

### `receive_data()`

Drains all currently available bytes from the socket and appends them to the
internal byte buffer. It handles packet fragmentation and clumped packets by
extracting only complete 4608-byte frames.

If the server closes the connection, this method disconnects the client cleanly.

### `get_latest_live_data()`

Returns the decoded data accumulated since the previous call and clears the
live read pointer.

The returned array has shape:

```text
(32, N)
```

where `32` is the number of EMG channels and `N` is the number of samples
received during that polling interval.

### `get_all_offline_data()`

Returns the full historical packet buffer as one `(32, Total Samples)` array.
The current ViewModel stores its own immutable recording chunks for offline
processing, but this client method is still available on the service.

### `disconnect()`

Closes the active socket and resets the client connection state.

## EMGTCPServer

`EMGTCPServer` is the built-in local demo server. It streams 32-channel EMG
packets to any connected local client.

It first tries to load the provided `recording.pkl`. If that file is not
available, it generates a synthetic EMG-like signal so the GUI can still be
tested.

Again, this server is for local testing/demo. The main project requirement is 
that the app can connect as a client to the provided exercise TCP server.

## Data Buffering Design (Runtime Flow)
To keep the application simple and lightweight, data buffering is handled 
directly within the runtime path by the ViewModel layer, avoiding redundant manager classes:

1. Live Rolling Buffer: 
Handled via `MainViewModel.live_raw_data[:, -live_window_samples:]` to slice out the newest 
samples required for real-time VisPy visualization.

2. Full Offline Recording: Handled via `MainViewModel._recording_chunks` to store the entire 
history of received EMG blocks for full offline analysis.

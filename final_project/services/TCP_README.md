# TCP Communication Notes

This application is designed to connect to the provided exercise TCP server as
a TCP client. The GUI also includes a built-in local TCP server, but that server
is only a convenience feature for local testing and demos.

## Intended Project Workflow

Use this workflow when testing against the provided exercise server:

1. Start the provided exercise TCP server outside this GUI.
2. Enter the server host and port in the GUI.
3. Click the connect button in the GUI.
4. The app receives 32-channel EMG packets and displays them live.
5. After disconnecting, the recorded data remains available in the Offline tab.

The client implementation is `EMGTCPClient` in `TCP_client_service.py`.

## Built-In Local Demo Server

The app also contains `EMGTCPServer` in `TCP_server_service.py`. This server is
started by the GUI's "Start TCP Server" button.

This built-in server is not required by the final project specification. It is
included so the app can be demonstrated or debugged without launching the
provided exercise server separately.

If you enter a different free port, such as `12346`, and start the built-in
server there, the GUI client can still connect successfully because both the
local server and client are using the same selected port.

## Current GUI Behavior

- "Start TCP Server" starts the built-in local demo server on the selected host
  and port.
- The connect action creates a TCP client connection to the selected host and
  port.
- In the current GUI flow, the app may helpfully start the local demo server
  before connecting if the built-in server is not already running.
- This can make a changed port appear to "work" even when no external exercise
  server is running, because the app has started its own local test server.

For grading or requirement-focused testing, use the provided exercise server as
the server source and treat the built-in server as a local fallback.

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

### `get_latest_data()`

Returns the decoded data accumulated since the previous call and clears the
client-side decoded buffer.

The returned array has shape:

```text
(32, N)
```

where `32` is the number of EMG channels and `N` is the number of samples
received during that polling interval.

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

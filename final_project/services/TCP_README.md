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
- An invalid port value is rejected immediately, before any socket is opened,
  with a status message shown instead of a crash.

## EMGTCPClient

`EMGTCPClient` handles the client-side TCP connection and packet reconstruction.

### `__init__(host='localhost', port=12345)`

Initializes the client endpoint, byte buffers, decoded sample buffer, and packet
size configuration. Port validity is checked in `connect()`, not here.

The expected packet size is:

```text
32 channels x 18 samples x 8 bytes = 4608 bytes
```

### `_is_valid_port(port)`

Checks that `port` is an integer between 1 and 65535. Called at the start of
`connect()`, before any socket is created.

**Handles:** Handle invalid port input

### `connect()`

Validates the port first; an invalid port is rejected with a status message
before any socket is created. Otherwise, opens the TCP socket and switches it
to non-blocking mode. Non-blocking mode is important because socket reads
should never freeze the GUI. Connection failures (e.g. server not running)
are caught and reported via `status_updated` instead of raising.

**Handles:** Handle invalid port input, Handle server not running, Show
status messages in the GUI instead of crashing

### `receive_data()`

Drains all currently available bytes from the socket and appends them to the
internal byte buffer. It handles packet fragmentation and clumped packets by
extracting only complete 4608-byte frames.

If the server closes the connection, this method disconnects the client
cleanly. If a read error occurs instead (lost connection), it is caught,
reported via `status_updated`, and the client disconnects.

**Handles:** Handle lost TCP connection, Show status messages in the GUI
instead of crashing

### `get_latest_live_data()`

Returns all newly received packets since the previous call and advances the
live read pointer.

The returned array has shape:

```text
(32, N)
```

where `32` is the number of EMG channels and `N` is the number of samples
received during that polling interval.

If nothing new has arrived, this returns an empty `(32, 0)` array without
emitting `no_data_warning` — that's normal during polling, not an error.

### `get_all_offline_data()`

Returns the full historical packet buffer as one `(32, Total Samples)` array.
The current ViewModel stores its own immutable recording chunks for offline
processing, but this client method is still available on the service.

If no packets were recorded, it emits `no_data_warning` instead of returning
nothing silently.

**Handles:** Handle no data available

### `disconnect()`

Closes the active socket and resets the client connection state. Recorded
packets are intentionally preserved after disconnect so they remain available
for offline analysis and plotting. If the session recorded zero packets,
`no_data_warning` is emitted here too, in addition to the check already in
`get_all_offline_data()`.

**Handles:** Handle no data available, Show status messages in the GUI
instead of crashing

## Data Buffering Design (Runtime Flow)

Buffering is split between the TCP service and the ViewModel runtime path.

**Byte buffer** (`EMGTCPClient.byte_buffer`): Raw bytes received from the
socket accumulate here. `_extract_packets()` consumes complete 4608-byte frames
from the front and leaves any incomplete trailing bytes in place.

**Packet store** (`EMGTCPClient.all_packets`): Each reconstructed `(32, 18)`
frame is appended here by `_extract_packets()`. This list grows for the entire
duration of a recording session and is not truncated during streaming.

**Live read pointer** (`EMGTCPClient.live_pointer`): An index into `all_packets`.
`get_latest_live_data()` slices `all_packets[live_pointer:]`, advances the
pointer to the current end of the list, and returns only the frames added
since the previous poll.

**Live rolling display buffer** (`MainViewModel.live_raw_data`): The ViewModel
keeps the newest samples needed for real-time VisPy visualization with
`live_raw_data[:, -live_window_samples:]`.

**Full offline recording** (`MainViewModel._recording_chunks`): The ViewModel
stores immutable chunks of the received EMG history for offline Matplotlib
analysis.

**Offline access** (`EMGTCPClient.get_all_offline_data()`): Concatenates every
frame in `all_packets` into a single `(32, Total Samples)` array. The current
GUI uses the ViewModel recording chunks for offline plotting, but this service
method remains available.

**Reset** (`EMGTCPClient.clear_buffers()`): Clears `byte_buffer` and
`all_packets`, and resets `live_pointer` to zero so a new recording session
starts from a clean state.

## EMGTCPServer

`EMGTCPServer` is the built-in local demo server. It streams 32-channel EMG
packets to any connected local client.

It first tries to load the project-local demo recording:

```text
final_project/data/recording.pkl
```

If that file is not available, the server can still start and listen for
clients, but it does not send signal packets. In that case the GUI shows a
warning that the server is not sending data.

Again, this server is for local testing/demo. The main project requirement is
that the app can connect as a client to the provided exercise TCP server.

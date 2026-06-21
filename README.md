# MyoFlow EMG Reader

PySide6 desktop application for live TCP signal visualization and offline
signal inspection.

This project was built for the Applied Programming 2026 final project. The
application connects to the provided Exercise 5 TCP server, reconstructs streamed
EMG packets, visualizes the signal live with VisPy, and allows recorded data to
be inspected offline with Matplotlib.

## Team

Group number: Group01

| Member | Main responsibility |
| --- | --- |
| YU-HSUAN KUO | TCP communication, packet reconstruction, buffering, TCP error handling |
| Martin VOGEL | PySide6 GUI, live VisPy plotting, channel controls, all-channel view |
| Lan Luo | Signal processing modes, offline Matplotlib inspection, documentation |

## Main Features

- TCP client for the provided Exercise 5 server.
- Correct reconstruction of `32 x 18` `float64` packets.
- Live VisPy visualization with rolling time windows.
- Selectable EMG channels with channel buttons and channel ordering.
- `Plot all Channels` overview with all 32 channels displayed together.
- Signal modes for both live and offline plots:
  - `Original`
  - `RMS`
  - `Filtered`
- Offline Matplotlib inspection after data has been recorded.
- Time-window control for live and offline inspection.
- Local demo TCP server for development and presentations.
- MVVM-style separation between GUI, application state, TCP services, and signal
  processing helpers.
- Basic error/status messages for connection errors, invalid ports, missing
  data, and disconnects.

## Requirements

The project uses Python with the dependencies listed in `requirements.txt`:

```text
numpy
scipy
matplotlib
PySide6
vispy
```

Python 3.10 or newer is recommended.

## Installation

Clone the repository and enter the repository root:

```bash
git clone https://github.com/Luolan-AI/applied-programming-final-project.git
cd applied-programming-final-project
```

Install the dependencies with `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate the virtual environment with:

```bash
.venv\Scripts\activate
```

If you use `uv`, the equivalent setup is:

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

You can also launch directly with `uv` without permanently installing packages
into an activated environment:

```bash
uv run --with-requirements requirements.txt python final_project/main.py
```

## Running the Application

Start the GUI from the repository root:

```bash
python final_project/main.py
```

If you are using `uv`:

```bash
uv run python final_project/main.py
```

The main window is called `MyoFlow EMG Reader`.

## TCP Data Format

The application expects the same TCP packet format as Exercise 5:

```text
32 channels x 18 samples x float64
```

One complete packet contains:

```text
32 x 18 x 8 = 4608 bytes
```

The TCP client stores incoming bytes in a byte buffer and only decodes complete
4608-byte packets. This means fragmented TCP reads and multiple packets received
in one socket read are both handled correctly.

The GUI assumes the Exercise 5 sample rate of `2000 Hz` for time labels, rolling
windows, RMS window sizing, and filter parameters.

## Connecting to the Provided TCP Server

The intended final-project workflow is to use the provided Exercise 5 TCP server
as the data source.

1. Start the provided Exercise 5 TCP server outside this GUI.
2. Open this application.
3. Enter the server host in the `Host` field.
4. Enter the server port in the `TCP Port` field.
5. Click `Connect TCP Client`.
6. Live streaming starts automatically after a successful connection.
7. Click `Disconnect TCP Client` to stop the client connection.
8. The recorded signal remains available in the `Offline` tab.

The connect button only starts the client connection. It does not automatically
start the built-in demo server.

## Built-In Local Demo Server

The GUI also includes a local demo TCP server controlled by the
`Start Demo TCP Server` button. This server is included for development,
debugging, and presentations when the provided exercise server is not already
running.

The demo server streams data from:

```text
final_project/data/recording.pkl
```

This file is included in the repository so the GUI can be demonstrated locally.
If the file is missing, the demo server can still start and listen on the chosen
host/port, but it will not send signal data. The GUI shows a warning in this
case.

For requirement-focused testing, use the provided Exercise 5 TCP server. Treat
the built-in demo server only as a convenience feature.

## Live Plot Usage

The `Live` tab uses VisPy for real-time plotting.

Typical live workflow:

1. Connect to a TCP server.
2. Select one or more channels from the channel list on the left.
3. Choose a signal mode from `Signal Mode`.
4. Choose how many channel rows should be visible with `Visible Channels`.
5. Choose the live rolling window length with `Time Window`.
6. Use `Plot all Channels` to open the all-channel overview dialog.

The live plot contains:

- x-axis time labels in seconds
- y-axis amplitude labels
- a rolling time window
- selected-channel plotting
- stacked multi-channel plotting when more than one channel is selected
- all-channel overview plotting with vertical offsets

The channel controls support selecting, deselecting, selecting all channels, and
reordering channels for display.

## Offline Plot Usage

The `Offline` tab uses Matplotlib for inspection of recorded data. It becomes
useful after at least one TCP packet has been received.

The offline plot supports:

- selecting one or more recorded channels
- switching between `Original`, `RMS`, and `Filtered`
- inspecting the recorded signal over time
- horizontal time scrolling when a finite time window is selected
- vertical scrolling when more channels are selected than fit on screen

Offline plotting does not read directly from the TCP socket. It uses the data
already stored by the ViewModel during the live session.

## Signal Processing

Signal processing is implemented in:

```text
final_project/services/signal_processing.py
```

The same processing function is used for live VisPy data and offline Matplotlib
data.

### Original

`Original` returns a copy of the raw reconstructed EMG samples without additional
processing.

### RMS

`RMS` computes a moving root-mean-square envelope per channel.

Parameters:

```text
window length: 100 ms
sample rate:   2000 Hz
window size:   200 samples
```

The RMS window is calculated from the active sample rate, so the implementation
is time-based rather than hard-coded to a fixed sample count.

### Filtered

`Filtered` applies a Butterworth band-pass filter.

Parameters:

```text
filter type: Butterworth band-pass
order:       4
low cutoff:  20 Hz
high cutoff: 450 Hz
method:      scipy.signal.filtfilt
```

If SciPy is unavailable, the application falls back to a small NumPy-only
baseline-removal filter so the GUI can still launch. The intended and submitted
setup is the full `requirements.txt` installation with SciPy.

## Project Structure

```text
applied-programming-final-project/
├── README.md
├── requirements.txt
├── docs/
│   └── team_git_workflow.md
└── final_project/
    ├── main.py
    ├── data/
    │   ├── myoflow_logo.png
    │   ├── myoflow_logo_flat.png
    │   └── recording.pkl
    ├── models/
    ├── services/
    │   ├── TCP_client_service.py
    │   ├── TCP_server_service.py
    │   ├── TCP_README.md
    │   └── signal_processing.py
    ├── utils/
    ├── viewmodels/
    │   └── main_view_model.py
    └── views/
        ├── button_labels.py
        ├── channel_drag_and_drop_menue.py
        ├── main_view.py
        └── plotview.py
```

## MVVM Design

The project follows an MVVM-style structure.

### View Layer

Files:

```text
final_project/views/main_view.py
final_project/views/plotview.py
final_project/views/channel_drag_and_drop_menue.py
final_project/views/button_labels.py
```

Responsibilities:

- build the PySide6 interface
- display connection controls, channel controls, live tab, and offline tab
- draw live plots with VisPy
- draw offline plots with Matplotlib
- forward user actions to the ViewModel
- update widgets when the ViewModel emits Qt signals

The View does not open TCP sockets and does not reconstruct packets.

### ViewModel Layer

File:

```text
final_project/viewmodels/main_view_model.py
```

Responsibilities:

- store application state
- connect GUI actions to backend services
- manage selected channels, signal mode, time window, and status messages
- keep a rolling live buffer for display
- keep immutable recording chunks for offline inspection
- run TCP acquisition and offline processing on worker threads
- emit plot-ready data to the View

The ViewModel coordinates the application but delegates socket communication and
signal processing to service functions/classes.

### Service Layer

Files:

```text
final_project/services/TCP_client_service.py
final_project/services/TCP_server_service.py
final_project/services/signal_processing.py
```

Responsibilities:

- TCP socket connection and disconnect logic
- byte buffering and packet reconstruction
- conversion of packets into NumPy arrays
- local demo server streaming
- reusable RMS and filtering functions

### Models and Utilities

The `models/` and `utils/` packages are available for shared state and helpers.
The current implementation keeps most runtime state in the ViewModel and service
classes because the data flow is small and direct.

## Error Handling

The application is designed to avoid crashes for common problems:

- invalid TCP port values
- server not running
- connection failure
- server disconnect
- no data available for offline plotting
- invalid signal mode
- missing local demo recording file

Errors are shown as status messages in the GUI instead of uncaught exceptions.

## Additional TCP Notes

More detailed notes about the TCP client, packet size, local demo server, and
buffering flow are available in:

```text
final_project/services/TCP_README.md
```

## Development Workflow

The team used GitHub issues, feature branches, and pull requests to divide the
work. The workflow guide is stored in:

```text
docs/team_git_workflow.md
```

Recommended workflow:

1. Start from the latest `main`.
2. Create a feature branch for one task.
3. Commit the change.
4. Open a Pull Request into `main`.
5. Let at least one teammate review and test.
6. Merge after review.

## Verification Checklist

Before submission, the following checks should pass on a clean environment:

- dependencies install from `requirements.txt`
- `python final_project/main.py` launches the GUI
- the GUI can connect to the provided Exercise 5 TCP server
- live VisPy plot updates while streaming
- channel selection works
- `Original`, `RMS`, and `Filtered` modes work in live view
- `Plot all Channels` opens the all-channel overview
- disconnecting preserves the received recording
- the `Offline` tab can inspect recorded channels with Matplotlib
- invalid ports and missing/no-data states show status messages

## Notes for Grading

- The main required server source is the provided Exercise 5 TCP server.
- The built-in local TCP server is an optional demo helper.
- The TCP client expects `32 x 18 x float64` packets.
- The GUI uses VisPy for live plotting and Matplotlib for offline inspection.
- The code separates GUI, application state, TCP services, and signal processing
  according to an MVVM-style design.

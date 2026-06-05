# applied-programming-final-project

PySide6 desktop application for live TCP signal visualization and offline signal inspection.

## Team

Group number: Group01

| Member | Responsibility |
|---|---|
| YU-HSUAN KUO | TCP communication, packet reconstruction, buffering |
| Martin VOGEL | PySide6 GUI, VisPy live plotting, channel selection |
| Lan Luo | Signal processing, offline Matplotlib plot, documentation |

## Project Structure

```text
final_project/
├── main.py
├── models/
├── services/
├── utils/
├── viewmodels/
└── views/
```

The project follows an MVVM-style structure:

- `models/` stores data and backend state.
- `services/` contains reusable logic such as signal processing.
- `viewmodels/` connects GUI actions to model and service logic.
- `views/` contains PySide6 widgets and plotting UI.
- `utils/` contains shared constants and helper functions.

## Setup

Install the project dependencies with:

```bash
pip install -r requirements.txt
```

## Run

Start the application from the repository root:

```bash
python final_project/main.py
```

## Use

Open the app and keep `Host` as `localhost` unless you want to connect to a
server on another machine. Enter the server port and press `Start Server` to
launch the local TCP server from inside the GUI. Then press `Connect`; live
streaming starts automatically after a successful connection. Use `Disconnect`
to stop the client connection and keep the received data for offline inspection.
Use `Stop Server` when you no longer need the local TCP server.

The `Channel` control selects one of the 32 channels for the live VisPy plot.
`Signal Mode` switches the live and offline views between `Original`, `RMS`, and
`Filtered`. `Plot All Channels` opens a live overview dialog with all 32 channels
drawn together using vertical offsets. The `Offline` tab shows the recorded
selected channel with Matplotlib after streaming has stopped or whenever
`Update Offline Plot` is pressed.

Signal processing uses a 50-sample moving RMS window. Filtering uses a 4th-order
Butterworth band-pass filter from 20 Hz to 450 Hz at a 1000 Hz assumed sample
rate. If SciPy is not installed yet, the app falls back to a small NumPy-only
baseline-removal filter so the GUI can still launch, but the intended setup is
the full `requirements.txt` install.

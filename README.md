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

The intended project workflow is to connect this GUI to the provided exercise
TCP server:

1. Start the provided exercise TCP server outside this GUI.
2. Enter its host and port in the GUI.
3. Press `Connect TCP Client` to start live streaming.
4. Use `Disconnect TCP Client` to stop the client connection. The received data
   remains available in the `Offline` tab for inspection.

The GUI also includes a built-in local TCP demo server. The `Start Demo TCP
Server` button launches this local server on the selected host and port. This is
useful for development, debugging, or presenting the app without separately
launching the provided exercise server, but it is not the required
final-project server. The connect button does not start this demo server
automatically; start it explicitly only when you want the local demo workflow.

`Signal Mode` switches the live and offline views between `Original`, `RMS`, and
`Filtered`. Use the channel buttons to select which channels are shown, and use
`Visible Channels` to choose how many stacked channel rows fit before vertical
scrolling appears. `Plot all Channels` opens a live overview dialog. The
`Offline` tab shows the recorded selected channels and remains usable after TCP
disconnect.

Signal processing uses a 100 ms moving RMS window, corresponding to 200 samples
at the Exercise 5 sample rate of 2000 Hz. Filtering uses a 4th-order Butterworth
band-pass filter from 20 Hz to 450 Hz. If SciPy is not installed yet, the app
falls back to a small NumPy-only baseline-removal filter so the GUI can still
launch, but the intended setup is the full `requirements.txt` install.

See `final_project/services/TCP_README.md` for more detail about the TCP client,
the built-in local demo server, packet size, and packet reconstruction.

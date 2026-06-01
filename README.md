# applied-programming-final-project

PySide6 desktop application for live TCP signal visualization and offline signal inspection.

## Team

Group number: Group01

| Member | Responsibility |
|---|---|
| Person A | TCP communication, packet reconstruction, buffering |
| Person B | PySide6 GUI, VisPy live plotting, channel selection |
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

"""Main ViewModel for application-level state."""

from PySide6.QtCore import QObject


class MainViewModel(QObject):
    """Minimal ViewModel placeholder for the initial project skeleton."""

    def __init__(self) -> None:
        super().__init__()
        self.status_text = "Project skeleton ready."

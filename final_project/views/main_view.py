"""Main window for the final project application."""

from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget


class MainView(QMainWindow):
    """Minimal main window used by the initial project skeleton."""

    def __init__(self, view_model) -> None:
        super().__init__()

        self.view_model = view_model
        self.setWindowTitle("TCP Signal Visualization")
        self.resize(1000, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(12, 12, 12, 12)

        status_label = QLabel(self.view_model.status_text)
        layout.addWidget(status_label)

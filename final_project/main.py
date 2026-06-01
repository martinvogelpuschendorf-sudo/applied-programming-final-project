"""Application entry point for the final project."""

import sys

from PySide6.QtWidgets import QApplication

from viewmodels.main_view_model import MainViewModel
from views.main_view import MainView


def main() -> int:
    """Create and start the Qt application."""
    app = QApplication(sys.argv)

    view_model = MainViewModel()
    view = MainView(view_model)
    view.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

"""Drag-and-drop channel selector menu for EMG channel ordering."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QCursor, QDrag
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

try:
    from . import button_labels
except ImportError:
    from views import button_labels


class ClickableLabel(QLabel):
    """QLabel that emits a clicked signal."""

    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class ChannelButton(QPushButton):
    """Checkable channel button that starts an insertion-style drag."""

    MIME_TYPE = "application/x-emg-channel"

    def __init__(self, channel_index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.channel_index = channel_index
        self._drag_start_position = None
        self._drag_menu: ChannelDragAndDropMenu | None = None
        self.setAcceptDrops(True)

    def set_drag_menu(self, menu: "ChannelDragAndDropMenu") -> None:
        self._drag_menu = menu

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not event.buttons() & Qt.MouseButton.LeftButton or self._drag_start_position is None:
            super().mouseMoveEvent(event)
            return

        distance = (event.position().toPoint() - self._drag_start_position).manhattanLength()
        if distance < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData(self.MIME_TYPE, str(self.channel_index).encode("ascii"))
        drag.setMimeData(mime_data)

        drag_pixmap = self.grab()
        drag.setPixmap(drag_pixmap)
        drag.setHotSpot(event.position().toPoint())

        opacity = QGraphicsOpacityEffect(self)
        opacity.setOpacity(0.35)
        self.setGraphicsEffect(opacity)
        if self._drag_menu is not None:
            self._drag_menu.begin_drag(self.channel_index)
        drag.exec(Qt.DropAction.MoveAction)
        self.setGraphicsEffect(None)
        if self._drag_menu is not None:
            self._drag_menu.end_drag()

    def dragEnterEvent(self, event) -> None:
        if self._drag_menu is not None and event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self._drag_menu is not None and event.mimeData().hasFormat(self.MIME_TYPE):
            self._drag_menu.update_drop_position(self.mapTo(self._drag_menu, event.position().toPoint()))
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:
        if self._drag_menu is not None and event.mimeData().hasFormat(self.MIME_TYPE):
            source_channel = int(bytes(event.mimeData().data(self.MIME_TYPE)).decode("ascii"))
            self._drag_menu.complete_drop(source_channel)
            event.acceptProposedAction()
            return
        event.ignore()


class ChannelDragAndDropMenu(QWidget):
    """Vertical channel menu with insertion feedback while dragging."""

    channel_toggled = Signal(int, bool)
    reorder_requested = Signal(int, int)
    select_all_clicked = Signal()
    placeholder_clicked = Signal()

    def __init__(self, channel_count: int = 32, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.channel_order = list(range(channel_count))
        self.available_channel_count = 0
        self._drop_index = 0
        self._dragged_channel: int | None = None
        self._scroll_area: QScrollArea | None = None
        self._auto_scroll_margin = 42
        self._auto_scroll_step = 18

        self.channel_layout = QVBoxLayout(self)
        self.channel_layout.setContentsMargins(0, 0, 0, 0)
        self.channel_layout.setSpacing(5)

        self.message_label = ClickableLabel(button_labels.CHANNEL_SELECTOR_CONNECT_MESSAGE)
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.message_label.clicked.connect(self.placeholder_clicked)
        self.message_label.setStyleSheet(
            "QLabel {"
            " background: #ffffff;"
            " border: 1px solid #c6cbd1;"
            " border-radius: 4px;"
            " padding: 10px;"
            " color: #5f6368;"
            "}"
        )

        self.select_all_button = QPushButton(button_labels.SELECT_ALL_CHANNELS)
        self.select_all_button.setMinimumHeight(34)
        self.select_all_button.clicked.connect(self.select_all_clicked)

        self.drop_indicator = QFrame()
        self.drop_indicator.setFixedHeight(12)
        self.drop_indicator.setStyleSheet(
            "QFrame {"
            " background: #3A86FF;"
            " border: 1px solid #1f6fe5;"
            " border-radius: 6px;"
            " margin: 2px 8px;"
            "}"
        )
        self.drop_indicator.hide()

        self.channel_layout.addWidget(self.message_label)
        self.channel_layout.addWidget(self.select_all_button)
        self.channel_buttons: dict[int, ChannelButton] = {}
        for channel_index in range(channel_count):
            button = ChannelButton(channel_index)
            button.setText(
                button_labels.CHANNEL_BUTTON_TEMPLATE.format(channel_number=channel_index + 1)
            )
            button.setCheckable(True)
            button.setMinimumHeight(30)
            button.set_drag_menu(self)
            button.clicked.connect(
                lambda checked, index=channel_index: self.channel_toggled.emit(index, checked)
            )
            self.channel_buttons[channel_index] = button
            self.channel_layout.addWidget(button)
        self.channel_layout.addStretch(1)
        self.setAcceptDrops(True)

    def attach_scroll_area(self, scroll_area: QScrollArea) -> None:
        """Let the scroll viewport handle drops and edge auto-scrolling."""
        if self._scroll_area is not None:
            self._scroll_area.viewport().removeEventFilter(self)
        self._scroll_area = scroll_area
        self._scroll_area.viewport().setAcceptDrops(True)
        self._scroll_area.viewport().installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if (
            self._scroll_area is None
            or watched is not self._scroll_area.viewport()
            or event.type()
            not in (
                QEvent.Type.DragEnter,
                QEvent.Type.DragMove,
                QEvent.Type.Drop,
                QEvent.Type.DragLeave,
            )
        ):
            return super().eventFilter(watched, event)

        if event.type() == QEvent.Type.DragLeave:
            self.drop_indicator.hide()
            event.accept()
            return True

        if not event.mimeData().hasFormat(ChannelButton.MIME_TYPE):
            event.ignore()
            return True

        if event.type() == QEvent.Type.DragEnter:
            event.acceptProposedAction()
            return True

        menu_position = self.mapFrom(self._scroll_area.viewport(), event.position().toPoint())
        if event.type() == QEvent.Type.DragMove:
            self.update_drop_position(menu_position)
            event.acceptProposedAction()
            return True

        source_channel = int(bytes(event.mimeData().data(ChannelButton.MIME_TYPE)).decode("ascii"))
        self.update_drop_position(menu_position)
        self.complete_drop(source_channel)
        event.acceptProposedAction()
        return True

    def set_available_channels(self, count: int, is_connected: bool) -> None:
        """Show only the channels reported by the TCP stream."""
        self.available_channel_count = max(0, min(count, len(self.channel_buttons)))
        has_channels = self.available_channel_count > 0
        self.message_label.setVisible(not has_channels)
        self.message_label.setText(
            button_labels.CHANNEL_SELECTOR_WAITING_MESSAGE
            if is_connected
            else button_labels.CHANNEL_SELECTOR_CONNECT_MESSAGE
        )
        self.select_all_button.setVisible(has_channels)
        for channel_index, button in self.channel_buttons.items():
            button.setVisible(channel_index < self.available_channel_count)
            if channel_index >= self.available_channel_count:
                button.setChecked(False)
        self.rebuild_order()

    def set_channel_order(self, order: list[int]) -> None:
        self.channel_order = list(order)
        self.rebuild_order()

    def rebuild_order(self) -> None:
        """Rebuild button layout according to channel_order."""
        self.drop_indicator.hide()
        for channel_index in self.channel_order:
            button = self.channel_buttons[channel_index]
            self.channel_layout.removeWidget(button)
            self.channel_layout.insertWidget(self.channel_layout.count() - 1, button)

    def begin_drag(self, channel_index: int) -> None:
        self._dragged_channel = channel_index
        self._drop_index = self._visible_order().index(channel_index)

    def end_drag(self) -> None:
        self._dragged_channel = None
        self.drop_indicator.hide()
        self.channel_layout.removeWidget(self.drop_indicator)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(ChannelButton.MIME_TYPE):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(ChannelButton.MIME_TYPE):
            self.update_drop_position(event.position().toPoint())
            event.acceptProposedAction()
            return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self.drop_indicator.hide()
        event.accept()

    def dropEvent(self, event) -> None:
        if event.mimeData().hasFormat(ChannelButton.MIME_TYPE):
            source_channel = int(bytes(event.mimeData().data(ChannelButton.MIME_TYPE)).decode("ascii"))
            self.complete_drop(source_channel)
            event.acceptProposedAction()
            return
        event.ignore()

    def update_drop_position(self, local_position) -> None:
        """Move the insertion indicator to the nearest between-channel slot."""
        visible_order = self._visible_order()
        if not visible_order:
            return

        self._auto_scroll(local_position)
        y_position = local_position.y()
        drop_index = len(visible_order)
        for index, channel_index in enumerate(visible_order):
            button = self.channel_buttons[channel_index]
            if y_position < button.geometry().center().y():
                drop_index = index
                break

        self._drop_index = drop_index
        self._place_indicator(drop_index, visible_order)

    def complete_drop(self, source_channel: int) -> None:
        self.drop_indicator.hide()
        self.channel_layout.removeWidget(self.drop_indicator)
        self.reorder_requested.emit(source_channel, self._drop_index)

    def _place_indicator(self, drop_index: int, visible_order: list[int]) -> None:
        self.channel_layout.removeWidget(self.drop_indicator)
        if drop_index >= len(visible_order):
            layout_index = self.channel_layout.count() - 1
        else:
            layout_index = self.channel_layout.indexOf(self.channel_buttons[visible_order[drop_index]])
        self.channel_layout.insertWidget(layout_index, self.drop_indicator)
        self.drop_indicator.show()

    def _visible_order(self) -> list[int]:
        return [
            channel_index
            for channel_index in self.channel_order
            if channel_index < self.available_channel_count
        ]

    def _auto_scroll(self, local_position: QPoint) -> None:
        if self._scroll_area is None:
            return

        viewport = self._scroll_area.viewport()
        viewport_position = self.mapTo(viewport, local_position)
        scroll_bar = self._scroll_area.verticalScrollBar()
        if viewport_position.y() < self._auto_scroll_margin:
            scroll_bar.setValue(scroll_bar.value() - self._auto_scroll_step)
        elif viewport_position.y() > viewport.height() - self._auto_scroll_margin:
            scroll_bar.setValue(scroll_bar.value() + self._auto_scroll_step)

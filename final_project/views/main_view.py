"""Main PySide6 window for the final project."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QScrollBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from .channel_drag_and_drop_menue import ChannelButton, ChannelDragAndDropMenu
    from .plotview import (
        AllChannelsDialog,
        OfflineMatplotlibPlot,
        VisPySignalPlot,
        channel_color_rgba_css,
        channel_color_css,
    )
except ImportError:
    from views.channel_drag_and_drop_menue import ChannelButton, ChannelDragAndDropMenu
    from views.plotview import (
        AllChannelsDialog,
        OfflineMatplotlibPlot,
        VisPySignalPlot,
        channel_color_rgba_css,
        channel_color_css,
    )


class PlotScrollArea(QScrollArea):
    """Scroll area that lets plot canvases scroll with the mouse wheel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._plot_widget: QWidget | None = None
        self._wheel_widgets: list[QWidget] = []

    def set_plot_widget(self, plot_widget: QWidget, wheel_widgets: list[QWidget]) -> None:
        self._plot_widget = plot_widget
        self.setWidget(plot_widget)
        self._wheel_widgets = [plot_widget, *wheel_widgets]
        for widget in self._wheel_widgets:
            widget.installEventFilter(self)
        self._sync_plot_viewport_height()

    def eventFilter(self, watched, event) -> bool:
        if watched in self._wheel_widgets and event.type() == QEvent.Type.Wheel:
            if self.verticalScrollBar().maximum() > 0:
                self._scroll_from_wheel_event(event)
                return True
        return super().eventFilter(watched, event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_plot_viewport_height()

    def _sync_plot_viewport_height(self) -> None:
        if self._plot_widget is not None and hasattr(
            self._plot_widget,
            "set_visible_channel_viewport_height",
        ):
            self._plot_widget.set_visible_channel_viewport_height(self.viewport().height())

    def _scroll_from_wheel_event(self, event) -> None:
        pixel_delta = event.pixelDelta().y()
        if pixel_delta:
            scroll_delta = pixel_delta
        else:
            scroll_delta = event.angleDelta().y()
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() - scroll_delta)
        event.accept()


class MainView(QMainWindow):
    """Main PySide6 GUI for live TCP signal visualization.

    The View owns widgets and plot surfaces only. It does not read from sockets
    and does not process signals itself; it forwards user actions to the
    ViewModel and redraws when the ViewModel emits data.
    """

    def __init__(self, view_model) -> None:
        super().__init__()

        # Keep a reference to the ViewModel so button callbacks can invoke
        # application actions such as "start server" and "change channel".
        self.view_model = view_model

        # Cache the latest live data so the all-channel dialog can be opened at
        # any time without waiting for another TCP packet.
        self.latest_all_channels = np.empty((32, 0), dtype=np.float64)
        self.latest_single_channel = np.empty(0, dtype=np.float64)
        self.current_time = 0.0
        self.selected_channel_indices: list[int] = []
        self.channel_buttons: dict[int, ChannelButton] = {}
        self.channel_order = list(range(32))
        self.available_channel_count = 0
        self._is_client_connected = False
        self._is_server_running = False
        self._offline_uses_total_time_window = True
        self._offline_scroll_syncing = False

        self.setWindowTitle("MyoFlow EMG Reader")
        self.resize(1200, 820)

        # Plot widgets live in plotview.py. Keeping them separate makes this
        # file mostly about layout and user interaction.
        self.single_plot = VisPySignalPlot("Selected Channel")
        self.all_channels_plot = VisPySignalPlot("All Channels")
        self.offline_plot = OfflineMatplotlibPlot()
        self.all_channels_dialog = AllChannelsDialog(self.all_channels_plot, self)
        self.offline_refresh_timer = QTimer(self)
        self.offline_refresh_timer.setInterval(1000)
        self.offline_refresh_timer.timeout.connect(self._refresh_offline_plot)
        self.live_redraw_timer = QTimer(self)
        self.live_redraw_timer.setSingleShot(True)
        self.live_redraw_timer.setInterval(75)
        self.live_redraw_timer.timeout.connect(self._redraw_live_plots)

        self._build_ui()
        self._connect_signals()
        self._set_connected_state(False)
        self._set_server_running_state(False)
        self.status_label.setText(self.view_model.status_text)

    def _build_ui(self) -> None:
        """Create all Qt widgets and place them in the main window."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(10)

        # Connection row: one host/port pair is shared by both the built-in
        # local server and the TCP client. This avoids mismatched ports.
        connection_layout = QHBoxLayout()
        connection_layout.setSpacing(8)
        logo_label = QLabel()
        logo_path = Path(__file__).resolve().parents[1] / "data" / "myoflow_logo_flat.png"
        logo_pixmap = QPixmap(str(logo_path))
        if not logo_pixmap.isNull():
            logo_height = 128
            logo_width = round(logo_pixmap.width() * logo_height / logo_pixmap.height())
            logo_label.setPixmap(
                logo_pixmap.scaled(
                    logo_width,
                    logo_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            logo_label.setFixedSize(logo_width, logo_height)
        else:
            logo_label.setFixedSize(128, 128)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.host_input = QLineEdit("localhost")
        self.port_input = QLineEdit("12345")
        self.host_input.setFixedWidth(130)
        self.port_input.setFixedWidth(130)
        self.start_server_button = QPushButton("Start TCP server")
        self.start_server_button.setFixedSize(130, 86)
        self.connect_button = QPushButton("Connect\nto TCP server")
        self.connect_button.setFixedSize(130, 86)
        self.connection_info_label = QLabel()
        self.connection_info_label.setMinimumWidth(220)
        self.connection_info_label.setMinimumHeight(86)
        self.connection_info_label.setStyleSheet(
            "QLabel {"
            " background: #ffffff;"
            " border: 1px solid #c6cbd1;"
            " border-radius: 4px;"
            " padding: 6px 8px;"
            " color: #202124;"
            "}"
        )

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        form.addRow("Host", self.host_input)
        form.addRow("TCP Port", self.port_input)

        right_connection_layout = QHBoxLayout()
        right_connection_layout.setSpacing(8)
        right_connection_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        right_connection_layout.addLayout(form)
        right_connection_layout.addWidget(self.start_server_button, alignment=Qt.AlignmentFlag.AlignTop)
        right_connection_layout.addWidget(self.connect_button, alignment=Qt.AlignmentFlag.AlignTop)
        right_connection_layout.addWidget(self.connection_info_label, alignment=Qt.AlignmentFlag.AlignTop)

        # Plot controls row. Multiple live and offline channels are selected
        # with the shared left-side button column.
        controls_layout = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Original", "RMS", "Filtered"])
        self.mode_combo.setCurrentText("Filtered")
        self.visible_channels_combo = QComboBox()
        self.visible_channels_combo.addItems(["1", "2", "4", "6", "8", "12", "16", "All"])
        self.visible_channels_combo.setCurrentText("4")
        self.visible_channels_combo.setFixedWidth(72)
        self.time_window_combo = QComboBox()
        self.time_window_combo.addItems(["5 s", "10 s", "20 s", "30 s", "60 s"])
        self.time_window_combo.setCurrentText("10 s")
        self.time_window_combo.setFixedWidth(76)
        self.plot_all_button = QPushButton("Plot All Channels")

        controls_layout.addStretch(1)
        controls_layout.addWidget(QLabel("Signal Mode"))
        controls_layout.addWidget(self.mode_combo)
        controls_layout.addWidget(QLabel("Visible channels"))
        controls_layout.addWidget(self.visible_channels_combo)
        controls_layout.addWidget(QLabel("Time window"))
        controls_layout.addWidget(self.time_window_combo)
        controls_layout.addWidget(self.plot_all_button)

        right_header_layout = QVBoxLayout()
        right_header_layout.setSpacing(8)
        right_header_layout.addLayout(right_connection_layout)
        right_header_layout.addLayout(controls_layout)

        connection_layout.addWidget(logo_label)
        connection_layout.addStretch(1)
        connection_layout.addLayout(right_header_layout)
        root_layout.addLayout(connection_layout)

        self.channel_scroll = QScrollArea()
        self.channel_scroll.setWidgetResizable(True)
        self.channel_scroll.setFixedWidth(170)
        self.channel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.channel_drag_menu = ChannelDragAndDropMenu(channel_count=32)
        self.channel_drag_menu.channel_toggled.connect(self._channel_button_clicked)
        self.channel_drag_menu.reorder_requested.connect(self._move_channel_to_position)
        self.channel_drag_menu.select_all_clicked.connect(self._toggle_all_channels)
        self.channel_drag_menu.placeholder_clicked.connect(self._channel_placeholder_clicked)
        self.channel_selector_message = self.channel_drag_menu.message_label
        self.select_all_button = self.channel_drag_menu.select_all_button
        self.channel_buttons = self.channel_drag_menu.channel_buttons
        self.channel_scroll.setWidget(self.channel_drag_menu)
        self.channel_drag_menu.attach_scroll_area(self.channel_scroll)
        self._sync_available_channel_controls()

        # The live tab uses VisPy for fast updates; the offline tab uses
        # Matplotlib because it is convenient for static inspection.
        self.tabs = QTabWidget()
        live_tab = QWidget()
        live_layout = QHBoxLayout(live_tab)
        live_layout.setContentsMargins(0, 0, 0, 0)
        live_layout.setSpacing(8)
        self.live_plot_scroll = PlotScrollArea()
        self.live_plot_scroll.setWidgetResizable(True)
        self.live_plot_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.live_plot_scroll.set_plot_widget(self.single_plot, [self.single_plot.canvas.native])
        live_layout.addWidget(self.live_plot_scroll, stretch=1)
        self._refresh_channel_button_styles()
        self.tabs.addTab(live_tab, "Live")

        offline_tab = QWidget()
        offline_layout = QVBoxLayout(offline_tab)
        offline_layout.setContentsMargins(0, 0, 0, 0)
        self.offline_plot_scroll = PlotScrollArea()
        self.offline_plot_scroll.setWidgetResizable(True)
        self.offline_plot_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.offline_plot_scroll.set_plot_widget(self.offline_plot, [self.offline_plot.canvas])
        offline_layout.addWidget(self.offline_plot_scroll)
        self.offline_time_scroll = QScrollBar(Qt.Orientation.Horizontal)
        self.offline_time_scroll.setVisible(False)
        offline_layout.addWidget(self.offline_time_scroll)
        self.tabs.addTab(offline_tab, "Offline")
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        content_layout.addWidget(self.channel_scroll)
        content_layout.addWidget(self.tabs, stretch=1)
        root_layout.addLayout(content_layout, stretch=1)

        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 0, 0, 0)
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.copyright_label = QLabel("© Luo Lan, YU-HSUAN KUO, Martin Vogel")
        self.copyright_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.copyright_label.setStyleSheet("QLabel { color: #5f6368; font-size: 10px; }")
        footer_layout.addWidget(self.status_label, stretch=1)
        footer_layout.addWidget(self.copyright_label)
        root_layout.addLayout(footer_layout)

    def _connect_signals(self) -> None:
        """Connect Qt widget signals to ViewModel actions and redraw slots."""
        # User actions: buttons and controls call ViewModel methods.
        self.start_server_button.clicked.connect(self._toggle_server_requested)
        self.connect_button.clicked.connect(self._toggle_connection_requested)
        self.mode_combo.currentTextChanged.connect(self.view_model.set_signal_mode)
        self.visible_channels_combo.currentTextChanged.connect(self._visible_channel_limit_changed)
        self.time_window_combo.currentTextChanged.connect(self._time_window_changed)
        self.offline_time_scroll.valueChanged.connect(self._offline_time_scroll_changed)
        self.plot_all_button.clicked.connect(self._show_all_channels)
        self.tabs.currentChanged.connect(self._tab_changed)

        # ViewModel updates: state changes update labels/buttons/plots.
        self.view_model.status_changed.connect(self.status_label.setText)
        self.view_model.connection_changed.connect(self._set_connected_state)
        self.view_model.server_running_changed.connect(self._set_server_running_state)
        self.view_model.live_data_changed.connect(self._update_live_plots)
        self.view_model.offline_data_changed.connect(self._update_offline_plot)

    def _toggle_server_requested(self) -> None:
        """Start or stop the local TCP server from one stateful button."""
        if self._is_server_running:
            self.view_model.stop_tcp_server()
        else:
            self.view_model.start_tcp_server(self.host_input.text(), self.port_input.text())

    def _toggle_connection_requested(self) -> None:
        """Connect or disconnect the TCP client from one stateful button."""
        if self._is_client_connected:
            self.view_model.disconnect_from_server()
        else:
            self._start_server_then_connect()

    def _channel_placeholder_clicked(self) -> None:
        """Start the local server and connect when the empty channel panel is clicked."""
        if not self._is_client_connected:
            self._start_server_then_connect()

    def _start_server_then_connect(self) -> None:
        """Ensure the local TCP server is running before connecting the client."""
        if self._is_server_running:
            self.view_model.connect_to_server(self.host_input.text(), self.port_input.text())
            return

        self.view_model.start_tcp_server(self.host_input.text(), self.port_input.text())
        QTimer.singleShot(
            150,
            lambda: self.view_model.connect_to_server(
                self.host_input.text(),
                self.port_input.text(),
            )
            if self._is_server_running and not self._is_client_connected
            else None,
        )

    def _channel_button_clicked(self, channel_index: int, checked: bool) -> None:
        """Toggle a live channel button and keep selected rows in click order."""
        if checked and channel_index not in self.selected_channel_indices:
            self.selected_channel_indices.append(channel_index)
        elif not checked and channel_index in self.selected_channel_indices:
            self.selected_channel_indices.remove(channel_index)

        self._refresh_channel_button_styles([channel_index])
        if self.selected_channel_indices:
            self.offline_plot.set_channel(self.selected_channel_indices[-1])
        self._schedule_live_redraw()
        if self._offline_tab_is_visible():
            self._refresh_offline_plot()

    def _toggle_all_channels(self) -> None:
        """Select or deselect every currently available EMG channel."""
        available_indices = list(range(self.available_channel_count))
        if available_indices and set(self.selected_channel_indices) == set(available_indices):
            self.selected_channel_indices.clear()
        else:
            self.selected_channel_indices = available_indices

        for channel_index, button in self.channel_buttons.items():
            button.setChecked(channel_index in self.selected_channel_indices)

        self._refresh_channel_button_styles()
        self._update_select_all_button()
        self._schedule_live_redraw()
        if self._offline_tab_is_visible():
            self._refresh_offline_plot()

    def _refresh_channel_button_styles(self, channel_indices: list[int] | None = None) -> None:
        """Color channel buttons like their matching plot lines."""
        indices = self.channel_buttons.keys() if channel_indices is None else channel_indices
        for channel_index in indices:
            button = self.channel_buttons[channel_index]
            color = channel_color_css(channel_index)
            active_fill = self._blend_with_white(channel_index, 0.45)
            if button is self.select_all_button:
                continue
            if button.isChecked():
                button.setStyleSheet(
                    "QPushButton {"
                    f" color: {color};"
                    " font-weight: 700;"
                    f" border: 2px solid {color};"
                    f" background: {active_fill};"
                    " border-radius: 4px;"
                    " padding: 4px 6px;"
                    "}"
                )
            else:
                button.setStyleSheet(
                    "QPushButton {"
                    f" color: {color};"
                    " font-weight: 600;"
                    " border: 1px solid #c6cbd1;"
                    " background: #ffffff;"
                    " border-radius: 4px;"
                    " padding: 4px 6px;"
                    "}"
                    "QPushButton:hover { background: #ffffff; }"
                )
            button.update()
        self._update_select_all_button()

    def _clear_channel_selection(self) -> None:
        """Deactivate all channel buttons and reset the live selection."""
        self.selected_channel_indices.clear()
        for button in self.channel_buttons.values():
            button.setChecked(False)
        self._refresh_channel_button_styles()

    def _sync_available_channel_controls(self) -> None:
        """Show selector controls for channels that exist in the TCP stream."""
        self.channel_drag_menu.set_available_channels(
            self.available_channel_count,
            self._is_client_connected,
        )
        self.selected_channel_indices = [
            channel_index
            for channel_index in self.selected_channel_indices
            if channel_index < self.available_channel_count
        ]
        if (
            self._is_client_connected
            and self.available_channel_count > 0
            and not self.selected_channel_indices
        ):
            self.selected_channel_indices = list(range(min(4, self.available_channel_count)))
        for channel_index, button in self.channel_buttons.items():
            button.setChecked(channel_index in self.selected_channel_indices)
        self._refresh_channel_button_styles()

    def _update_select_all_button(self) -> None:
        """Style and label the bulk selection control."""
        available_indices = set(range(self.available_channel_count))
        all_selected = bool(available_indices) and set(self.selected_channel_indices) == available_indices
        self.select_all_button.setText("Deselect all" if all_selected else "Select all")
        self.select_all_button.setStyleSheet(
            "QPushButton {"
            " color: #202124;"
            " font-weight: 700;"
            " border: 2px solid #5f6368;"
            " background: #edf0f2;"
            " border-radius: 4px;"
            " padding: 5px 6px;"
            "}"
            "QPushButton:hover { background: #e1e5e8; }"
        )

    def _update_connection_info(self) -> None:
        """Show the current TCP endpoint and measured stream metadata."""
        if not self._is_client_connected:
            self.connection_info_label.setText(
                "Connected to: --\n"
                "Channels: --\n"
                "Sampling rate: --\n"
                "Time Recorded: --"
            )
            return

        host = self.view_model.tcp_client.host
        port = self.view_model.tcp_client.port
        has_received_samples = (
            self.latest_all_channels.ndim == 2 and self.latest_all_channels.shape[1] > 0
        )
        channel_text = str(self.latest_all_channels.shape[0]) if has_received_samples else "--"
        sample_rate = getattr(self.view_model, "sample_rate", self.single_plot.sample_rate)
        self.connection_info_label.setText(
            f"Connected to: {host}:{port}\n"
            f"Channels: {channel_text}\n"
            f"Sampling rate: {sample_rate:g} Hz\n"
            f"Time Recorded: {self.current_time:.1f} s"
        )

    def _blend_with_white(self, channel_index: int, opacity: float) -> str:
        """Return the channel color composited over white for dark-mode-safe fills."""
        rgba_text = channel_color_rgba_css(channel_index, opacity)
        red, green, blue = [
            int(part.strip())
            for part in rgba_text.removeprefix("rgba(").removesuffix(")").split(",")[:3]
        ]
        blended = [
            round(component * opacity + 255 * (1.0 - opacity))
            for component in (red, green, blue)
        ]
        return f"rgb({blended[0]}, {blended[1]}, {blended[2]})"

    def _ordered_selected_channels(self) -> list[int]:
        """Return selected channels in the current button/display order."""
        selected = set(self.selected_channel_indices)
        return [
            channel_index
            for channel_index in self.channel_order
            if channel_index in selected and channel_index < self.available_channel_count
        ]

    def _move_channel_to_position(self, source_channel: int, insertion_index: int) -> None:
        """Move a channel to the insertion slot shown by the drag menu."""
        visible_order = [
            channel_index
            for channel_index in self.channel_order
            if channel_index < self.available_channel_count
        ]
        if source_channel not in visible_order:
            return

        old_visible_index = visible_order.index(source_channel)
        adjusted_index = insertion_index
        if old_visible_index < adjusted_index:
            adjusted_index -= 1

        self.channel_order.remove(source_channel)
        remaining_visible_order = [
            channel_index
            for channel_index in self.channel_order
            if channel_index < self.available_channel_count
        ]
        if adjusted_index >= len(remaining_visible_order):
            visible_positions = [
                self.channel_order.index(channel_index)
                for channel_index in remaining_visible_order
            ]
            insert_position = max(visible_positions) + 1 if visible_positions else 0
        else:
            target_channel = remaining_visible_order[adjusted_index]
            insert_position = self.channel_order.index(target_channel)

        self.channel_order.insert(insert_position, source_channel)
        self.channel_drag_menu.set_channel_order(self.channel_order)
        self._schedule_live_redraw()
        if self._offline_tab_is_visible():
            self._refresh_offline_plot()

    def _visible_channel_limit(self) -> int | None:
        text = self.visible_channels_combo.currentText()
        if text == "All":
            return None
        return int(text)

    def _visible_channel_limit_changed(self) -> None:
        """Apply the stacked-channel viewport limit to live and offline plots."""
        limit = self._visible_channel_limit()
        self.single_plot.set_visible_channel_limit(limit)
        self.offline_plot.set_visible_channel_limit(limit)
        self._schedule_live_redraw()
        if self._offline_tab_is_visible():
            self._refresh_offline_plot()

    def _time_window_seconds(self) -> float:
        return float(self.time_window_combo.currentText().removesuffix(" s"))

    def _time_window_changed(self) -> None:
        """Apply the selected time span to live, all-channel, and offline plots."""
        seconds = self._time_window_seconds()
        self.single_plot.set_visible_duration_seconds(seconds)
        self.all_channels_plot.set_visible_duration_seconds(seconds)
        self.view_model.set_live_window_seconds(seconds)
        self._offline_uses_total_time_window = False
        self.offline_plot.set_visible_duration_seconds(seconds)
        self.offline_plot.set_visible_window_start_seconds(0.0)
        self.offline_time_scroll.setValue(0)
        self._schedule_live_redraw()
        if self.all_channels_dialog.isVisible():
            self._redraw_all_channels_dialog()
        if self._offline_tab_is_visible():
            self._refresh_offline_plot()

    def _offline_time_scroll_changed(self, value: int) -> None:
        """Scroll the finite offline time window through the recording."""
        if self._offline_scroll_syncing:
            return
        self.offline_plot.set_visible_window_start_seconds(value / 1000.0)
        if self._offline_tab_is_visible():
            self._refresh_offline_plot()

    def _redraw_live_plots(self) -> None:
        """Redraw live plots from cached ViewModel data."""
        self.single_plot.plot_selected_channels(
            self.latest_all_channels,
            self._ordered_selected_channels(),
            self.current_time,
            mode=self.mode_combo.currentText(),
        )
        if self.all_channels_dialog.isVisible():
            self.all_channels_plot.plot_all_channels(
                self.latest_all_channels,
                self.current_time,
                mode=self.mode_combo.currentText(),
            )

    def _schedule_live_redraw(self) -> None:
        """Coalesce expensive plot redraws so button clicks stay responsive."""
        if not self.live_redraw_timer.isActive():
            self.live_redraw_timer.start()

    def _set_connected_state(self, is_connected: bool) -> None:
        """Enable/disable client buttons based on connection state."""
        self._is_client_connected = is_connected
        self.connect_button.setText(
            "Disconnect\nfrom TCP server" if is_connected else "Connect\nto TCP server"
        )
        if not is_connected:
            self.offline_refresh_timer.stop()
            self.available_channel_count = 0
            self.latest_all_channels = np.empty((32, 0), dtype=np.float64)
            self.latest_single_channel = np.empty(0, dtype=np.float64)
            self.current_time = 0.0
            self._clear_channel_selection()
            self._sync_available_channel_controls()
            self._schedule_live_redraw()
            self.offline_plot.show_empty("No recorded data yet.")
            self.offline_time_scroll.setVisible(False)
        else:
            self._sync_available_channel_controls()
        self._refresh_host_port_state()
        self._update_connection_info()

    def _set_server_running_state(self, is_running: bool) -> None:
        """Enable/disable server buttons based on local server state."""
        self._is_server_running = is_running
        self.start_server_button.setText("Stop TCP server" if is_running else "Start TCP server")
        self._refresh_host_port_state()

    def _refresh_host_port_state(self) -> None:
        """Prevent endpoint edits while either side is using the endpoint."""
        can_edit_endpoint = not self._is_client_connected and not self._is_server_running
        self.host_input.setEnabled(can_edit_endpoint)
        self.port_input.setEnabled(can_edit_endpoint)

    def _update_live_plots(
        self,
        all_channels: object,
        selected_channel: object,
        current_time: float = 0.0,
    ) -> None:
        """Receive processed data from the ViewModel and redraw live plots.

        The ViewModel sends both the full 32-channel buffer and the currently
        selected channel. The GUI adds display-only information here, such as
        the channel number shown in the plot title.
        """
        self.latest_all_channels = np.asarray(all_channels)
        self.latest_single_channel = np.asarray(selected_channel)
        self.current_time = current_time
        if self.latest_all_channels.ndim == 2 and self.latest_all_channels.shape[1] > 0:
            channel_count = self.latest_all_channels.shape[0]
            if channel_count != self.available_channel_count:
                self.available_channel_count = channel_count
                self._sync_available_channel_controls()
        self._update_connection_info()
        self._schedule_live_redraw()

    def _show_all_channels(self) -> None:
        """Open the all-channel overview using the latest cached live data."""
        self.all_channels_dialog.show()
        self.all_channels_dialog.raise_()
        self.all_channels_dialog.activateWindow()
        QTimer.singleShot(75, self._redraw_all_channels_dialog)

    def _redraw_all_channels_dialog(self) -> None:
        """Draw the all-channel overview after the dialog has responded."""
        self.all_channels_plot.plot_all_channels(
            self.latest_all_channels,
            getattr(self, "current_time", 0.0),
            mode=self.mode_combo.currentText(),
        )

    def _update_offline_plot(self, data: object) -> None:
        """Redraw the Matplotlib offline plot for the selected channel/mode."""
        offline_data = np.asarray(data)
        self._apply_offline_time_window()
        self.offline_plot.plot(
            offline_data,
            self.mode_combo.currentText(),
            self._ordered_selected_channels(),
        )
        self._sync_offline_time_scroll(offline_data)

    def _tab_changed(self, index: int) -> None:
        """Refresh offline data when entering/leaving the Offline tab."""
        if self.tabs.tabText(index) == "Offline":
            self._refresh_offline_plot()
            self.offline_refresh_timer.start()
        else:
            self.offline_refresh_timer.stop()

    def _offline_tab_is_visible(self) -> bool:
        return self.tabs.currentWidget() is not None and self.tabs.tabText(self.tabs.currentIndex()) == "Offline"

    def _refresh_offline_plot(self) -> None:
        """Redraw offline plots from the recorded per-channel signal."""
        offline_data = self.view_model.processed_recording()
        self._apply_offline_time_window()
        self.offline_plot.plot(
            offline_data,
            self.mode_combo.currentText(),
            self._ordered_selected_channels(),
        )
        self._sync_offline_time_scroll(offline_data)

    def _apply_offline_time_window(self) -> None:
        if self._offline_uses_total_time_window:
            self.offline_plot.set_visible_duration_seconds(None)
        else:
            self.offline_plot.set_visible_duration_seconds(self._time_window_seconds())

    def _sync_offline_time_scroll(self, data: object) -> None:
        data = np.asarray(data)
        duration_seconds = data.shape[1] / self.offline_plot.sample_rate if data.ndim == 2 else 0.0
        window_seconds = self.offline_plot.visible_duration_seconds
        should_scroll = (
            not self._offline_uses_total_time_window
            and window_seconds is not None
            and duration_seconds > window_seconds
        )
        self.offline_time_scroll.setVisible(should_scroll)
        if not should_scroll:
            return

        max_start_ms = max(0, round((duration_seconds - window_seconds) * 1000))
        current_start_ms = min(
            max_start_ms,
            round(self.offline_plot.visible_window_start_seconds * 1000),
        )
        self._offline_scroll_syncing = True
        self.offline_time_scroll.setRange(0, max_start_ms)
        self.offline_time_scroll.setPageStep(max(1, round(window_seconds * 1000)))
        self.offline_time_scroll.setSingleStep(250)
        self.offline_time_scroll.setValue(current_start_ms)
        self._offline_scroll_syncing = False

    def closeEvent(self, event) -> None:
        """Clean up sockets when the user closes the main window."""
        self.offline_refresh_timer.stop()
        self.live_redraw_timer.stop()
        self.view_model.disconnect_from_server(announce=False)
        self.view_model.stop_tcp_server()
        super().closeEvent(event)

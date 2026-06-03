"""Main PySide6 window for the final project."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from .plotview import AllChannelsDialog, OfflineMatplotlibPlot, VisPySignalPlot
except ImportError:
    from views.plotview import AllChannelsDialog, OfflineMatplotlibPlot, VisPySignalPlot


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
        self._is_client_connected = False
        self._is_server_running = False

        self.setWindowTitle("TCP Signal Visualization")
        self.resize(1200, 820)

        # Plot widgets live in plotview.py. Keeping them separate makes this
        # file mostly about layout and user interaction.
        self.single_plot = VisPySignalPlot("Selected Channel")
        self.all_channels_plot = VisPySignalPlot("All Channels")
        self.offline_plot = OfflineMatplotlibPlot()
        self.all_channels_dialog = AllChannelsDialog(self.all_channels_plot, self)

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
        self.host_input = QLineEdit("localhost")
        self.port_input = QLineEdit("12345")
        self.start_server_button = QPushButton("Start Server")
        self.stop_server_button = QPushButton("Stop Server")
        self.connect_button = QPushButton("Connect")
        self.disconnect_button = QPushButton("Disconnect")

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.addRow("Host", self.host_input)
        form.addRow("TCP Port", self.port_input)
        connection_layout.addLayout(form, stretch=1)
        connection_layout.addWidget(self.start_server_button)
        connection_layout.addWidget(self.stop_server_button)
        connection_layout.addWidget(self.connect_button)
        connection_layout.addWidget(self.disconnect_button)
        root_layout.addLayout(connection_layout)

        # Plot controls row. Channel changes are routed through the ViewModel so
        # the selected channel is consistent for live and offline views.
        controls_layout = QHBoxLayout()
        self.channel_spinbox = QSpinBox()
        self.channel_spinbox.setRange(1, 32)
        self.channel_spinbox.setValue(1)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Original", "RMS", "Filtered"])
        self.plot_all_button = QPushButton("Plot All Channels")
        self.offline_button = QPushButton("Update Offline Plot")

        controls_layout.addWidget(QLabel("Channel"))
        controls_layout.addWidget(self.channel_spinbox)
        controls_layout.addWidget(QLabel("Signal Mode"))
        controls_layout.addWidget(self.mode_combo)
        controls_layout.addStretch(1)
        controls_layout.addWidget(self.plot_all_button)
        controls_layout.addWidget(self.offline_button)
        root_layout.addLayout(controls_layout)

        # The live tab uses VisPy for fast updates; the offline tab uses
        # Matplotlib because it is convenient for static inspection.
        self.tabs = QTabWidget()
        live_tab = QWidget()
        live_layout = QVBoxLayout(live_tab)
        live_layout.setContentsMargins(0, 0, 0, 0)
        live_layout.addWidget(self.single_plot)
        self.tabs.addTab(live_tab, "Live")

        offline_tab = QWidget()
        offline_layout = QVBoxLayout(offline_tab)
        offline_layout.setContentsMargins(0, 0, 0, 0)
        offline_layout.addWidget(self.offline_plot)
        self.tabs.addTab(offline_tab, "Offline")
        root_layout.addWidget(self.tabs, stretch=1)

        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root_layout.addWidget(self.status_label)

    def _connect_signals(self) -> None:
        """Connect Qt widget signals to ViewModel actions and redraw slots."""
        # User actions: buttons and controls call ViewModel methods.
        self.start_server_button.clicked.connect(self._start_server_requested)
        self.stop_server_button.clicked.connect(self.view_model.stop_tcp_server)
        self.connect_button.clicked.connect(self._connect_requested)
        self.disconnect_button.clicked.connect(self.view_model.disconnect_from_server)
        self.channel_spinbox.valueChanged.connect(self._channel_changed)
        self.mode_combo.currentTextChanged.connect(self.view_model.set_signal_mode)
        self.plot_all_button.clicked.connect(self._show_all_channels)
        self.offline_button.clicked.connect(self.view_model.request_offline_plot)

        # ViewModel updates: state changes update labels/buttons/plots.
        self.view_model.status_changed.connect(self.status_label.setText)
        self.view_model.connection_changed.connect(self._set_connected_state)
        self.view_model.server_running_changed.connect(self._set_server_running_state)
        self.view_model.live_data_changed.connect(self._update_live_plots)
        self.view_model.offline_data_changed.connect(self._update_offline_plot)

    def _start_server_requested(self) -> None:
        """Start the local TCP server using the current host/port fields."""
        self.view_model.start_tcp_server(self.host_input.text(), self.port_input.text())

    def _connect_requested(self) -> None:
        """Connect the TCP client using the current host/port fields."""
        self.view_model.connect_to_server(self.host_input.text(), self.port_input.text())

    def _channel_changed(self, channel_number: int) -> None:
        """Update both live and offline selected-channel state."""
        self.offline_plot.set_channel(channel_number - 1)
        self.view_model.set_channel(channel_number)

    def _set_connected_state(self, is_connected: bool) -> None:
        """Enable/disable client buttons based on connection state."""
        self._is_client_connected = is_connected
        self.connect_button.setEnabled(not is_connected)
        self.disconnect_button.setEnabled(is_connected)
        self._refresh_host_port_state()

    def _set_server_running_state(self, is_running: bool) -> None:
        """Enable/disable server buttons based on local server state."""
        self._is_server_running = is_running
        self.start_server_button.setEnabled(not is_running)
        self.stop_server_button.setEnabled(is_running)
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
        self.single_plot.plot_single_channel(
            self.latest_single_channel,
            current_time,
            channel_number=self.channel_spinbox.value(),
            mode=self.mode_combo.currentText(),
        )
        if self.all_channels_dialog.isVisible():
            self.all_channels_plot.plot_all_channels(self.latest_all_channels, current_time)

    def _show_all_channels(self) -> None:
        """Open the all-channel overview using the latest cached live data."""
        self.all_channels_plot.plot_all_channels(
            self.latest_all_channels,
            getattr(self, "current_time", 0.0),
        )
        self.all_channels_dialog.show()
        self.all_channels_dialog.raise_()
        self.all_channels_dialog.activateWindow()

    def _update_offline_plot(self, data: object) -> None:
        """Redraw the Matplotlib offline plot for the selected channel/mode."""
        self.offline_plot.plot(np.asarray(data), self.mode_combo.currentText())

    def closeEvent(self, event) -> None:
        """Clean up sockets when the user closes the main window."""
        self.view_model.disconnect_from_server(announce=False)
        self.view_model.stop_tcp_server()
        super().closeEvent(event)

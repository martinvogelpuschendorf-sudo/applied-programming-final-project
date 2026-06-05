"""Editable labels and button text used by the GUI views."""

START_TCP_SERVER = "Start\nTCP Server"
STOP_TCP_SERVER = "Stop\nTCP Server"

CONNECT_TO_TCP_SERVER = "Connect\nTCP Server"
DISCONNECT_FROM_TCP_SERVER = "Disconnect\nTCP Server"

PLOT_ALL_CHANNELS = "Plot all Channels"
PLOT_ALL_CHANNELS_DIALOG_TITLE = PLOT_ALL_CHANNELS

SELECT_ALL_CHANNELS = "Select all Channels"
DESELECT_ALL_CHANNELS = "Deselect all Channels"

CHANNEL_BUTTON_TEMPLATE = "Channel {channel_number}"

WINDOW_TITLE = "MyoFlow EMG Reader"

LIVE_PLOT_TITLE = "Selected Channel"
ALL_CHANNELS_PLOT_TITLE = "All Channels"

HOST_LABEL = "Host"
TCP_PORT_LABEL = "TCP Port"

SIGNAL_MODE_LABEL = "Signal Mode"
VISIBLE_CHANNELS_LABEL = "Visible Channels"
TIME_WINDOW_LABEL = "Time Window"

SIGNAL_MODE_OPTIONS = ["Original", "RMS", "Filtered"]
DEFAULT_SIGNAL_MODE = "Filtered"

VISIBLE_CHANNEL_OPTIONS = ["1", "2", "4", "6", "8", "12", "16", "All"]
DEFAULT_VISIBLE_CHANNELS = "4"
ALL_VISIBLE_CHANNELS_OPTION = "All"

TIME_WINDOW_OPTIONS = ["5 s", "10 s", "20 s", "30 s", "60 s"]
DEFAULT_TIME_WINDOW = "10 s"
TIME_WINDOW_SUFFIX = " s"

LIVE_TAB_LABEL = "Live"
OFFLINE_TAB_LABEL = "Offline"

CHANNEL_SELECTOR_CONNECT_MESSAGE = "Connect to TCP server to display available EMG channels"
CHANNEL_SELECTOR_WAITING_MESSAGE = "Waiting for available EMG channels..."

OFFLINE_NO_RECORDING_MESSAGE = "No recorded data yet."
OFFLINE_NO_RECORDED_DATA_AVAILABLE_MESSAGE = "No recorded data available."
OFFLINE_SELECT_CHANNELS_MESSAGE = "Select one or more channels to inspect recorded data."

CONNECTION_INFO_EMPTY = (
    "Connected to: --\n"
    "Channels: --\n"
    "Sampling Rate: --\n"
    "Time Recorded: --"
)
CONNECTION_INFO_TEMPLATE = (
    "Connected to: {host}:{port}\n"
    "Channels: {channel_count}\n"
    "Sampling Rate: {sample_rate:g} Hz\n"
    "Time Recorded: {current_time:.1f} s"
)

COPYRIGHT_LABEL = "© Luo Lan, YU-HSUAN KUO, Martin Vogel"

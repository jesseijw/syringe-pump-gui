from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QDoubleSpinBox, QPushButton, QProgressBar,
)
from PyQt5.QtCore import Qt, pyqtSignal
from state import PumpState
import config

_STATE_COLORS = {
    PumpState.IDLE:     "#888888",
    PumpState.HOMING:   "#FFA500",
    PumpState.RUNNING:  "#00AA00",
    PumpState.STOPPING: "#FFA500",
    PumpState.EMPTY:    "#FF6600",
    PumpState.ERROR:    "#CC0000",
    PumpState.STARTUP:  "#888888",
}


class PumpPanel(QWidget):
    run_requested         = pyqtSignal(int, float, float)  # pump_id, volume_ml, flow_rate_ml_sec
    stop_requested        = pyqtSignal(int)                # pump_id
    initial_volume_set    = pyqtSignal(int, float)         # pump_id, volume_ml

    def __init__(self, pump_id: int, parent=None):
        super().__init__(parent)
        self.pump_id = pump_id
        self._build_ui()
        self.set_state(PumpState.IDLE)

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self._title = QLabel(f"Pump {self.pump_id}")
        self._title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._title)

        self._status = QLabel("IDLE")
        self._status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._status)

        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Current Volume (mL):"))
        self._volume_label = QLabel(f"{config.FULL_VOLUME_ML:.1f}")
        vol_row.addWidget(self._volume_label)
        layout.addLayout(vol_row)

        init_row = QHBoxLayout()
        init_row.addWidget(QLabel("Initial Volume (mL):"))
        self._init_volume_spin = QDoubleSpinBox()
        self._init_volume_spin.setRange(0.0, config.FULL_VOLUME_ML)
        self._init_volume_spin.setDecimals(2)
        self._init_volume_spin.setValue(config.FULL_VOLUME_ML)
        self._set_volume_btn = QPushButton("Set")
        self._set_volume_btn.clicked.connect(self._on_set_volume)
        init_row.addWidget(self._init_volume_spin)
        init_row.addWidget(self._set_volume_btn)
        layout.addLayout(init_row)

        flow_row = QHBoxLayout()
        flow_row.addWidget(QLabel("Flow Rate (mL/s):"))
        self._flow_spin = QDoubleSpinBox()
        self._flow_spin.setRange(0.01, 5.0)
        self._flow_spin.setDecimals(3)
        self._flow_spin.setValue(0.1)
        flow_row.addWidget(self._flow_spin)
        layout.addLayout(flow_row)

        purge_row = QHBoxLayout()
        purge_row.addWidget(QLabel("Purge Amount (mL):"))
        self._purge_spin = QDoubleSpinBox()
        self._purge_spin.setRange(0.0, config.FULL_VOLUME_ML)
        self._purge_spin.setDecimals(2)
        self._purge_spin.setValue(1.0)
        purge_row.addWidget(self._purge_spin)
        layout.addLayout(purge_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 1000)
        self._progress.setValue(1000)
        layout.addWidget(self._progress)

        btn_row = QHBoxLayout()
        self._run_btn  = QPushButton("Run")
        self._stop_btn = QPushButton("Stop")
        self._run_btn.clicked.connect(self._on_run)
        self._stop_btn.clicked.connect(lambda: self.stop_requested.emit(self.pump_id))
        btn_row.addWidget(self._run_btn)
        btn_row.addWidget(self._stop_btn)
        layout.addLayout(btn_row)

    def _on_set_volume(self):
        self.initial_volume_set.emit(self.pump_id, self._init_volume_spin.value())

    def _on_run(self):
        self.run_requested.emit(
            self.pump_id,
            self._purge_spin.value(),   # volume_ml (purge amount)
            self._flow_spin.value(),    # flow_rate_ml_sec
        )

    def set_state(self, state: PumpState):
        color = _STATE_COLORS.get(state, "#888888")
        self._status.setText(state.value)
        self._status.setStyleSheet(
            f"font-weight: bold; padding: 4px; border-radius: 4px;"
            f"background-color: {color}; color: white;"
        )
        is_idle = (state == PumpState.IDLE)
        self._init_volume_spin.setEnabled(is_idle)
        self._set_volume_btn.setEnabled(is_idle)
        self._flow_spin.setEnabled(is_idle)
        self._purge_spin.setEnabled(is_idle)
        self._run_btn.setEnabled(is_idle)
        # EMPTY locks all buttons — operator re-homes via main window "Home All" button
        self._stop_btn.setEnabled(state == PumpState.RUNNING)

    def update_volume(self, volume_ml: float):
        self._volume_label.setText(f"{volume_ml:.2f}")
        fraction = max(0.0, min(1.0, volume_ml / config.FULL_VOLUME_ML))
        self._progress.setValue(int(fraction * 1000))

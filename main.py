import sys
import config
import settings as _settings
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox,
)
from controller import TicController, ArduinoController
from pump import Pump, LimitSwitchWorker, DispenseWorker, HomingWorker
from pump_panel import PumpPanel
from startup_dialog import StartupDialog
from settings_dialog import SettingsDialog
from state import PumpState


def _make_controller():
    return TicController() if config.BACKEND == "tic" else ArduinoController()


class MainWindow(QMainWindow):

    def __init__(self, pumps: dict, panels: dict):
        super().__init__()
        self.setWindowTitle("Syringe Pump Controller")
        self._pumps   = pumps
        self._panels  = panels
        self._workers: dict = {}
        self._homing_workers: dict = {}
        self._build_ui()
        self._wire_signals()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        top = QHBoxLayout()
        top.addWidget(QLabel("<h2>Syringe Pump Controller</h2>"))
        top.addStretch()
        settings_btn = QPushButton("⚙ Settings")
        settings_btn.clicked.connect(self._open_settings)
        top.addWidget(settings_btn)
        root.addLayout(top)

        self._home_btn = QPushButton("Home All Pumps")
        self._home_btn.clicked.connect(self._home_all)
        root.addWidget(self._home_btn)

        panels_row = QHBoxLayout()
        for pid in sorted(self._panels):
            panels_row.addWidget(self._panels[pid])
        root.addLayout(panels_row)

    def _wire_signals(self):
        for pid, panel in self._panels.items():
            panel.run_requested.connect(self._on_run)
            panel.stop_requested.connect(self._on_stop)

    def _on_run(self, pump_id: int, volume_ml: float, flow_rate_ml_sec: float):
        pump  = self._pumps[pump_id]
        panel = self._panels[pump_id]

        # Cancel and wait on any old dispense worker for this pump
        if pump_id in self._workers:
            self._workers[pump_id].cancel()
            self._workers[pump_id].wait()

        # Run dispense in background thread
        worker = DispenseWorker(pump, volume_ml, flow_rate_ml_sec)
        worker.finished.connect(self._on_dispense_finished)
        worker.error.connect(self._on_dispense_error)
        self._workers[pump_id] = worker
        panel.set_state(PumpState.RUNNING)
        worker.start()

    def _on_dispense_finished(self, pump_id: int):
        pump  = self._pumps[pump_id]
        panel = self._panels[pump_id]
        panel.set_state(pump.state)
        panel.update_volume(pump.current_volume_ml)
        # Remove stale dispense worker reference
        self._workers.pop(pump_id, None)
        # Start limit switch polling
        limit_worker = LimitSwitchWorker(pump_id, pump._controller)
        limit_worker.limit_hit.connect(self._on_limit_hit)
        self._workers[f"limit_{pump_id}"] = limit_worker
        limit_worker.start()

    def _on_dispense_error(self, pump_id: int, msg: str, is_validation_error: bool):
        pump  = self._pumps[pump_id]
        panel = self._panels[pump_id]
        panel.set_state(pump.state)
        panel.update_volume(pump.current_volume_ml)
        # Remove stale dispense worker reference
        self._workers.pop(pump_id, None)
        if is_validation_error:
            QMessageBox.warning(self, "Invalid Input", msg)
        # If not validation error, panel.set_state(pump.state) already set ERROR

    def _on_stop(self, pump_id: int):
        if pump_id in self._workers:
            self._workers[pump_id].cancel()
        self._pumps[pump_id].stop()
        self._panels[pump_id].set_state(self._pumps[pump_id].state)

    def _on_limit_hit(self, pump_id: int):
        self._pumps[pump_id].mark_empty()
        self._panels[pump_id].set_state(PumpState.EMPTY)
        self._panels[pump_id].update_volume(0.0)

    def _home_all(self):
        for pid, pump in self._pumps.items():
            if pid in self._homing_workers and self._homing_workers[pid].isRunning():
                continue  # homing already in progress for this pump
            self._panels[pid].set_state(PumpState.HOMING)
            worker = HomingWorker(pump)
            worker.finished.connect(self._on_homing_finished)
            worker.error.connect(self._on_homing_error)
            self._homing_workers[pid] = worker
            worker.start()

    def _on_homing_finished(self, pump_id: int):
        pump = self._pumps[pump_id]
        self._panels[pump_id].set_state(PumpState.IDLE)
        self._panels[pump_id].update_volume(pump.current_volume_ml)

    def _on_homing_error(self, pump_id: int, msg: str):
        self._panels[pump_id].set_state(PumpState.ERROR)

    def closeEvent(self, event):
        for w in self._workers.values():
            if hasattr(w, "cancel"):
                w.cancel()
            w.wait()
        # Homing workers cannot be interrupted mid-flight; wait for them to finish
        for w in getattr(self, "_homing_workers", {}).values():
            w.wait()
        event.accept()

    def _open_settings(self):
        SettingsDialog(self).exec_()


def main():
    app = QApplication(sys.argv)
    ctrl = _make_controller()

    try:
        detected = ctrl.detect()
    except Exception:
        detected = []

    dlg = StartupDialog(detected_ids=detected)
    if dlg.exec_() != StartupDialog.Accepted:
        sys.exit(0)

    pumps  = {pid: Pump(pid, ctrl) for pid in detected}
    panels = {pid: PumpPanel(pid) for pid in detected}

    if not pumps:
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(None, "No Pumps", "No pump controllers were detected. Check connections and restart.")
        sys.exit(1)

    if dlg.choice == StartupDialog.HOME:
        for pid, pump in pumps.items():
            panels[pid].set_state(PumpState.HOMING)
            try:
                pump.home()
                panels[pid].set_state(PumpState.IDLE)
                panels[pid].update_volume(pump.current_volume_ml)
            except Exception:
                panels[pid].set_state(PumpState.ERROR)
    else:
        saved = _settings.get("PUMP_POSITIONS")
        for pid, pump in pumps.items():
            pump.resume(int(saved.get(str(pid), 0)))
            panels[pid].set_state(PumpState.IDLE)
            panels[pid].update_volume(pump.current_volume_ml)

    win = MainWindow(pumps=pumps, panels=panels)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

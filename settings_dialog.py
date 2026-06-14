from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QDoubleSpinBox, QDialogButtonBox,
)
import settings as _settings


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._build_ui()

    def _build_ui(self):
        layout = QFormLayout(self)
        self._fields = {}
        spec = [
            ("MICROSTEPPING",             "Microstepping",               1,    256, 0),
            ("LEAD_SCREW_PITCH_MM",       "Lead screw pitch (mm)",       0.1,  50,  2),
            ("SYRINGE_INNER_DIAMETER_MM", "Syringe inner diameter (mm)", 1.0,  50,  2),
            ("MAX_FLOW_RATE_ML_SEC",      "Max flow rate (mL/s)",        0.01, 50,  3),
            ("MIN_FLOW_RATE_ML_SEC",      "Min flow rate (mL/s)",        0.001, 5,  4),
        ]
        for key, label, lo, hi, decimals in spec:
            spin = QDoubleSpinBox()
            spin.setRange(lo, hi)
            spin.setDecimals(decimals)
            spin.setValue(float(_settings.get(key)))
            layout.addRow(label, spin)
            self._fields[key] = spin

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _save(self):
        _settings.save({k: spin.value() for k, spin in self._fields.items()})
        self.accept()

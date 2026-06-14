from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)


class StartupDialog(QDialog):
    HOME   = 1
    RESUME = 2

    def __init__(self, detected_ids: "list[int]", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Syringe Pump Controller — Startup")
        self.setModal(True)
        self._choice = None
        self._build_ui(detected_ids)

    def _build_ui(self, detected_ids: "list[int]"):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Controllers detected:</b>"))

        for pid in [1, 2, 3]:
            icon, color = ("✓", "green") if pid in detected_ids else ("✗", "red")
            layout.addWidget(
                QLabel(f"<span style='color:{color}'>{icon}</span>  Pump {pid}")
            )

        layout.addSpacing(12)
        btn_row = QHBoxLayout()
        self._home_btn   = QPushButton("Home All Pumps")
        self._resume_btn = QPushButton("Resume Existing Position")
        self._home_btn.clicked.connect(lambda: self._select(self.HOME))
        self._resume_btn.clicked.connect(lambda: self._select(self.RESUME))
        btn_row.addWidget(self._home_btn)
        btn_row.addWidget(self._resume_btn)
        layout.addLayout(btn_row)

    def _select(self, choice: int):
        self._choice = choice
        self.accept()

    @property
    def choice(self) -> "int | None":
        return self._choice

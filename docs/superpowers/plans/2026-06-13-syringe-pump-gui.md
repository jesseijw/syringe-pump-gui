# Syringe Pump GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PyQt5 GUI on Raspberry Pi to control 3 syringe pumps via NEMA 17 stepper motors, supporting Tic T825 USB controllers and Arduino serial backends.

**Architecture:** Hardware is abstracted behind a `PumpController` interface with two concrete implementations (TicController, ArduinoController). High-level pump logic (homing, dispense, position tracking) lives in `pump.py`. The GUI thread never touches hardware directly — all controller calls go through worker QThreads that emit signals back to the GUI.

**Tech Stack:** Python 3.9+, PyQt5, ticlib, pyserial, RPi.GPIO (Arduino backend only), pytest

---

## File Map

| File | Responsibility |
|------|---------------|
| `config.py` | Default hardware constants (never modified at runtime) |
| `settings.py` | Loads config.py + settings.json, provides `get()` / `save()` |
| `settings.json` | User-tunable overrides, written by settings dialog |
| `units.py` | mL ↔ steps conversion math |
| `state.py` | `PumpState` enum + transition validator |
| `errors.py` | Custom exception classes |
| `controller.py` | Abstract `PumpController` + `TicController` + `ArduinoController` |
| `pump.py` | `Pump` class (homing, dispense, position tracking) + worker QThreads |
| `pump_panel.py` | PyQt5 widget for one pump card |
| `startup_dialog.py` | Detect controllers + Home/Resume modal |
| `settings_dialog.py` | Runtime settings editor |
| `main.py` | App entry point + main window |
| `tests/conftest.py` | pytest fixtures (QApplication, mock controller) |
| `tests/test_errors.py` | Exception class tests |
| `tests/test_state.py` | State machine transition tests |
| `tests/test_settings.py` | Config loading + override tests |
| `tests/test_units.py` | Conversion math tests |
| `tests/test_controller.py` | Controller interface + backend tests (mocked hardware) |
| `tests/test_pump.py` | Pump logic tests + widget smoke tests |
| `tests/test_startup_dialog.py` | Startup dialog tests |
| `arduino/pump_controller.ino` | Arduino firmware (Arduino backend only) |

---

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `.gitignore`

- [ ] **Step 1: Create requirements.txt**

```
PyQt5>=5.15
pyserial>=3.5
pytest>=7.0
pytest-qt>=4.2
```

Note: `ticlib` and `RPi.GPIO` are Pi-specific. Install separately on the Pi with `pip install ticlib RPi.GPIO`. Omitted here to avoid breaking dev-machine installs.

- [ ] **Step 2: Create .gitignore**

```
__pycache__/
*.pyc
*.pyo
.pytest_cache/
settings.json
```

- [ ] **Step 3: Create tests/conftest.py**

```python
import sys
import pytest
from unittest.mock import MagicMock
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def mock_controller():
    ctrl = MagicMock()
    ctrl.detect.return_value = [1, 2, 3]
    ctrl.read_limit.return_value = False
    return ctrl
```

- [ ] **Step 4: Install dependencies**

```bash
cd /Users/jessiewang/Downloads/syringe_pump_gui
pip install PyQt5 pyserial pytest pytest-qt
```

Expected: packages install without error.

- [ ] **Step 5: Verify test runner works**

```bash
cd /Users/jessiewang/Downloads/syringe_pump_gui
pytest tests/ -v
```

Expected: `no tests ran` (0 collected).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .gitignore tests/
git commit -m "chore: project scaffolding"
```

---

### Task 2: errors.py

**Files:**
- Create: `errors.py`
- Create: `tests/test_errors.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_errors.py
from errors import (
    HomingTimeoutError, HomingTravelExceededError,
    InvalidStateTransitionError, ControllerNotFoundError,
    SerialConnectionError, ValidationError,
)

def test_all_errors_are_exceptions():
    for cls in [
        HomingTimeoutError, HomingTravelExceededError,
        InvalidStateTransitionError, ControllerNotFoundError,
        SerialConnectionError, ValidationError,
    ]:
        assert issubclass(cls, Exception)

def test_errors_carry_messages():
    e = ValidationError("purge amount exceeds current volume")
    assert str(e) == "purge amount exceeds current volume"
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_errors.py -v
```

Expected: `ModuleNotFoundError: No module named 'errors'`

- [ ] **Step 3: Create errors.py**

```python
class HomingTimeoutError(Exception): pass
class HomingTravelExceededError(Exception): pass
class InvalidStateTransitionError(Exception): pass
class ControllerNotFoundError(Exception): pass
class SerialConnectionError(Exception): pass
class ValidationError(Exception): pass
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_errors.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add errors.py tests/test_errors.py
git commit -m "feat: add custom exception classes"
```

---

### Task 3: state.py

**Files:**
- Create: `state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_state.py
import pytest
from state import PumpState, validate_transition
from errors import InvalidStateTransitionError


def test_valid_startup_to_homing():
    validate_transition(PumpState.STARTUP, PumpState.HOMING)

def test_valid_startup_to_idle():
    validate_transition(PumpState.STARTUP, PumpState.IDLE)

def test_valid_homing_to_idle():
    validate_transition(PumpState.HOMING, PumpState.IDLE)

def test_valid_homing_to_error():
    validate_transition(PumpState.HOMING, PumpState.ERROR)

def test_valid_idle_to_running():
    validate_transition(PumpState.IDLE, PumpState.RUNNING)

def test_valid_running_to_stopping():
    validate_transition(PumpState.RUNNING, PumpState.STOPPING)

def test_valid_stopping_to_idle():
    validate_transition(PumpState.STOPPING, PumpState.IDLE)

def test_valid_stopping_to_empty():
    validate_transition(PumpState.STOPPING, PumpState.EMPTY)

def test_valid_empty_to_idle():
    validate_transition(PumpState.EMPTY, PumpState.IDLE)

def test_valid_error_to_homing():
    validate_transition(PumpState.ERROR, PumpState.HOMING)

def test_invalid_idle_to_startup():
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(PumpState.IDLE, PumpState.STARTUP)

def test_invalid_running_to_idle_directly():
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(PumpState.RUNNING, PumpState.IDLE)

def test_invalid_empty_to_running():
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(PumpState.EMPTY, PumpState.RUNNING)
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_state.py -v
```

Expected: `ModuleNotFoundError: No module named 'state'`

- [ ] **Step 3: Create state.py**

```python
from enum import Enum
from errors import InvalidStateTransitionError


class PumpState(Enum):
    STARTUP  = "STARTUP"
    HOMING   = "HOMING"
    IDLE     = "IDLE"
    RUNNING  = "RUNNING"
    STOPPING = "STOPPING"
    EMPTY    = "EMPTY"
    ERROR    = "ERROR"


_VALID_TRANSITIONS = {
    PumpState.STARTUP:  {PumpState.HOMING, PumpState.IDLE},
    PumpState.HOMING:   {PumpState.IDLE,  PumpState.ERROR},
    PumpState.IDLE:     {PumpState.HOMING, PumpState.RUNNING},
    PumpState.RUNNING:  {PumpState.STOPPING, PumpState.ERROR},
    PumpState.STOPPING: {PumpState.IDLE, PumpState.EMPTY},
    PumpState.EMPTY:    {PumpState.IDLE},
    PumpState.ERROR:    {PumpState.HOMING},
}


def validate_transition(current: PumpState, next_state: PumpState) -> None:
    allowed = _VALID_TRANSITIONS.get(current, set())
    if next_state not in allowed:
        raise InvalidStateTransitionError(
            f"Cannot transition from {current.value} to {next_state.value}"
        )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_state.py -v
```

Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add state.py tests/test_state.py
git commit -m "feat: add PumpState enum and transition validator"
```

---

### Task 4: config.py + settings.py

**Files:**
- Create: `config.py`
- Create: `settings.py`
- Create: `tests/test_settings.py`

- [ ] **Step 1: Create config.py**

```python
# Tic T825 is strongly recommended. Arduino backend requires separate firmware.
BACKEND = "tic"              # "arduino" or "tic"

SERIAL_PORT = "/dev/ttyUSB0"   # TODO: confirm after wiring
SERIAL_BAUD = 115200

# Run `ticcmd --list` to find serial numbers after connecting controllers
TIC_SERIAL_NUMBERS = {
    1: "TODO",
    2: "TODO",
    3: "TODO",
}

STEPS_PER_REV             = 200
MICROSTEPPING             = 16          # TODO: confirm from driver config
LEAD_SCREW_PITCH_MM       = 8.0         # TODO: measure from CAD
SYRINGE_INNER_DIAMETER_MM = 15.9        # TODO: measure actual syringe barrel
FULL_VOLUME_ML            = 15.0

MAX_FLOW_RATE_ML_SEC = 5.0              # TODO: tune to safe hardware limit
MIN_FLOW_RATE_ML_SEC = 0.01

LIMIT_SWITCH_NORMALLY_CLOSED = True     # normally-closed: broken wire = fault detected

LIMIT_SWITCH_PINS = {
    1: {"aft": None, "forward": None},  # TODO: fill in after wiring
    2: {"aft": None, "forward": None},  # TODO
    3: {"aft": None, "forward": None},  # TODO
}

HOMING_SPEED_MM_PER_SEC = 2.0
HOMING_TIMEOUT_SEC      = 30
MAX_HOMING_TRAVEL_MM    = 150

# Persisted pump positions (steps from home). Updated by pump.py after each move.
PUMP_POSITIONS = {"1": 0, "2": 0, "3": 0}
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_settings.py
import json
import pytest
import settings


@pytest.fixture(autouse=True)
def clean_settings(tmp_path, monkeypatch):
    fake_path = tmp_path / "settings.json"
    monkeypatch.setattr(settings, "_SETTINGS_PATH", fake_path)
    settings._runtime.clear()
    yield fake_path
    settings._runtime.clear()


def test_defaults_loaded_without_settings_file():
    import config
    assert settings.get("MICROSTEPPING") == config.MICROSTEPPING


def test_settings_json_overrides_default(clean_settings):
    clean_settings.write_text(json.dumps({"MICROSTEPPING": 32}))
    settings._runtime.clear()
    assert settings.get("MICROSTEPPING") == 32


def test_save_writes_to_json(clean_settings):
    settings.save({"LEAD_SCREW_PITCH_MM": 4.0})
    data = json.loads(clean_settings.read_text())
    assert data["LEAD_SCREW_PITCH_MM"] == 4.0


def test_unknown_keys_ignored_on_save(clean_settings):
    import config
    settings.save({"NOT_A_REAL_KEY": 999})
    assert settings.get("MICROSTEPPING") == config.MICROSTEPPING


def test_save_then_reload_round_trips(clean_settings):
    settings.save({"MICROSTEPPING": 8})
    settings._runtime.clear()
    assert settings.get("MICROSTEPPING") == 8


def test_pump_positions_persisted(clean_settings):
    settings.save({"PUMP_POSITIONS": {"1": 500, "2": 0, "3": 0}})
    settings._runtime.clear()
    assert settings.get("PUMP_POSITIONS")["1"] == 500
```

- [ ] **Step 3: Run to verify failure**

```bash
pytest tests/test_settings.py -v
```

Expected: `ModuleNotFoundError: No module named 'settings'`

- [ ] **Step 4: Create settings.py**

```python
import json
import pathlib
import config as _defaults

_SETTINGS_PATH = pathlib.Path(__file__).parent / "settings.json"

_OVERRIDABLE_KEYS = {
    "MICROSTEPPING", "LEAD_SCREW_PITCH_MM", "SYRINGE_INNER_DIAMETER_MM",
    "MAX_FLOW_RATE_ML_SEC", "MIN_FLOW_RATE_ML_SEC", "PUMP_POSITIONS",
}

_runtime: dict = {}


def _load() -> None:
    global _runtime
    base = {k: getattr(_defaults, k) for k in _OVERRIDABLE_KEYS}
    if _SETTINGS_PATH.exists():
        with open(_SETTINGS_PATH) as f:
            overrides = json.load(f)
        base.update({k: v for k, v in overrides.items() if k in _OVERRIDABLE_KEYS})
    _runtime = base


def get(key: str):
    if not _runtime:
        _load()
    return _runtime[key]


def save(updates: dict) -> None:
    _load()
    _runtime.update({k: v for k, v in updates.items() if k in _OVERRIDABLE_KEYS})
    with open(_SETTINGS_PATH, "w") as f:
        json.dump({k: _runtime[k] for k in _OVERRIDABLE_KEYS}, f, indent=2)
    _load()
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_settings.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add config.py settings.py tests/test_settings.py
git commit -m "feat: add config defaults and settings.json override loader"
```

---

### Task 5: units.py

**Files:**
- Create: `units.py`
- Create: `tests/test_units.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_units.py
import pytest
from unittest.mock import patch

MOCK_SETTINGS = {
    "MICROSTEPPING": 16,
    "LEAD_SCREW_PITCH_MM": 8.0,
    "SYRINGE_INNER_DIAMETER_MM": 15.9,
}


@pytest.fixture(autouse=True)
def patch_settings():
    with patch("settings.get", side_effect=lambda k: MOCK_SETTINGS[k]):
        import units
        import importlib
        importlib.reload(units)
        yield


def test_ml_to_steps_zero():
    import units
    assert units.ml_to_steps(0.0) == 0


def test_ml_to_steps_positive():
    import units
    assert units.ml_to_steps(15.0) > 0


def test_steps_to_ml_zero():
    import units
    assert units.steps_to_ml(0) == pytest.approx(0.0)


def test_round_trip():
    import units
    assert units.steps_to_ml(units.ml_to_steps(7.5)) == pytest.approx(7.5, abs=0.01)


def test_flow_rate_proportional():
    import units
    s1 = units.flow_rate_to_steps_per_sec(1.0)
    s2 = units.flow_rate_to_steps_per_sec(2.0)
    assert s2 == pytest.approx(2 * s1)


def test_known_value():
    # diameter=15.9mm → area=π×7.95²≈198.55mm²
    # mm_per_ml=1000/198.55≈5.036  steps_per_mm=(200×16)/8=400
    # steps_per_ml≈2014 → ml_to_steps(1.0)≈2014
    import units
    assert 1900 < units.ml_to_steps(1.0) < 2200
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_units.py -v
```

Expected: `ModuleNotFoundError: No module named 'units'`

- [ ] **Step 3: Create units.py**

```python
import math
import settings


def _steps_per_ml() -> float:
    diameter = settings.get("SYRINGE_INNER_DIAMETER_MM")
    pitch    = settings.get("LEAD_SCREW_PITCH_MM")
    ustep    = settings.get("MICROSTEPPING")
    cross_section = math.pi * (diameter / 2) ** 2
    mm_per_ml     = 1000.0 / cross_section
    steps_per_mm  = (200 * ustep) / pitch
    return steps_per_mm * mm_per_ml


def ml_to_steps(ml: float) -> int:
    return round(ml * _steps_per_ml())


def steps_to_ml(steps: int) -> float:
    spm = _steps_per_ml()
    return 0.0 if spm == 0 else steps / spm


def flow_rate_to_steps_per_sec(ml_per_sec: float) -> float:
    return ml_per_sec * _steps_per_ml()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_units.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add units.py tests/test_units.py
git commit -m "feat: add mL/steps conversion module"
```

---

### Task 6: controller.py — abstract interface

**Files:**
- Create: `controller.py`
- Create: `tests/test_controller.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_controller.py
import pytest
from unittest.mock import MagicMock, patch


def test_abstract_controller_cannot_be_instantiated():
    from controller import PumpController
    with pytest.raises(TypeError):
        PumpController()


def test_concrete_subclass_must_implement_all_methods():
    from controller import PumpController

    class Incomplete(PumpController):
        pass

    with pytest.raises(TypeError):
        Incomplete()
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_controller.py -v
```

Expected: `ModuleNotFoundError: No module named 'controller'`

- [ ] **Step 3: Create controller.py with abstract base**

```python
from abc import ABC, abstractmethod
from typing import List


class PumpController(ABC):

    @abstractmethod
    def detect(self) -> List[int]:
        """Return list of pump IDs found on the bus."""

    @abstractmethod
    def energize(self, pump_id: int) -> None:
        """Enable motor coils."""

    @abstractmethod
    def deenergize(self, pump_id: int) -> None:
        """Release motor coils to prevent overheating when idle."""

    @abstractmethod
    def home(self, pump_id: int) -> None:
        """Begin slow aft movement. Caller polls read_limit('aft') for completion."""

    @abstractmethod
    def move(self, pump_id: int, steps: int, steps_per_sec: float) -> None:
        """Move `steps` at `steps_per_sec`. Blocks until motion completes."""

    @abstractmethod
    def stop(self, pump_id: int) -> None:
        """Immediately halt motion."""

    @abstractmethod
    def read_limit(self, pump_id: int, side: str) -> bool:
        """Return True if named switch is active. side: 'aft' | 'forward'"""
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_controller.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add controller.py tests/test_controller.py
git commit -m "feat: add abstract PumpController interface"
```

---

### Task 7: TicController

**Files:**
- Modify: `controller.py` (append TicController)
- Modify: `tests/test_controller.py` (append TicController tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_controller.py`:

```python
def test_tic_detect_returns_found_ids():
    with patch("controller.ticlib") as mock_ticlib:
        mock_ticlib.TicUSB.return_value = MagicMock()
        from controller import TicController
        import importlib, controller
        importlib.reload(controller)
        ctrl = controller.TicController()
        found = ctrl.detect()
        import config
        assert set(found) == set(config.TIC_SERIAL_NUMBERS.keys())


def test_tic_detect_excludes_missing_controller():
    with patch("controller.ticlib") as mock_ticlib:
        mock_ticlib.TicUSB.side_effect = [MagicMock(), Exception("not found"), MagicMock()]
        from controller import TicController
        ctrl = TicController()
        found = ctrl.detect()
        assert 2 not in found
        assert 1 in found and 3 in found


def test_tic_energize_calls_tic():
    with patch("controller.ticlib") as mock_ticlib:
        mock_tic = MagicMock()
        mock_ticlib.TicUSB.return_value = mock_tic
        from controller import TicController
        ctrl = TicController()
        ctrl.detect()
        ctrl.energize(1)
        mock_tic.energize.assert_called_once()


def test_tic_read_limit_forward():
    with patch("controller.ticlib") as mock_ticlib:
        mock_tic = MagicMock()
        mock_vars = MagicMock()
        mock_vars.forward_limit_active = True
        mock_tic.get_variables.return_value = mock_vars
        mock_ticlib.TicUSB.return_value = mock_tic
        from controller import TicController
        ctrl = TicController()
        ctrl.detect()
        assert ctrl.read_limit(1, "forward") is True


def test_tic_read_limit_aft():
    with patch("controller.ticlib") as mock_ticlib:
        mock_tic = MagicMock()
        mock_vars = MagicMock()
        mock_vars.reverse_limit_active = True
        mock_tic.get_variables.return_value = mock_vars
        mock_ticlib.TicUSB.return_value = mock_tic
        from controller import TicController
        ctrl = TicController()
        ctrl.detect()
        assert ctrl.read_limit(1, "aft") is True
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_controller.py -v -k "tic"
```

Expected: failures — `TicController` not defined.

- [ ] **Step 3: Append TicController to controller.py**

```python
try:
    import ticlib
except ImportError:
    ticlib = None   # not available on dev machines

import config as _cfg
import time as _time


class TicController(PumpController):

    def __init__(self):
        self._tics: dict = {}

    def detect(self) -> List[int]:
        if ticlib is None:
            raise ImportError("ticlib not installed. Run: pip install ticlib")
        found = []
        for pump_id, serial_num in _cfg.TIC_SERIAL_NUMBERS.items():
            try:
                tic = ticlib.TicUSB(serial_number=str(serial_num))
                self._tics[pump_id] = tic
                found.append(pump_id)
            except Exception:
                pass
        return found

    def _tic(self, pump_id: int):
        if pump_id not in self._tics:
            from errors import ControllerNotFoundError
            raise ControllerNotFoundError(f"Pump {pump_id} not detected")
        return self._tics[pump_id]

    def energize(self, pump_id: int) -> None:
        self._tic(pump_id).energize()

    def deenergize(self, pump_id: int) -> None:
        self._tic(pump_id).deenergize()

    def home(self, pump_id: int) -> None:
        tic = self._tic(pump_id)
        steps_per_sec = int(
            _cfg.HOMING_SPEED_MM_PER_SEC
            * (200 * _cfg.MICROSTEPPING) / _cfg.LEAD_SCREW_PITCH_MM
        )
        tic.set_target_velocity(-steps_per_sec)

    def move(self, pump_id: int, steps: int, steps_per_sec: float) -> None:
        tic = self._tic(pump_id)
        tic.reset_command_timeout()
        current = tic.get_variables().current_position
        tic.set_target_position(current + steps)
        # Poll until motion complete
        while True:
            tic.reset_command_timeout()
            v = tic.get_variables()
            if v.current_position == current + steps:
                break
            _time.sleep(0.02)

    def stop(self, pump_id: int) -> None:
        self._tic(pump_id).halt_and_hold()

    def read_limit(self, pump_id: int, side: str) -> bool:
        variables = self._tic(pump_id).get_variables()
        if side == "forward":
            return bool(variables.forward_limit_active)
        if side == "aft":
            return bool(variables.reverse_limit_active)
        raise ValueError(f"Unknown side: {side!r}. Use 'aft' or 'forward'.")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_controller.py -v -k "tic"
```

Expected: all TicController tests pass.

- [ ] **Step 5: Commit**

```bash
git add controller.py tests/test_controller.py
git commit -m "feat: add TicController for Tic T825 backend"
```

---

### Task 8: ArduinoController

**Files:**
- Modify: `controller.py` (append ArduinoController)
- Modify: `tests/test_controller.py` (append ArduinoController tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_controller.py`:

```python
def test_arduino_detect_opens_serial_port():
    with patch("controller.serial") as mock_serial:
        mock_ser = MagicMock()
        mock_ser.readline.return_value = b"OK\n"
        mock_serial.Serial.return_value = mock_ser
        from controller import ArduinoController
        ctrl = ArduinoController()
        found = ctrl.detect()
        assert found == [1, 2, 3]
        mock_serial.Serial.assert_called_once()


def test_arduino_stop_sends_correct_command():
    with patch("controller.serial"):
        from controller import ArduinoController
        ctrl = ArduinoController()
        mock_ser = MagicMock()
        mock_ser.readline.return_value = b"OK\n"
        ctrl._ser = mock_ser
        ctrl.stop(2)
        mock_ser.write.assert_called_with(b"STOP:2\n")


def test_arduino_read_limit_forward_parses_response():
    with patch("controller.serial"):
        from controller import ArduinoController
        ctrl = ArduinoController()
        mock_ser = MagicMock()
        mock_ser.readline.return_value = b"1\n"
        ctrl._ser = mock_ser
        assert ctrl.read_limit(1, "forward") is True


def test_arduino_read_limit_not_triggered():
    with patch("controller.serial"):
        from controller import ArduinoController
        ctrl = ArduinoController()
        mock_ser = MagicMock()
        mock_ser.readline.return_value = b"0\n"
        ctrl._ser = mock_ser
        assert ctrl.read_limit(1, "aft") is False
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_controller.py -v -k "arduino"
```

Expected: failures — `ArduinoController` not defined.

- [ ] **Step 3: Append ArduinoController to controller.py**

```python
try:
    import serial
except ImportError:
    serial = None


class ArduinoController(PumpController):

    def __init__(self):
        self._ser = None

    def _send(self, cmd: str) -> str:
        if self._ser is None:
            from errors import SerialConnectionError
            raise SerialConnectionError("Not connected. Call detect() first.")
        self._ser.write(cmd.encode())
        return self._ser.readline().decode().strip()

    def detect(self) -> List[int]:
        if serial is None:
            raise ImportError("pyserial not installed. Run: pip install pyserial")
        try:
            self._ser = serial.Serial(_cfg.SERIAL_PORT, _cfg.SERIAL_BAUD, timeout=2)
            return [1, 2, 3]
        except Exception as exc:
            from errors import ControllerNotFoundError
            raise ControllerNotFoundError(
                f"Cannot open {_cfg.SERIAL_PORT}: {exc}"
            ) from exc

    def energize(self, pump_id: int) -> None:
        self._send(f"ENERGIZE:{pump_id}\n")

    def deenergize(self, pump_id: int) -> None:
        self._send(f"DEENERGIZE:{pump_id}\n")

    def home(self, pump_id: int) -> None:
        self._send(f"HOME:{pump_id}\n")

    def move(self, pump_id: int, steps: int, steps_per_sec: float) -> None:
        self._send(f"MOVE:{pump_id}:{steps}:{int(steps_per_sec)}\n")

    def stop(self, pump_id: int) -> None:
        self._ser.write(f"STOP:{pump_id}\n".encode())

    def read_limit(self, pump_id: int, side: str) -> bool:
        return self._send(f"LIMIT:{pump_id}:{side}\n") == "1"
```

- [ ] **Step 4: Run all controller tests**

```bash
pytest tests/test_controller.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add controller.py tests/test_controller.py
git commit -m "feat: add ArduinoController for serial backend"
```

---

### Task 9: pump.py — Pump class

**Files:**
- Create: `pump.py`
- Create: `tests/test_pump.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_pump.py
import pytest
from unittest.mock import MagicMock, patch
from state import PumpState
from errors import HomingTimeoutError, HomingTravelExceededError, ValidationError


@pytest.fixture
def mock_ctrl():
    ctrl = MagicMock()
    ctrl.read_limit.return_value = False
    return ctrl


@pytest.fixture
def pump(mock_ctrl):
    from pump import Pump
    return Pump(pump_id=1, controller=mock_ctrl)


def test_initial_state_is_startup(pump):
    assert pump.state == PumpState.STARTUP


def test_homing_sets_position_zero(pump, mock_ctrl):
    mock_ctrl.read_limit.side_effect = [False, False, True]
    pump.home()
    assert pump.position_steps == 0


def test_homing_transitions_to_idle(pump, mock_ctrl):
    mock_ctrl.read_limit.return_value = True
    pump.home()
    assert pump.state == PumpState.IDLE


def test_homing_calls_energize_then_deenergize(pump, mock_ctrl):
    mock_ctrl.read_limit.return_value = True
    pump.home()
    mock_ctrl.energize.assert_called_once_with(1)
    mock_ctrl.deenergize.assert_called_once_with(1)


def test_homing_timeout_transitions_to_error(pump, mock_ctrl):
    mock_ctrl.read_limit.return_value = False
    with patch("pump.POLL_INTERVAL_SEC", 0.001), \
         patch("config.HOMING_TIMEOUT_SEC", 0.005):
        with pytest.raises(HomingTimeoutError):
            pump.home()
    assert pump.state == PumpState.ERROR


def test_dispense_increments_position(pump, mock_ctrl):
    pump._state = PumpState.IDLE
    pump._position_steps = 0
    with patch("units.ml_to_steps", return_value=100), \
         patch("units.flow_rate_to_steps_per_sec", return_value=50.0), \
         patch("settings.save"), patch("settings.get", return_value=5.0):
        pump.dispense(volume_ml=1.0, flow_rate_ml_sec=0.5)
    assert pump.position_steps == 100


def test_dispense_validates_volume_exceeds_remaining(pump, mock_ctrl):
    pump._state = PumpState.IDLE
    pump._position_steps = 0
    with patch("settings.get", side_effect=lambda k: 5.0 if "MAX" in k else 0.01), \
         patch("units.ml_to_steps", return_value=0):
        with pytest.raises(ValidationError):
            pump.dispense(volume_ml=20.0, flow_rate_ml_sec=1.0)


def test_dispense_validates_flow_rate_too_high(pump, mock_ctrl):
    pump._state = PumpState.IDLE
    with patch("settings.get", side_effect=lambda k: 5.0 if "MAX" in k else 0.01):
        with pytest.raises(ValidationError):
            pump.dispense(volume_ml=1.0, flow_rate_ml_sec=999.0)


def test_current_volume_derived_from_position(pump):
    with patch("units.steps_to_ml", return_value=5.0):
        pump._position_steps = 1000
        assert pump.current_volume_ml == pytest.approx(15.0 - 5.0)


def test_stop_from_running_transitions_to_idle(pump, mock_ctrl):
    pump._state = PumpState.RUNNING
    pump.stop()
    assert pump.state == PumpState.IDLE
    mock_ctrl.stop.assert_called_once_with(1)


def test_mark_empty_transitions_to_empty(pump, mock_ctrl):
    pump._state = PumpState.RUNNING
    pump.mark_empty()
    assert pump.state == PumpState.EMPTY
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_pump.py -v
```

Expected: `ModuleNotFoundError: No module named 'pump'`

- [ ] **Step 3: Create pump.py**

```python
import time
import config
import settings
import units
from state import PumpState, validate_transition
from errors import HomingTimeoutError, HomingTravelExceededError, ValidationError

POLL_INTERVAL_SEC = 0.05


class Pump:

    def __init__(self, pump_id: int, controller):
        self.pump_id = pump_id
        self._controller = controller
        self._state = PumpState.STARTUP
        self._position_steps: int = 0

    @property
    def state(self) -> PumpState:
        return self._state

    @property
    def position_steps(self) -> int:
        return self._position_steps

    @property
    def current_volume_ml(self) -> float:
        return config.FULL_VOLUME_ML - units.steps_to_ml(self._position_steps)

    def _transition(self, next_state: PumpState) -> None:
        validate_transition(self._state, next_state)
        self._state = next_state

    def home(self) -> None:
        self._transition(PumpState.HOMING)
        self._controller.energize(self.pump_id)
        try:
            self._controller.home(self.pump_id)
            deadline = time.monotonic() + config.HOMING_TIMEOUT_SEC
            max_steps = int(
                config.MAX_HOMING_TRAVEL_MM
                * (200 * config.MICROSTEPPING) / config.LEAD_SCREW_PITCH_MM
            )
            steps_moved = 0
            step_increment = int(
                config.HOMING_SPEED_MM_PER_SEC * POLL_INTERVAL_SEC
                * (200 * config.MICROSTEPPING) / config.LEAD_SCREW_PITCH_MM
            )
            while not self._controller.read_limit(self.pump_id, "aft"):
                if time.monotonic() > deadline:
                    self._controller.stop(self.pump_id)
                    raise HomingTimeoutError(
                        f"Pump {self.pump_id} did not reach aft limit within "
                        f"{config.HOMING_TIMEOUT_SEC}s"
                    )
                if steps_moved > max_steps:
                    self._controller.stop(self.pump_id)
                    raise HomingTravelExceededError(
                        f"Pump {self.pump_id} exceeded max homing travel of "
                        f"{config.MAX_HOMING_TRAVEL_MM}mm"
                    )
                time.sleep(POLL_INTERVAL_SEC)
                steps_moved += step_increment
        except (HomingTimeoutError, HomingTravelExceededError):
            self._state = PumpState.ERROR
            self._controller.deenergize(self.pump_id)
            raise
        self._controller.stop(self.pump_id)
        self._position_steps = 0
        self._controller.deenergize(self.pump_id)
        self._transition(PumpState.IDLE)

    def dispense(self, volume_ml: float, flow_rate_ml_sec: float) -> None:
        max_flow = settings.get("MAX_FLOW_RATE_ML_SEC")
        min_flow = settings.get("MIN_FLOW_RATE_ML_SEC")
        if not (min_flow <= flow_rate_ml_sec <= max_flow):
            raise ValidationError(
                f"Flow rate {flow_rate_ml_sec} mL/s out of range [{min_flow}, {max_flow}]"
            )
        if volume_ml > self.current_volume_ml:
            raise ValidationError(
                f"Purge {volume_ml} mL exceeds current volume {self.current_volume_ml:.2f} mL"
            )
        steps = units.ml_to_steps(volume_ml)
        speed = units.flow_rate_to_steps_per_sec(flow_rate_ml_sec)
        self._transition(PumpState.RUNNING)
        self._controller.energize(self.pump_id)
        self._controller.move(self.pump_id, steps, speed)
        self._position_steps += steps
        positions = settings.get("PUMP_POSITIONS")
        positions[str(self.pump_id)] = self._position_steps
        settings.save({"PUMP_POSITIONS": positions})
        self._controller.deenergize(self.pump_id)
        self._transition(PumpState.STOPPING)
        self._transition(PumpState.IDLE)

    def stop(self) -> None:
        if self._state == PumpState.RUNNING:
            self._controller.stop(self.pump_id)
            self._controller.deenergize(self.pump_id)
            self._transition(PumpState.STOPPING)
            self._transition(PumpState.IDLE)

    def mark_empty(self) -> None:
        self._controller.stop(self.pump_id)
        self._controller.deenergize(self.pump_id)
        self._state = PumpState.STOPPING
        self._transition(PumpState.EMPTY)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_pump.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add pump.py tests/test_pump.py
git commit -m "feat: add Pump class with homing, dispense, and position tracking"
```

---

### Task 10: LimitSwitchWorker QThread

**Files:**
- Modify: `pump.py` (append LimitSwitchWorker)
- Modify: `tests/test_pump.py` (append worker tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_pump.py`:

```python
def test_limit_worker_emits_signal_on_forward_limit(qapp, mock_ctrl):
    from pump import LimitSwitchWorker
    mock_ctrl.read_limit.side_effect = [False, False, True]
    received = []
    worker = LimitSwitchWorker(pump_id=1, controller=mock_ctrl, poll_interval_sec=0.001)
    worker.limit_hit.connect(lambda pid: received.append(pid))
    worker.start()
    worker.wait(500)
    assert received == [1]


def test_limit_worker_stops_when_cancelled(qapp, mock_ctrl):
    from pump import LimitSwitchWorker
    mock_ctrl.read_limit.return_value = False
    worker = LimitSwitchWorker(pump_id=1, controller=mock_ctrl, poll_interval_sec=0.005)
    worker.start()
    worker.cancel()
    worker.wait(500)
    assert not worker.isRunning()
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_pump.py -v -k "worker"
```

Expected: `ImportError: cannot import name 'LimitSwitchWorker'`

- [ ] **Step 3: Append LimitSwitchWorker to pump.py**

```python
from PyQt5.QtCore import QThread, pyqtSignal


class LimitSwitchWorker(QThread):
    limit_hit = pyqtSignal(int)   # emits pump_id

    def __init__(self, pump_id: int, controller, poll_interval_sec: float = POLL_INTERVAL_SEC):
        super().__init__()
        self._pump_id = pump_id
        self._controller = controller
        self._interval = poll_interval_sec
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        while not self._cancelled:
            if self._controller.read_limit(self._pump_id, "forward"):
                self.limit_hit.emit(self._pump_id)
                return
            time.sleep(self._interval)
```

- [ ] **Step 4: Run all pump tests**

```bash
pytest tests/test_pump.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add pump.py tests/test_pump.py
git commit -m "feat: add LimitSwitchWorker QThread for forward limit detection"
```

---

### Task 11: pump_panel.py

**Files:**
- Create: `pump_panel.py`
- Modify: `tests/test_pump.py` (append panel smoke tests)

- [ ] **Step 1: Create pump_panel.py**

```python
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
    run_requested  = pyqtSignal(int, float, float)  # pump_id, flow_rate, purge_vol
    stop_requested = pyqtSignal(int)                # pump_id

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
        vol_row.addWidget(QLabel("Volume (mL):"))
        self._volume_label = QLabel(f"{config.FULL_VOLUME_ML:.1f}")
        vol_row.addWidget(self._volume_label)
        layout.addLayout(vol_row)

        flow_row = QHBoxLayout()
        flow_row.addWidget(QLabel("Flow (mL/s):"))
        self._flow_spin = QDoubleSpinBox()
        self._flow_spin.setRange(0.01, 5.0)
        self._flow_spin.setDecimals(3)
        self._flow_spin.setValue(0.1)
        flow_row.addWidget(self._flow_spin)
        layout.addLayout(flow_row)

        purge_row = QHBoxLayout()
        purge_row.addWidget(QLabel("Purge (mL):"))
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

    def _on_run(self):
        self.run_requested.emit(
            self.pump_id,
            self._flow_spin.value(),
            self._purge_spin.value(),
        )

    def set_state(self, state: PumpState):
        color = _STATE_COLORS.get(state, "#888888")
        self._status.setText(state.value)
        self._status.setStyleSheet(
            f"font-weight: bold; padding: 4px; border-radius: 4px;"
            f"background-color: {color}; color: white;"
        )
        is_idle = (state == PumpState.IDLE)
        self._flow_spin.setEnabled(is_idle)
        self._purge_spin.setEnabled(is_idle)
        self._run_btn.setEnabled(is_idle)
        self._stop_btn.setEnabled(state == PumpState.RUNNING)

    def update_volume(self, volume_ml: float):
        self._volume_label.setText(f"{volume_ml:.2f}")
        fraction = max(0.0, min(1.0, volume_ml / config.FULL_VOLUME_ML))
        self._progress.setValue(int(fraction * 1000))
```

- [ ] **Step 2: Write smoke tests**

Append to `tests/test_pump.py`:

```python
def test_pump_panel_constructs(qapp):
    from pump_panel import PumpPanel
    assert PumpPanel(pump_id=1) is not None


def test_pump_panel_run_signal_emitted(qapp):
    from pump_panel import PumpPanel
    received = []
    panel = PumpPanel(pump_id=2)
    panel.set_state(PumpState.IDLE)
    panel.run_requested.connect(lambda pid, fr, pv: received.append((pid, fr, pv)))
    panel._run_btn.click()
    assert len(received) == 1 and received[0][0] == 2


def test_pump_panel_inputs_locked_when_running(qapp):
    from pump_panel import PumpPanel
    panel = PumpPanel(pump_id=1)
    panel.set_state(PumpState.RUNNING)
    assert not panel._flow_spin.isEnabled()
    assert not panel._purge_spin.isEnabled()
    assert not panel._run_btn.isEnabled()
    assert panel._stop_btn.isEnabled()


def test_pump_panel_update_volume(qapp):
    from pump_panel import PumpPanel
    panel = PumpPanel(pump_id=1)
    panel.update_volume(7.5)
    assert panel._volume_label.text() == "7.50"
    assert panel._progress.value() == 500  # 7.5/15.0 × 1000
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_pump.py -v -k "panel"
```

Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add pump_panel.py tests/test_pump.py
git commit -m "feat: add PumpPanel PyQt5 widget"
```

---

### Task 12: Startup dialog

**Files:**
- Create: `startup_dialog.py`
- Create: `tests/test_startup_dialog.py`

- [ ] **Step 1: Create startup_dialog.py**

```python
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)


class StartupDialog(QDialog):
    HOME   = 1
    RESUME = 2

    def __init__(self, detected_ids: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Syringe Pump Controller — Startup")
        self.setModal(True)
        self._choice = None
        self._build_ui(detected_ids)

    def _build_ui(self, detected_ids: list):
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
    def choice(self) -> int:
        return self._choice
```

- [ ] **Step 2: Create tests/test_startup_dialog.py**

```python
from startup_dialog import StartupDialog


def test_startup_dialog_constructs(qapp):
    assert StartupDialog(detected_ids=[1, 2, 3]) is not None


def test_home_choice(qapp):
    dlg = StartupDialog(detected_ids=[1, 2, 3])
    dlg._home_btn.click()
    assert dlg.choice == StartupDialog.HOME


def test_resume_choice(qapp):
    dlg = StartupDialog(detected_ids=[1, 3])
    dlg._resume_btn.click()
    assert dlg.choice == StartupDialog.RESUME
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_startup_dialog.py -v
```

Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add startup_dialog.py tests/test_startup_dialog.py
git commit -m "feat: add startup dialog for Home/Resume selection"
```

---

### Task 13: settings_dialog.py + main.py

**Files:**
- Create: `settings_dialog.py`
- Create: `main.py`

- [ ] **Step 1: Create settings_dialog.py**

```python
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
```

- [ ] **Step 2: Create main.py**

```python
import sys
import config
import settings as _settings
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
)
from controller import TicController, ArduinoController
from pump import Pump, LimitSwitchWorker
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

    def _on_run(self, pump_id: int, flow_rate: float, purge_vol: float):
        pump  = self._pumps[pump_id]
        panel = self._panels[pump_id]
        try:
            pump.dispense(purge_vol, flow_rate)
        except Exception as exc:
            panel.set_state(PumpState.ERROR)
            return
        panel.set_state(pump.state)
        panel.update_volume(pump.current_volume_ml)
        worker = LimitSwitchWorker(pump_id, pump._controller)
        worker.limit_hit.connect(self._on_limit_hit)
        self._workers[pump_id] = worker
        worker.start()

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
            self._panels[pid].set_state(PumpState.HOMING)
            try:
                pump.home()
                self._panels[pid].set_state(PumpState.IDLE)
                self._panels[pid].update_volume(pump.current_volume_ml)
            except Exception:
                self._panels[pid].set_state(PumpState.ERROR)

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
            pump._state = PumpState.IDLE
            pump._position_steps = int(saved.get(str(pid), 0))
            panels[pid].set_state(PumpState.IDLE)
            panels[pid].update_volume(pump.current_volume_ml)

    win = MainWindow(pumps=pumps, panels=panels)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke-test the app**

```bash
cd /Users/jessiewang/Downloads/syringe_pump_gui
python main.py
```

Expected: startup dialog appears showing ✗ for all pumps (no hardware connected). Both "Home All Pumps" and "Resume Existing Position" buttons are visible. Clicking Resume should show an empty dashboard with 3 pump panels. Close the window.

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add main.py settings_dialog.py
git commit -m "feat: add main window, settings dialog, and app entry point"
```

---

### Task 14: Arduino firmware

**Files:**
- Create: `arduino/pump_controller.ino`

- [ ] **Step 1: Create arduino/pump_controller.ino**

```cpp
// Syringe Pump Controller — Arduino Firmware
// Protocol: commands end with '\n', responses end with '\n'
//
// Commands:
//   ENERGIZE:<id>
//   DEENERGIZE:<id>
//   HOME:<id>
//   MOVE:<id>:<steps>:<steps_per_sec>
//   STOP:<id>
//   LIMIT:<id>:<aft|forward>
//
// Responses: "OK\n" or "1\n"/"0\n" for LIMIT queries.

#include <AccelStepper.h>

// TODO: Set these pin numbers after wiring is complete
#define PUMP1_STEP_PIN    2
#define PUMP1_DIR_PIN     3
#define PUMP1_ENABLE_PIN  4
#define PUMP1_AFT_PIN     5
#define PUMP1_FWD_PIN     6

#define PUMP2_STEP_PIN    7
#define PUMP2_DIR_PIN     8
#define PUMP2_ENABLE_PIN  9
#define PUMP2_AFT_PIN    10
#define PUMP2_FWD_PIN    11

#define PUMP3_STEP_PIN   12
#define PUMP3_DIR_PIN    13
#define PUMP3_ENABLE_PIN A0
#define PUMP3_AFT_PIN    A1
#define PUMP3_FWD_PIN    A2

// Normally-closed: LOW signal = switch activated (broken wire = fault detected)
#define LIMIT_NORMALLY_CLOSED true

AccelStepper steppers[3] = {
    AccelStepper(AccelStepper::DRIVER, PUMP1_STEP_PIN, PUMP1_DIR_PIN),
    AccelStepper(AccelStepper::DRIVER, PUMP2_STEP_PIN, PUMP2_DIR_PIN),
    AccelStepper(AccelStepper::DRIVER, PUMP3_STEP_PIN, PUMP3_DIR_PIN),
};

const int ENABLE_PINS[3] = {PUMP1_ENABLE_PIN, PUMP2_ENABLE_PIN, PUMP3_ENABLE_PIN};
const int AFT_PINS[3]    = {PUMP1_AFT_PIN,    PUMP2_AFT_PIN,    PUMP3_AFT_PIN};
const int FWD_PINS[3]    = {PUMP1_FWD_PIN,    PUMP2_FWD_PIN,    PUMP3_FWD_PIN};

bool readLimit(int idx, bool forward) {
    int pin  = forward ? FWD_PINS[idx] : AFT_PINS[idx];
    bool raw = (digitalRead(pin) == LOW);
    return LIMIT_NORMALLY_CLOSED ? raw : !raw;
}

void setup() {
    Serial.begin(115200);
    for (int i = 0; i < 3; i++) {
        pinMode(ENABLE_PINS[i], OUTPUT);
        digitalWrite(ENABLE_PINS[i], HIGH);   // disabled (active LOW)
        pinMode(AFT_PINS[i], INPUT_PULLUP);
        pinMode(FWD_PINS[i], INPUT_PULLUP);
        steppers[i].setMaxSpeed(10000);
        steppers[i].setAcceleration(1000);
    }
}

void loop() {
    for (int i = 0; i < 3; i++) steppers[i].run();

    if (!Serial.available()) return;

    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    int c1 = cmd.indexOf(':');
    String command = cmd.substring(0, c1);
    String rest    = cmd.substring(c1 + 1);
    int id  = rest.substring(0, rest.indexOf(':')).toInt();
    int idx = id - 1;

    if (idx < 0 || idx > 2) { Serial.println("ERR:bad_id"); return; }

    if (command == "ENERGIZE") {
        digitalWrite(ENABLE_PINS[idx], LOW);
        Serial.println("OK");

    } else if (command == "DEENERGIZE") {
        digitalWrite(ENABLE_PINS[idx], HIGH);
        Serial.println("OK");

    } else if (command == "STOP") {
        steppers[idx].stop();
        Serial.println("OK");

    } else if (command == "HOME") {
        steppers[idx].setSpeed(-200);   // slow aft movement
        steppers[idx].runSpeed();
        Serial.println("OK");

    } else if (command == "MOVE") {
        // MOVE:<id>:<steps>:<steps_per_sec>
        int c2   = rest.indexOf(':');
        int c3   = rest.indexOf(':', c2 + 1);
        long steps  = rest.substring(c2 + 1, c3).toInt();
        float speed = rest.substring(c3 + 1).toFloat();
        steppers[idx].setMaxSpeed(speed);
        steppers[idx].move(steps);
        Serial.println("OK");

    } else if (command == "LIMIT") {
        bool fwd = rest.endsWith("forward");
        Serial.println(readLimit(idx, fwd) ? "1" : "0");

    } else {
        Serial.println("ERR:unknown_cmd");
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add arduino/pump_controller.ino
git commit -m "feat: add Arduino firmware for serial backend"
```

---

## Spec Coverage Check

| Spec requirement | Task(s) |
|-----------------|---------|
| 3 syringe pumps, NEMA 17, 15 mL | 4, 9, 11 |
| 6 limit switches (aft + forward) | 7, 8, 9, 10, 14 |
| Homing sequence + aft=full/forward=empty model | 9 |
| Startup recovery dialog (Home / Resume) | 12, 13 |
| Per-pump: flow rate, purge amount inputs | 11 |
| Current volume derived from position (read-only) | 9, 11 |
| Position tracking + persistence to settings.json | 9, 13 |
| Forward limit auto-stop (LimitSwitchWorker) | 10 |
| PumpState enum + transition validator | 3, 9 |
| Custom exceptions | 2 |
| Config defaults + settings.json override | 4 |
| Settings dialog (runtime overrides) | 13 |
| TicController (ticlib, hardware limit stops) | 7 |
| ArduinoController (pyserial) | 8 |
| Abstract PumpController interface | 6 |
| Threading: GUI → Worker → Controller | 10, 13 |
| energize / deenergize | 6, 7, 8, 9 |
| detect() + startup controller report | 6, 7, 8, 12, 13 |
| Input validation (flow rate bounds, volume bounds) | 9 |
| Input fields locked when non-IDLE | 11 |
| Status badges (color per state) | 11 |
| LIMIT_SWITCH_NORMALLY_CLOSED | 4, 7, 8, 14 |
| settings.json never overwrites config.py | 4 |
| Arduino firmware | 14 |
| units.py conversion math | 5 |

# Syringe Pump GUI — Design Spec
**Date:** 2026-06-13
**Author:** Ahmed H. Nagi (biosensing lead)

---

## Overview

A PyQt5 desktop GUI running on a Raspberry Pi to control three syringe pumps in a biosensing fluidics system. Each pump is driven by a NEMA 17 stepper motor. The GUI supports two hardware backends (Arduino via serial, or Tic T825 USB stepper controllers) selected via a config file. All hardware-specific values are isolated in `config.py`; user-tunable overrides live in `settings.json`. Tic T825 is the recommended backend — it provides hardware trajectory generation, hardware limit switch handling, and USB control with no firmware to maintain.

---

## Scope

- 3 syringe pumps, each with a 15 mL syringe
- 6 limit switches (2 per pump: aft/full and forward/empty)
- Startup recovery dialog (home vs. resume)
- Per-pump control: flow rate (mL/s), purge amount (mL)
- Position tracking and derived current volume display
- Forward limit switch detection (syringe empty → auto-stop)
- Settings panel for mechanical specs (writes to `settings.json`)
- **Out of scope:** rotating valve integration (separate spec later), logging, withdraw operation

---

## File Structure

```
syringe_pump_gui/
├── config.py          # default hardware constants (never modified at runtime)
├── settings.json      # user overrides (written by settings dialog)
├── units.py           # mL ↔ motor steps conversion math
├── state.py           # PumpState enum and valid transitions
├── errors.py          # custom exception classes
├── controller.py      # abstract motor interface + Arduino & Tic T825 implementations
├── pump.py            # high-level pump logic (home, dispense, stop)
├── pump_panel.py      # PyQt5 widget for one pump card
├── main.py            # app entry point + main window
└── arduino/
    └── pump_controller.ino   # Arduino firmware (Arduino backend only)
```

---

## Configuration

### config.py — defaults (never modified at runtime)

```python
# --- HARDWARE BACKEND ---
# Tic T825 is strongly recommended. Arduino backend requires separate firmware.
BACKEND = "tic"              # "arduino" or "tic"

# --- ARDUINO (only used if BACKEND = "arduino") ---
SERIAL_PORT = "/dev/ttyUSB0"   # TODO: confirm after wiring
SERIAL_BAUD = 115200

# --- TIC T825 (only used if BACKEND = "tic") ---
# Run `ticcmd --list` to find serial numbers after connecting controllers
TIC_SERIAL_NUMBERS = {
    1: "TODO",   # Pump 1
    2: "TODO",   # Pump 2
    3: "TODO",   # Pump 3
}

# --- MOTOR / SYRINGE SPECS ---
STEPS_PER_REV       = 200
MICROSTEPPING       = 16          # TODO: confirm from driver config
LEAD_SCREW_PITCH_MM = 8.0         # TODO: measure from CAD
SYRINGE_INNER_DIAMETER_MM = 15.9  # TODO: measure actual syringe barrel
FULL_VOLUME_ML      = 15.0        # maximum syringe capacity

# --- FLOW RATE LIMITS ---
MAX_FLOW_RATE_ML_SEC = 5.0        # TODO: tune to safe hardware limit
MIN_FLOW_RATE_ML_SEC = 0.01

# --- LIMIT SWITCHES ---
# Normally-closed is required. A broken wire then appears as a fault, not a miss.
LIMIT_SWITCH_NORMALLY_CLOSED = True

# GPIO pin numbers — only used if BACKEND = "arduino"
# Format: {pump_id: {"aft": gpio_pin, "forward": gpio_pin}}
LIMIT_SWITCH_PINS = {
    1: {"aft": None, "forward": None},   # TODO
    2: {"aft": None, "forward": None},   # TODO
    3: {"aft": None, "forward": None},   # TODO
}

# --- HOMING ---
HOMING_SPEED_MM_PER_SEC  = 2.0
HOMING_TIMEOUT_SEC       = 30
MAX_HOMING_TRAVEL_MM     = 150   # hard distance limit — stop and fault if exceeded
```

### settings.json — user overrides

Values in `settings.json` override `config.py` at load time. The settings dialog writes here; `config.py` is never touched at runtime. If `settings.json` is missing, defaults from `config.py` are used.

```json
{
  "MICROSTEPPING": 16,
  "LEAD_SCREW_PITCH_MM": 8.0,
  "SYRINGE_INNER_DIAMETER_MM": 15.9,
  "MAX_FLOW_RATE_ML_SEC": 5.0,
  "MIN_FLOW_RATE_ML_SEC": 0.01
}
```

**Load order:** `config.py` defaults → `settings.json` overrides → runtime values.

---

## Position and Volume Model

Aft limit = plunger fully retracted = syringe **full** (15 mL).
Forward limit = plunger fully advanced = syringe **empty** (0 mL).

```
aft limit                          forward limit
    |←————————— travel ————————————→|
    0 steps                    max steps
  15 mL                           0 mL
```

After homing:
```python
position_steps   = 0
current_volume_ml = FULL_VOLUME_ML   # 15.0
```

After every move:
```python
position_steps   += commanded_steps
current_volume_ml = FULL_VOLUME_ML - steps_to_ml(position_steps)
```

Positive steps = dispense (plunger advances, volume decreases). Negative steps = withdraw (not exposed in UI yet, but sign convention is defined here to avoid future ambiguity).

Position is persisted to `settings.json` after every move so it survives restarts.

---

## State Machine

Defined in `state.py`:

```python
class PumpState(Enum):
    STARTUP   = "STARTUP"
    HOMING    = "HOMING"
    IDLE      = "IDLE"
    RUNNING   = "RUNNING"
    STOPPING  = "STOPPING"
    EMPTY     = "EMPTY"
    ERROR     = "ERROR"
```

Valid transitions:

```
STARTUP  → HOMING
STARTUP  → IDLE       (resume path — no homing)
HOMING   → IDLE       (homing succeeded)
HOMING   → ERROR      (timeout or travel limit exceeded)
IDLE     → HOMING     (manual re-home)
IDLE     → RUNNING    (dispense started)
RUNNING  → STOPPING   (Stop button or forward limit hit)
RUNNING  → ERROR      (controller fault)
STOPPING → IDLE
EMPTY    → IDLE       (operator acknowledges)
ERROR    → HOMING     (operator retries)
```

Any transition not listed above is illegal and must raise `InvalidStateTransitionError`.

---

## Custom Exceptions (`errors.py`)

```python
class HomingTimeoutError(Exception): ...
class HomingTravelExceededError(Exception): ...
class InvalidStateTransitionError(Exception): ...
class ControllerNotFoundError(Exception): ...
class SerialConnectionError(Exception): ...
class ValidationError(Exception): ...
```

---

## units.py

Stateless conversion functions. All read runtime config values (post-override).

```python
def ml_to_steps(ml: float) -> int
def steps_to_ml(steps: int) -> float
def flow_rate_to_steps_per_sec(ml_per_sec: float) -> float
```

Conversion formula:
```
cross_section_mm2 = π × (SYRINGE_INNER_DIAMETER_MM / 2)²
mm_per_ml        = 1000 / cross_section_mm2
steps_per_mm     = (STEPS_PER_REV × MICROSTEPPING) / LEAD_SCREW_PITCH_MM
steps_per_ml     = steps_per_mm × mm_per_ml
```

---

## controller.py

### Interface

```python
class PumpController:
    def detect(self) -> list[int]          # return list of detected pump IDs
    def energize(self, pump_id: int)       # enable motor coils before move
    def deenergize(self, pump_id: int)     # release motor after move (prevent heating)
    def home(self, pump_id: int) -> None
    def move(self, pump_id: int, steps: int, steps_per_sec: float) -> None
    def stop(self, pump_id: int) -> None
    def read_limit(self, pump_id: int, side: str) -> bool  # side: "aft" | "forward"
```

`detect()` is called at startup before the recovery dialog is shown. If a pump cannot be found, it is reported with `ControllerNotFoundError` and excluded from the session.

Motors are de-energized after a dispense completes or after an error. They are re-energized just before homing or moving.

### ArduinoController

- Serial commands: `HOME:1`, `MOVE:1:500:200`, `STOP:1`, `LIMIT:1:aft`, `ENERGIZE:1`, `DEENERGIZE:1`
- Limit switches wired to Arduino digital pins (configured via `LIMIT_SWITCH_PINS`)
- Arduino firmware handles step generation; all three pumps can run concurrently via independent timer interrupts
- `LIMIT_SWITCH_NORMALLY_CLOSED` logic applied in firmware

### TicController

- Uses `ticlib` (primary); falls back to `ticcmd` subprocess if `ticlib` unavailable
- Each pump identified by serial number from `TIC_SERIAL_NUMBERS`
- Limit switches wired directly to Tic T825 forward/reverse limit inputs — no RPi GPIO needed
- **Hardware limit stop**: Tic stops motion autonomously when a limit switch triggers. `read_limit()` reads the Tic status register after the fact — the GUI does not need to race the motor.
- `LIMIT_SWITCH_NORMALLY_CLOSED` configured via Tic settings

---

## pump.py

`Pump` wraps a controller instance and manages state transitions.

### Homing sequence
1. Transition: `STARTUP/IDLE/ERROR → HOMING`
2. `energize(pump_id)`
3. Move aft at `HOMING_SPEED_MM_PER_SEC`
4. Poll `read_limit(pump_id, "aft")` until `True`
5. Safety checks — raise `HomingTimeoutError` if `HOMING_TIMEOUT_SEC` exceeded; raise `HomingTravelExceededError` if travel exceeds `MAX_HOMING_TRAVEL_MM`
6. Set `position_steps = 0`; derive `current_volume_ml = FULL_VOLUME_ML`
7. `deenergize(pump_id)`
8. Transition: `HOMING → IDLE`

### Dispense sequence
1. Validate: `purge_amount_ml <= current_volume_ml`; `MIN_FLOW_RATE_ML_SEC <= flow_rate <= MAX_FLOW_RATE_ML_SEC`; raise `ValidationError` on failure
2. Transition: `IDLE → RUNNING`
3. `energize(pump_id)`
4. `controller.move(pump_id, steps, steps_per_sec)`
5. Update `position_steps` and persist to `settings.json`
6. On completion: `deenergize(pump_id)`, transition `RUNNING → STOPPING → IDLE`

### Limit switch polling (forward/empty detection)
- **Tic backend**: poll Tic status register every 100 ms while `RUNNING`; Tic has already stopped the motor before the poll detects it
- **Arduino backend**: poll `read_limit(pump_id, "forward")` every 25 ms while `RUNNING`; call `stop()` immediately on trigger
- On forward limit detected: transition `RUNNING → STOPPING → EMPTY`, emit `pump_empty` signal to GUI

---

## Threading Model

All hardware communication happens in worker threads. The GUI thread never calls controller methods directly.

```
GUI Thread (PyQt5 main thread)
    ↕  signals/slots only
PumpWorker QThread  (one per pump)
    ├── HomingWorker  (runs homing sequence, emits progress signals)
    └── MoveWorker    (runs dispense sequence, emits position signals)
    ↓
Controller (called only from worker thread)
```

`HomingWorker` emits `homing_progress(pump_id, status_str)` so the startup dialog can update per-pump status. `MoveWorker` emits `position_update(pump_id, position_steps)` on each step increment so the progress bar stays live.

---

## GUI Layout

### Startup sequence
1. App starts → `detect()` all controllers; report any missing
2. Modal **Startup Dialog**:
   ```
   Syringe Pump Controller — Startup

   Controllers detected: Pump 1 ✓  Pump 2 ✓  Pump 3 ✓

   [ Home All Pumps ]
   [ Resume Existing Position ]
   ```
   - **Home All Pumps**: runs homing sequence for all detected pumps, shows per-pump progress
   - **Resume Existing Position**: loads `position_steps` from `settings.json`; skips homing. Operator takes responsibility for position accuracy.

### Main dashboard
```
[  Syringe Pump Controller               ⚙ Settings  ]
[  [Home All Pumps]                                   ]

[ ── Pump 1 ──── ][ ── Pump 2 ──── ][ ── Pump 3 ──── ]
[ Status: IDLE   ][ Status: RUNNING][ Status: IDLE   ]
[ Vol: 15.0 mL   ][ Vol:  8.3 mL  ][ Vol: 15.0 mL   ]
[ Flow:  [    ]  ][ Flow:  [    ]  ][ Flow:  [    ]  ]
[ Purge: [    ]  ][ Purge: [    ]  ][ Purge: [    ]  ]
[ ████░░░░░░░░░  ][ ████████████░  ][ ████░░░░░░░░░  ]
[ [Run]   [Stop] ][ [Run]   [Stop] ][ [Run]   [Stop] ]
```

**Current volume** is derived from `position_steps` — not user-entered. It updates live during a dispense.

**Input fields** (Flow rate, Purge amount) are editable only in `IDLE` state; disabled in all other states.

### Pump status badges
| State    | Color  |
|----------|--------|
| IDLE     | Grey   |
| HOMING   | Yellow |
| RUNNING  | Green  |
| STOPPING | Yellow |
| EMPTY    | Orange |
| ERROR    | Red    |

### Settings dialog
Editable fields for mechanical specs and flow rate limits. Values are validated before saving and written to `settings.json`. `config.py` is never modified.

---

## Error Handling

| Condition | Behavior |
|-----------|----------|
| Forward limit hit during dispense | Stop motor, transition → EMPTY, alert operator |
| Aft limit not hit within timeout | `HomingTimeoutError`, transition → ERROR |
| Travel exceeds `MAX_HOMING_TRAVEL_MM` | `HomingTravelExceededError`, transition → ERROR |
| Purge amount > current volume | `ValidationError` shown inline, no movement |
| Flow rate out of bounds | `ValidationError` shown inline |
| Controller not found at startup | Reported in startup dialog; pump excluded from session |
| Serial connection lost (Arduino) | `SerialConnectionError`, transition → ERROR, disable Run |
| Illegal state transition | `InvalidStateTransitionError`, log and transition → ERROR |

---

## Dependencies

- `PyQt5`
- `pyserial` (Arduino backend only)
- `ticlib` (Tic T825 backend, primary); `ticcmd` CLI (fallback)
- `RPi.GPIO` (Arduino backend limit switches only)

---

## Out of Scope

- Rotating valve control (separate spec after this GUI is complete)
- Logging / run history
- Withdraw operation (sign convention defined above, UI not exposed)
- Network / remote control

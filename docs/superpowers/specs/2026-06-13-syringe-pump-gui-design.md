# Syringe Pump GUI — Design Spec
**Date:** 2026-06-13
**Author:** Ahmed H. Nagi (biosensing lead)

---

## Overview

A PyQt5 desktop GUI running on a Raspberry Pi to control three syringe pumps in a biosensing fluidics system. Each pump is driven by a NEMA 17 stepper motor. The GUI supports two hardware backends (Arduino via serial, or Tic T825 USB stepper controllers) selected via a config file. All hardware-specific values are isolated in `config.py` and left as labeled placeholders until the circuit is finalized.

---

## Scope

- 3 syringe pumps, each with a 15 mL syringe
- 6 limit switches (2 per pump: aft/home and forward/empty)
- Homing sequence on startup
- Per-pump control: flow rate, purge amount, current volume
- Forward limit switch detection (syringe empty → auto-stop)
- Settings panel for mechanical specs
- **Out of scope:** rotating valve integration (separate spec later)

---

## File Structure

```
syringe_pump_gui/
├── config.py          # all hardware constants (fill in after wiring)
├── units.py           # mL ↔ motor steps conversion math
├── controller.py      # abstract motor interface + Arduino & Tic T825 implementations
├── pump.py            # high-level pump logic (home, run, stop, limit detection)
├── pump_panel.py      # PyQt5 widget for one pump card
├── main.py            # app entry point + main window
└── arduino/
    └── pump_controller.ino   # Arduino firmware for Arduino backend
```

---

## config.py

All hardware-specific constants live here. The rest of the codebase reads from this file. Placeholder values are marked `# TODO`.

```python
# --- HARDWARE BACKEND ---
BACKEND = "tic"              # "arduino" or "tic"

# --- ARDUINO (only used if BACKEND = "arduino") ---
SERIAL_PORT = "/dev/ttyUSB0"   # TODO: confirm after wiring
SERIAL_BAUD = 115200

# --- TIC T825 (only used if BACKEND = "tic") ---
TIC_SERIAL_NUMBERS = {
    1: "TODO",   # Pump 1
    2: "TODO",   # Pump 2
    3: "TODO",   # Pump 3
}

# --- MOTOR / SYRINGE SPECS ---
STEPS_PER_REV = 200
MICROSTEPPING = 16             # TODO: confirm from driver config
LEAD_SCREW_PITCH_MM = 8.0      # TODO: measure from CAD
SYRINGE_INNER_DIAMETER_MM = 15.9  # TODO: measure actual syringe

# --- LIMIT SWITCHES (RPi GPIO, only used if BACKEND = "arduino") ---
LIMIT_SWITCH_PINS = {
    1: {"aft": None, "forward": None},   # TODO
    2: {"aft": None, "forward": None},   # TODO
    3: {"aft": None, "forward": None},   # TODO
}

# --- HOMING ---
HOMING_SPEED_MM_PER_SEC = 2.0
HOMING_TIMEOUT_SEC = 30
```

---

## units.py

Stateless conversion functions. All read from `config.py`.

- `ml_to_steps(ml) -> int` — converts mL to motor steps using syringe cross-section and lead screw pitch
- `flow_rate_to_steps_per_sec(ml_per_sec) -> float` — converts mL/s to steps/sec
- `steps_to_ml(steps) -> float` — inverse, used for progress display

**Conversion formula:**
```
cross_section_mm2 = π × (SYRINGE_INNER_DIAMETER_MM / 2)²
mm_per_ml = 1000 / cross_section_mm2        # 1 mL = 1000 mm³
steps_per_mm = (STEPS_PER_REV × MICROSTEPPING) / LEAD_SCREW_PITCH_MM
steps_per_ml = steps_per_mm × mm_per_ml
```

---

## controller.py

Abstract base class + two concrete implementations.

### Interface

```python
class PumpController:
    def home(self, pump_id: int) -> None
    def move(self, pump_id: int, steps: int, steps_per_sec: float) -> None
    def stop(self, pump_id: int) -> None
    def read_limit(self, pump_id: int, side: str) -> bool  # side: "aft" | "forward"
```

### ArduinoController

- Communicates over serial (pyserial) using short command strings:
  - `HOME:1` → home pump 1
  - `MOVE:1:500:200` → move pump 1, 500 steps at 200 steps/sec
  - `STOP:1` → stop pump 1
  - `LIMIT:1:aft` → query aft limit switch on pump 1
- Arduino firmware (separate `.ino`) handles step generation and reports limit states
- Limit switches wired to Arduino digital pins (pin numbers in `config.py`)

### TicController

- Uses `ticlib` Python library (primary); falls back to `ticcmd` subprocess if `ticlib` unavailable
- Identifies each pump's Tic by serial number from `config.py`
- Limit switches wired directly to Tic T825 forward/reverse limit inputs (no extra GPIO needed)
- `read_limit()` reads from Tic status register

---

## pump.py

`Pump` class wraps a `PumpController` instance and exposes high-level operations.

### Homing
1. Move aft at `HOMING_SPEED_MM_PER_SEC` until `read_limit(pump_id, "aft")` returns `True`
2. Mark current position as 15 mL origin
3. Raise `HomingTimeoutError` if aft limit not triggered within `HOMING_TIMEOUT_SEC`

### Purge
1. Validate: `purge_amount <= current_volume`
2. Convert inputs via `units.py`
3. Call `controller.move(pump_id, steps, steps_per_sec)`
4. Track steps remaining to update progress bar

### Limit switch polling
- Runs in a `QThread` background worker
- Polls `read_limit(pump_id, "forward")` every 50 ms while pump is running
- On trigger: calls `controller.stop()`, emits `pump_empty` signal to GUI

---

## GUI Layout

### Main window

```
[  Syringe Pump Controller               ⚙ Settings  ]
[  [Home All Pumps]                                   ]

[ ── Pump 1 ──── ][ ── Pump 2 ──── ][ ── Pump 3 ──── ]
[ Status: IDLE   ][ Status: RUNNING][ Status: IDLE   ]
[ Flow:  [    ]  ][ Flow:  [    ]  ][ Flow:  [    ]  ]
[ Purge: [    ]  ][ Purge: [    ]  ][ Purge: [    ]  ]
[ Vol:   [    ]  ][ Vol:   [    ]  ][ Vol:   [    ]  ]
[ ████░░░░░░░░░  ][ ████████████░  ][ ████░░░░░░░░░  ]
[ [Run]   [Stop] ][ [Run]   [Stop] ][ [Run]   [Stop] ]
```

### Pump status badges
| State | Color |
|-------|-------|
| IDLE | Grey |
| HOMING | Yellow |
| RUNNING | Green |
| EMPTY | Orange |
| ERROR | Red |

### Startup homing dialog
Modal dialog blocks interaction until homing completes. Shows per-pump status:
```
Homing pumps — please wait...
  ✓ Pump 1 homed
  ⟳ Pump 2 homing...
  · Pump 3 waiting
```
"Home All Pumps" button re-triggers this dialog at any time.

### Settings dialog
Editable fields for all `config.py` mechanical specs. Changes apply immediately and are written back to `config.py` on save.

---

## Error Handling

| Condition | Behavior |
|-----------|----------|
| Forward limit hit during purge | Stop motor, show EMPTY badge, alert user |
| Aft limit not hit during homing | Timeout error, show ERROR badge |
| Purge amount > current volume | Input validation error before starting |
| Serial connection lost (Arduino) | Show ERROR badge, disable Run button |
| Tic not found by serial number | Show ERROR at startup with instructions |

---

## Dependencies

- `PyQt5`
- `pyserial` (Arduino backend only)
- `ticlib` or `ticcmd` CLI (Tic T825 backend only)
- `RPi.GPIO` (Arduino backend limit switches only)

---

## Out of Scope

- Rotating valve control (separate spec after this GUI is complete)
- Data logging / run history
- Network/remote control

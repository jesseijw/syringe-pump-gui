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

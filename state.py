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

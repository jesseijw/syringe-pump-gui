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

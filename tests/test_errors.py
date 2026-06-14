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

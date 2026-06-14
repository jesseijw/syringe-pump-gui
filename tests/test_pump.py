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


def test_limit_worker_emits_signal_on_forward_limit(qapp, mock_ctrl):
    from pump import LimitSwitchWorker
    from PyQt5.QtCore import Qt
    mock_ctrl.read_limit.side_effect = [False, False, True]
    received = []
    worker = LimitSwitchWorker(pump_id=1, controller=mock_ctrl, poll_interval_sec=0.001)
    worker.limit_hit.connect(lambda pid: received.append(pid), Qt.DirectConnection)
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

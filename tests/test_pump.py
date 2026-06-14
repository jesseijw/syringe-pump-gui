import pytest
from unittest.mock import MagicMock, patch
from state import PumpState
from errors import HomingTimeoutError, HomingTravelExceededError, ValidationError
import config


@pytest.fixture
def mock_ctrl():
    ctrl = MagicMock()
    ctrl.read_limit.return_value = False
    return ctrl


@pytest.fixture
def pump(mock_ctrl):
    from pump import Pump
    return Pump(pump_id=1, controller=mock_ctrl)


def _settings_side_effect(k):
    return {
        "MAX_FLOW_RATE_ML_SEC": 5.0,
        "MIN_FLOW_RATE_ML_SEC": 0.01,
        "PUMP_POSITIONS": {"1": 0, "2": 0, "3": 0},
        "SYRINGE_INNER_DIAMETER_MM": 15.9,
        "LEAD_SCREW_PITCH_MM": 8.0,
        "MICROSTEPPING": 16,
    }.get(k, None)


def test_initial_state_is_startup(pump):
    assert pump.state == PumpState.STARTUP


def test_homing_sets_position_zero(pump, mock_ctrl):
    mock_ctrl.read_limit.side_effect = [False, False, True]
    with patch("settings.get", side_effect=_settings_side_effect):
        pump.home()
    assert pump.position_steps == 0


def test_homing_transitions_to_idle(pump, mock_ctrl):
    mock_ctrl.read_limit.return_value = True
    with patch("settings.get", side_effect=_settings_side_effect):
        pump.home()
    assert pump.state == PumpState.IDLE


def test_homing_calls_energize_then_deenergize(pump, mock_ctrl):
    mock_ctrl.read_limit.return_value = True
    with patch("settings.get", side_effect=_settings_side_effect):
        pump.home()
    mock_ctrl.energize.assert_called_once_with(1)
    mock_ctrl.deenergize.assert_called_once_with(1)


def test_homing_timeout_transitions_to_error(pump, mock_ctrl):
    mock_ctrl.read_limit.return_value = False
    with patch("pump.POLL_INTERVAL_SEC", 0.001), \
         patch("config.HOMING_TIMEOUT_SEC", 0.005), \
         patch("settings.get", side_effect=_settings_side_effect):
        with pytest.raises(HomingTimeoutError):
            pump.home()
    assert pump.state == PumpState.ERROR
    mock_ctrl.deenergize.assert_called_once_with(1)


def test_dispense_increments_position(pump, mock_ctrl):
    pump._state = PumpState.IDLE
    pump._position_steps = 0

    with patch("units.ml_to_steps", return_value=100), \
         patch("units.flow_rate_to_steps_per_sec", return_value=50.0), \
         patch("settings.save"), patch("settings.get", side_effect=_settings_side_effect):
        pump.dispense(volume_ml=1.0, flow_rate_ml_sec=0.5)
    assert pump.position_steps == 100


def test_dispense_validates_volume_exceeds_remaining(pump, mock_ctrl):
    pump._state = PumpState.IDLE
    pump._position_steps = 0
    with patch("settings.get", side_effect=_settings_side_effect), \
         patch("units.ml_to_steps", return_value=0):
        with pytest.raises(ValidationError):
            pump.dispense(volume_ml=20.0, flow_rate_ml_sec=1.0)


def test_dispense_validates_flow_rate_too_high(pump, mock_ctrl):
    pump._state = PumpState.IDLE
    with patch("settings.get", side_effect=_settings_side_effect):
        with pytest.raises(ValidationError):
            pump.dispense(volume_ml=1.0, flow_rate_ml_sec=999.0)


def steps_to_ml(steps):
    import math
    diameter = 15.9
    pitch = 8.0
    ustep = 16
    cross_section = math.pi * (diameter / 2) ** 2
    mm_per_ml = 1000.0 / cross_section
    steps_per_mm = (200 * ustep) / pitch
    spm = steps_per_mm * mm_per_ml
    return 0.0 if spm == 0 else steps / spm


def test_current_volume_derived_from_position(pump):
    steps = 1000
    pump._position_steps = steps
    with patch("units.steps_to_ml", return_value=5.0):
        assert pump.current_volume_ml == pytest.approx(config.FULL_VOLUME_ML - 5.0)


def test_stop_from_running_transitions_to_idle(pump, mock_ctrl):
    pump._state = PumpState.RUNNING
    pump.stop()
    assert pump.state == PumpState.IDLE
    mock_ctrl.stop.assert_called_once_with(1)


def test_stop_is_noop_when_not_running(pump, mock_ctrl):
    # pump starts in STARTUP state
    pump.stop()
    mock_ctrl.stop.assert_not_called()
    mock_ctrl.deenergize.assert_not_called()


def test_mark_empty_transitions_to_empty(pump, mock_ctrl):
    pump._state = PumpState.RUNNING
    pump.mark_empty()
    assert pump.state == PumpState.EMPTY


def test_dispense_deenergizes_on_move_failure(pump, mock_ctrl):
    mock_ctrl.move.side_effect = RuntimeError("hardware fault")
    pump._state = PumpState.IDLE
    with patch("settings.get", side_effect=_settings_side_effect), \
         patch("settings.save"):
        with pytest.raises(RuntimeError):
            pump.dispense(volume_ml=1.0, flow_rate_ml_sec=0.5)
    mock_ctrl.deenergize.assert_called_once_with(pump.pump_id)
    assert pump.state == PumpState.ERROR


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

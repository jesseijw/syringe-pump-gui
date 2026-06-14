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


def test_tic_detect_returns_found_ids():
    import importlib, controller
    importlib.reload(controller)
    with patch("controller.ticlib") as mock_ticlib:
        mock_ticlib.TicUSB.return_value = MagicMock()
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

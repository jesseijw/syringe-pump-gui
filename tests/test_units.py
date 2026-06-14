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
    import units
    assert 1900 < units.ml_to_steps(1.0) < 2200

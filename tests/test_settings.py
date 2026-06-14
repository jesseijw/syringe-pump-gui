import json
import pytest
import settings


@pytest.fixture(autouse=True)
def clean_settings(tmp_path, monkeypatch):
    fake_path = tmp_path / "settings.json"
    monkeypatch.setattr(settings, "_SETTINGS_PATH", fake_path)
    settings._runtime.clear()
    yield fake_path
    settings._runtime.clear()


def test_defaults_loaded_without_settings_file():
    import config
    assert settings.get("MICROSTEPPING") == config.MICROSTEPPING


def test_settings_json_overrides_default(clean_settings):
    clean_settings.write_text(json.dumps({"MICROSTEPPING": 32}))
    settings._runtime.clear()
    assert settings.get("MICROSTEPPING") == 32


def test_save_writes_to_json(clean_settings):
    settings.save({"LEAD_SCREW_PITCH_MM": 4.0})
    data = json.loads(clean_settings.read_text())
    assert data["LEAD_SCREW_PITCH_MM"] == 4.0


def test_unknown_keys_ignored_on_save(clean_settings):
    import config
    settings.save({"NOT_A_REAL_KEY": 999})
    assert settings.get("MICROSTEPPING") == config.MICROSTEPPING


def test_save_then_reload_round_trips(clean_settings):
    settings.save({"MICROSTEPPING": 8})
    settings._runtime.clear()
    assert settings.get("MICROSTEPPING") == 8


def test_pump_positions_persisted(clean_settings):
    settings.save({"PUMP_POSITIONS": {"1": 500, "2": 0, "3": 0}})
    settings._runtime.clear()
    assert settings.get("PUMP_POSITIONS")["1"] == 500

import json
import pathlib
import config as _defaults

_SETTINGS_PATH = pathlib.Path(__file__).parent / "settings.json"

_OVERRIDABLE_KEYS = {
    "MICROSTEPPING", "LEAD_SCREW_PITCH_MM", "SYRINGE_INNER_DIAMETER_MM",
    "MAX_FLOW_RATE_ML_SEC", "MIN_FLOW_RATE_ML_SEC", "PUMP_POSITIONS",
}

_runtime: dict = {}


def _load() -> None:
    global _runtime
    base = {k: getattr(_defaults, k) for k in _OVERRIDABLE_KEYS}
    if _SETTINGS_PATH.exists():
        with open(_SETTINGS_PATH) as f:
            overrides = json.load(f)
        base.update({k: v for k, v in overrides.items() if k in _OVERRIDABLE_KEYS})
    _runtime = base


def get(key: str):
    if not _runtime:
        _load()
    return _runtime[key]


def save(updates: dict) -> None:
    _load()
    _runtime.update({k: v for k, v in updates.items() if k in _OVERRIDABLE_KEYS})
    with open(_SETTINGS_PATH, "w") as f:
        json.dump({k: _runtime[k] for k in _OVERRIDABLE_KEYS}, f, indent=2)
    _load()

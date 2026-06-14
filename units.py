import math
import settings


def _steps_per_ml() -> float:
    diameter = settings.get("SYRINGE_INNER_DIAMETER_MM")
    pitch    = settings.get("LEAD_SCREW_PITCH_MM")
    ustep    = settings.get("MICROSTEPPING")
    cross_section = math.pi * (diameter / 2) ** 2
    mm_per_ml     = 1000.0 / cross_section
    steps_per_mm  = (200 * ustep) / pitch
    return steps_per_mm * mm_per_ml


def ml_to_steps(ml: float) -> int:
    return round(ml * _steps_per_ml())


def steps_to_ml(steps: int) -> float:
    spm = _steps_per_ml()
    return 0.0 if spm == 0 else steps / spm


def flow_rate_to_steps_per_sec(ml_per_sec: float) -> float:
    return ml_per_sec * _steps_per_ml()

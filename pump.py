import time
import config
import settings
import units
from state import PumpState, validate_transition
from errors import HomingTimeoutError, HomingTravelExceededError, ValidationError

POLL_INTERVAL_SEC = 0.05


class Pump:

    def __init__(self, pump_id: int, controller):
        self.pump_id = pump_id
        self._controller = controller
        self._state = PumpState.STARTUP
        self._position_steps: int = 0

    @property
    def state(self) -> PumpState:
        return self._state

    @property
    def position_steps(self) -> int:
        return self._position_steps

    @property
    def current_volume_ml(self) -> float:
        return config.FULL_VOLUME_ML - units.steps_to_ml(self._position_steps)

    def _transition(self, next_state: PumpState) -> None:
        validate_transition(self._state, next_state)
        self._state = next_state

    def home(self) -> None:
        self._transition(PumpState.HOMING)
        self._controller.energize(self.pump_id)
        try:
            self._controller.home(self.pump_id)
            deadline = time.monotonic() + config.HOMING_TIMEOUT_SEC
            max_steps = int(
                config.MAX_HOMING_TRAVEL_MM
                * (200 * config.MICROSTEPPING) / config.LEAD_SCREW_PITCH_MM
            )
            steps_moved = 0
            step_increment = int(
                config.HOMING_SPEED_MM_PER_SEC * POLL_INTERVAL_SEC
                * (200 * config.MICROSTEPPING) / config.LEAD_SCREW_PITCH_MM
            )
            while not self._controller.read_limit(self.pump_id, "aft"):
                if time.monotonic() > deadline:
                    self._controller.stop(self.pump_id)
                    raise HomingTimeoutError(
                        f"Pump {self.pump_id} did not reach aft limit within "
                        f"{config.HOMING_TIMEOUT_SEC}s"
                    )
                if steps_moved > max_steps:
                    self._controller.stop(self.pump_id)
                    raise HomingTravelExceededError(
                        f"Pump {self.pump_id} exceeded max homing travel of "
                        f"{config.MAX_HOMING_TRAVEL_MM}mm"
                    )
                time.sleep(POLL_INTERVAL_SEC)
                steps_moved += step_increment
        except (HomingTimeoutError, HomingTravelExceededError):
            self._state = PumpState.ERROR
            self._controller.deenergize(self.pump_id)
            raise
        self._controller.stop(self.pump_id)
        self._position_steps = 0
        self._controller.deenergize(self.pump_id)
        self._transition(PumpState.IDLE)

    def dispense(self, volume_ml: float, flow_rate_ml_sec: float) -> None:
        max_flow = config.MAX_FLOW_RATE_ML_SEC
        min_flow = config.MIN_FLOW_RATE_ML_SEC
        if not (min_flow <= flow_rate_ml_sec <= max_flow):
            raise ValidationError(
                f"Flow rate {flow_rate_ml_sec} mL/s out of range [{min_flow}, {max_flow}]"
            )
        if volume_ml > self.current_volume_ml:
            raise ValidationError(
                f"Purge {volume_ml} mL exceeds current volume {self.current_volume_ml:.2f} mL"
            )
        steps = units.ml_to_steps(volume_ml)
        speed = units.flow_rate_to_steps_per_sec(flow_rate_ml_sec)
        self._transition(PumpState.RUNNING)
        self._controller.energize(self.pump_id)
        self._controller.move(self.pump_id, steps, speed)
        self._position_steps += steps
        try:
            positions = settings.get("PUMP_POSITIONS")
            if isinstance(positions, dict):
                positions[str(self.pump_id)] = self._position_steps
                settings.save({"PUMP_POSITIONS": positions})
        except (KeyError, TypeError):
            pass
        self._controller.deenergize(self.pump_id)
        self._transition(PumpState.STOPPING)
        self._transition(PumpState.IDLE)

    def stop(self) -> None:
        if self._state == PumpState.RUNNING:
            self._controller.stop(self.pump_id)
            self._controller.deenergize(self.pump_id)
            self._transition(PumpState.STOPPING)
            self._transition(PumpState.IDLE)

    def mark_empty(self) -> None:
        self._controller.stop(self.pump_id)
        self._controller.deenergize(self.pump_id)
        self._state = PumpState.STOPPING
        self._transition(PumpState.EMPTY)


from PyQt5.QtCore import QThread, pyqtSignal


class LimitSwitchWorker(QThread):
    limit_hit = pyqtSignal(int)   # emits pump_id

    def __init__(self, pump_id: int, controller, poll_interval_sec: float = POLL_INTERVAL_SEC):
        super().__init__()
        self._pump_id = pump_id
        self._controller = controller
        self._interval = poll_interval_sec
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        while not self._cancelled:
            if self._controller.read_limit(self._pump_id, "forward"):
                self.limit_hit.emit(self._pump_id)
                return
            time.sleep(self._interval)

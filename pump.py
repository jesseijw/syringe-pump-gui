import time
import threading
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
        self._lock = threading.Lock()

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
        with self._lock:
            self._transition(PumpState.HOMING)
        self._controller.energize(self.pump_id)
        try:
            self._controller.home(self.pump_id)
            start = time.monotonic()
            deadline = start + config.HOMING_TIMEOUT_SEC
            max_steps = int(
                config.MAX_HOMING_TRAVEL_MM
                * (config.STEPS_PER_REV * settings.get("MICROSTEPPING"))
                / settings.get("LEAD_SCREW_PITCH_MM")
            )
            move_start = time.monotonic()
            while not self._controller.read_limit(self.pump_id, "aft"):
                now = time.monotonic()
                if now > deadline:
                    self._controller.stop(self.pump_id)
                    raise HomingTimeoutError(
                        f"Pump {self.pump_id} did not reach aft limit within "
                        f"{config.HOMING_TIMEOUT_SEC}s"
                    )
                elapsed_sec = now - move_start
                steps_moved = int(
                    elapsed_sec
                    * config.HOMING_SPEED_MM_PER_SEC
                    / settings.get("LEAD_SCREW_PITCH_MM")
                    * config.STEPS_PER_REV
                    * settings.get("MICROSTEPPING")
                )
                if steps_moved > max_steps:
                    self._controller.stop(self.pump_id)
                    raise HomingTravelExceededError(
                        f"Pump {self.pump_id} exceeded max homing travel of "
                        f"{config.MAX_HOMING_TRAVEL_MM}mm"
                    )
                time.sleep(POLL_INTERVAL_SEC)
        except (HomingTimeoutError, HomingTravelExceededError):
            self._controller.deenergize(self.pump_id)
            with self._lock:
                self._transition(PumpState.ERROR)
            raise
        self._controller.stop(self.pump_id)
        self._controller.deenergize(self.pump_id)
        with self._lock:
            self._position_steps = 0
            self._transition(PumpState.IDLE)

    def dispense(self, volume_ml: float, flow_rate_ml_sec: float) -> None:
        max_flow = settings.get("MAX_FLOW_RATE_ML_SEC")
        min_flow = settings.get("MIN_FLOW_RATE_ML_SEC")
        if not (min_flow <= flow_rate_ml_sec <= max_flow):
            raise ValidationError(
                f"Flow rate {flow_rate_ml_sec} mL/s out of range [{min_flow}, {max_flow}]"
            )
        if volume_ml > self.current_volume_ml:
            raise ValidationError(
                f"Dispense {volume_ml} mL exceeds current volume {self.current_volume_ml:.2f} mL"
            )
        steps = units.ml_to_steps(volume_ml)
        speed = units.flow_rate_to_steps_per_sec(flow_rate_ml_sec)
        with self._lock:
            self._transition(PumpState.RUNNING)
        self._controller.energize(self.pump_id)
        try:
            self._controller.move(self.pump_id, steps, speed)
        except Exception:
            self._controller.deenergize(self.pump_id)
            with self._lock:
                self._transition(PumpState.ERROR)
            raise
        with self._lock:
            self._position_steps += steps
        try:
            positions = settings.get("PUMP_POSITIONS") or {}
            if isinstance(positions, dict):
                positions[str(self.pump_id)] = self._position_steps
                settings.save({"PUMP_POSITIONS": positions})
        except Exception:
            pass  # position persistence failure is non-fatal; motor already done
        self._controller.deenergize(self.pump_id)
        with self._lock:
            self._transition(PumpState.STOPPING)
            self._transition(PumpState.IDLE)

    def stop(self) -> None:
        with self._lock:
            if self._state != PumpState.RUNNING:
                return
        self._controller.stop(self.pump_id)
        self._controller.deenergize(self.pump_id)
        with self._lock:
            self._transition(PumpState.STOPPING)
            self._transition(PumpState.IDLE)

    def mark_empty(self) -> None:
        with self._lock:
            if self._state != PumpState.RUNNING:
                return
        self._controller.stop(self.pump_id)
        self._controller.deenergize(self.pump_id)
        with self._lock:
            self._transition(PumpState.STOPPING)
            self._transition(PumpState.EMPTY)

    def resume(self, position_steps: int) -> None:
        """Restore a known position without homing. Transitions STARTUP → IDLE."""
        with self._lock:
            self._position_steps = position_steps
            self._transition(PumpState.IDLE)


from PyQt5.QtCore import QThread, pyqtSignal


class LimitSwitchWorker(QThread):
    limit_hit = pyqtSignal(int)   # emits pump_id

    def __init__(self, pump_id: int, controller, poll_interval_sec: float = POLL_INTERVAL_SEC):
        super().__init__()
        self._pump_id = pump_id
        self._controller = controller
        self._interval = poll_interval_sec
        self._stop_event = threading.Event()

    def cancel(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.is_set():
            if self._controller.read_limit(self._pump_id, "forward"):
                self.limit_hit.emit(self._pump_id)
                return
            time.sleep(self._interval)


class DispenseWorker(QThread):
    finished = pyqtSignal(int)               # pump_id
    error    = pyqtSignal(int, str, bool)    # pump_id, error message, is_validation_error

    def __init__(self, pump: "Pump", volume_ml: float, flow_rate_ml_sec: float):
        super().__init__()
        self._pump = pump
        self._volume_ml = volume_ml
        self._flow_rate_ml_sec = flow_rate_ml_sec

    def cancel(self) -> None:
        # Dispense cannot be interrupted mid-flight; this is a no-op.
        # The caller should call stop() on the Pump directly to halt motion.
        pass

    def run(self):
        try:
            self._pump.dispense(self._volume_ml, self._flow_rate_ml_sec)
            self.finished.emit(self._pump.pump_id)
        except ValidationError as exc:
            self.error.emit(self._pump.pump_id, str(exc), True)
        except Exception as exc:
            self.error.emit(self._pump.pump_id, str(exc), False)


class HomingWorker(QThread):
    finished = pyqtSignal(int)          # pump_id
    error    = pyqtSignal(int, str)     # pump_id, error message

    def __init__(self, pump: "Pump"):
        super().__init__()
        self._pump = pump

    def cancel(self) -> None:
        # Dispense cannot be interrupted mid-flight; this is a no-op.
        # The caller should call stop() on the Pump directly to halt motion.
        pass

    def run(self):
        try:
            self._pump.home()
            self.finished.emit(self._pump.pump_id)
        except Exception as exc:
            self.error.emit(self._pump.pump_id, str(exc))

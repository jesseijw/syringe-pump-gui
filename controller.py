from abc import ABC, abstractmethod
from typing import List


class PumpController(ABC):

    @abstractmethod
    def detect(self) -> List[int]:
        """Return list of pump IDs found on the bus."""

    @abstractmethod
    def energize(self, pump_id: int) -> None:
        """Enable motor coils."""

    @abstractmethod
    def deenergize(self, pump_id: int) -> None:
        """Release motor coils to prevent overheating when idle."""

    @abstractmethod
    def home(self, pump_id: int) -> None:
        """Begin slow aft movement. Caller polls read_limit('aft') for completion."""

    @abstractmethod
    def move(self, pump_id: int, steps: int, steps_per_sec: float) -> None:
        """Move `steps` at `steps_per_sec`. Blocks until motion completes."""

    @abstractmethod
    def stop(self, pump_id: int) -> None:
        """Immediately halt motion."""

    @abstractmethod
    def read_limit(self, pump_id: int, side: str) -> bool:
        """Return True if named switch is active. side: 'aft' | 'forward'"""


try:
    import ticlib
except ImportError:
    ticlib = None   # not available on dev machines

import config as _cfg
import time as _time


class TicController(PumpController):

    def __init__(self):
        self._tics: dict = {}

    def detect(self) -> List[int]:
        if ticlib is None:
            raise ImportError("ticlib not installed. Run: pip install ticlib")
        found = []
        for pump_id, serial_num in _cfg.TIC_SERIAL_NUMBERS.items():
            try:
                tic = ticlib.TicUSB(serial_number=str(serial_num))
                self._tics[pump_id] = tic
                found.append(pump_id)
            except Exception:
                pass
        return found

    def _tic(self, pump_id: int):
        if pump_id not in self._tics:
            from errors import ControllerNotFoundError
            raise ControllerNotFoundError(f"Pump {pump_id} not detected")
        return self._tics[pump_id]

    def energize(self, pump_id: int) -> None:
        self._tic(pump_id).energize()

    def deenergize(self, pump_id: int) -> None:
        self._tic(pump_id).deenergize()

    def home(self, pump_id: int) -> None:
        tic = self._tic(pump_id)
        steps_per_sec = int(
            _cfg.HOMING_SPEED_MM_PER_SEC
            * (200 * _cfg.MICROSTEPPING) / _cfg.LEAD_SCREW_PITCH_MM
        )
        tic.set_target_velocity(-steps_per_sec)

    def move(self, pump_id: int, steps: int, steps_per_sec: float) -> None:
        tic = self._tic(pump_id)
        tic.reset_command_timeout()
        # Set speed limit before commanding position
        try:
            tic.set_speed_limit(int(steps_per_sec))
        except AttributeError:
            pass  # ticlib version may use a different API; speed set via Tic Control Center
        current = tic.get_variables().current_position
        target = current + steps
        tic.set_target_position(target)
        # Poll until motion completes
        import time
        timeout = abs(steps / steps_per_sec) * 3 + 10
        deadline = time.monotonic() + timeout
        while True:
            tic.reset_command_timeout()
            if tic.get_variables().current_position == target:
                break
            if time.monotonic() > deadline:
                tic.halt_and_hold()
                raise RuntimeError(f"Pump {pump_id} motion timeout")
            time.sleep(0.1)

    def stop(self, pump_id: int) -> None:
        self._tic(pump_id).halt_and_hold()

    def read_limit(self, pump_id: int, side: str) -> bool:
        variables = self._tic(pump_id).get_variables()
        if side == "forward":
            return bool(variables.forward_limit_active)
        if side == "aft":
            return bool(variables.reverse_limit_active)
        raise ValueError(f"Unknown side: {side!r}. Use 'aft' or 'forward'.")


try:
    import serial
except ImportError:
    serial = None


class ArduinoController(PumpController):

    def __init__(self):
        self._ser = None

    def _send(self, cmd: str) -> str:
        if self._ser is None:
            from errors import SerialConnectionError
            raise SerialConnectionError("Not connected. Call detect() first.")
        self._ser.write(cmd.encode())
        return self._ser.readline().decode().strip()

    def detect(self) -> List[int]:
        if serial is None:
            raise ImportError("pyserial not installed. Run: pip install pyserial")
        try:
            self._ser = serial.Serial(_cfg.SERIAL_PORT, _cfg.SERIAL_BAUD, timeout=2)
            return [1, 2, 3]
        except Exception as exc:
            from errors import ControllerNotFoundError
            raise ControllerNotFoundError(
                f"Cannot open {_cfg.SERIAL_PORT}: {exc}"
            ) from exc

    def energize(self, pump_id: int) -> None:
        self._send(f"ENERGIZE:{pump_id}\n")

    def deenergize(self, pump_id: int) -> None:
        self._send(f"DEENERGIZE:{pump_id}\n")

    def home(self, pump_id: int) -> None:
        self._send(f"HOME:{pump_id}\n")

    def move(self, pump_id: int, steps: int, steps_per_sec: float) -> None:
        self._send(f"MOVE:{pump_id}:{steps}:{steps_per_sec:.2f}\n")
        # Poll until motion completes
        import time
        timeout = abs(steps / steps_per_sec) * 3 + 10  # 3× expected duration + 10s buffer
        deadline = time.monotonic() + timeout
        while True:
            remaining = int(self._send(f"DISTANCETOGO:{pump_id}\n").strip())
            if remaining == 0:
                break
            if time.monotonic() > deadline:
                self.stop(pump_id)
                raise RuntimeError(f"Pump {pump_id} motion timeout after {timeout:.0f}s")
            time.sleep(0.1)

    def stop(self, pump_id: int) -> None:
        self._ser.write(f"STOP:{pump_id}\n".encode())

    def read_limit(self, pump_id: int, side: str) -> bool:
        return self._send(f"LIMIT:{pump_id}:{side}\n") == "1"

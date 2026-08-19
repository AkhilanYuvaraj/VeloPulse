"""
VeloPulseAI — Tier 1 Hardware Telemetry Manager.

Supports three operating modes for ingesting real-time 2 Hz vehicle
telemetry streams:

  1. SERIAL       — ESP32 / Arduino over USB COM (pyserial)
  2. BLUETOOTH_OBD — ELM327 Bluetooth adapter (python-obd)
  3. SIMULATION    — Benchtop emulator with live fault injection

The ``HardwareManager`` class coordinates background polling at 2 Hz,
stores frames in a thread-safe circular buffer, and exposes a unified
interface for the FastAPI server to query live telemetry and trigger
fault injection during demonstrations.
"""

import json
import time
import logging
import threading
import random
import math
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Union

try:
    import serial
except ImportError:
    serial = None

try:
    import obd
except ImportError:
    obd = None


logger = logging.getLogger("velopulse.tier1_hardware")


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class FaultType(Enum):
    """Fault types available for injection in simulation mode."""

    VOLTAGE_DROP = "voltage_drop"
    THERMAL_RUNAWAY = "thermal_runaway"
    BEARING_VIBRATION = "bearing_vibration"
    ENGINE_MISFIRE = "engine_misfire"
    COMBINED = "combined"


class HardwareMode(Enum):
    SERIAL = "SERIAL"
    BLUETOOTH_OBD = "BLUETOOTH_OBD"
    SIMULATION = "SIMULATION"
    WOKWI = "WOKWI"


@dataclass
class ConnectionStatus:
    mode: HardwareMode
    connected: bool
    port_or_address: str
    last_reading_timestamp: Optional[str]
    frames_received: int
    errors_count: int
    uptime_seconds: float
    _start_time: float = field(default_factory=time.time, repr=False)

    def update_uptime(self):
        self.uptime_seconds = time.time() - self._start_time


class TelemetrySource(ABC):
    """Abstract base class for all hardware telemetry sources."""

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def read_frame(self) -> Optional[Dict[str, Any]]:
        """Returns the canonical telemetry dictionary or None if read fails."""
        pass

    @abstractmethod
    def get_status(self) -> ConnectionStatus:
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        pass


class SerialTelemetrySource(TelemetrySource):
    """Serial/USB mode source for ESP32/Arduino telemetry."""
    
    def __init__(self, port: str = "COM3", baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn: Optional['serial.Serial'] = None
        self._connected = False
        self._frames_received = 0
        self._errors_count = 0
        self._last_reading_time = None
        self._status = ConnectionStatus(
            mode=HardwareMode.SERIAL,
            connected=False,
            port_or_address=self.port,
            last_reading_timestamp=None,
            frames_received=0,
            errors_count=0,
            uptime_seconds=0.0
        )

    def connect(self) -> bool:
        if serial is None:
            logger.error("pyserial is not installed. Cannot use Serial Mode.")
            return False
            
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1.0)
            self._connected = True
            self._status._start_time = time.time()
            logger.info(f"Connected to Serial port {self.port} at {self.baudrate} baud.")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Serial port {self.port}: {e}")
            self._errors_count += 1
            return False

    def disconnect(self) -> None:
        self._connected = False
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        logger.info("Disconnected from Serial port.")

    def read_frame(self) -> Optional[Dict[str, Any]]:
        if not self._connected or not self.serial_conn:
            return None

        try:
            line = self.serial_conn.readline().decode('utf-8').strip()
            if not line:
                return None
                
            raw_data = json.loads(line)
            
            # Map raw data to canonical format (assuming raw matches closely)
            frame = {
                "engine_temp_c": float(raw_data.get("engine_temp_c", 0.0)),
                "engine_rpm": float(raw_data.get("engine_rpm", 0.0)),
                "coolant_temp_c": float(raw_data.get("coolant_temp_c", 0.0)),
                "battery_voltage_v": float(raw_data.get("battery_voltage_v", 0.0)),
                "vibration_level": float(raw_data.get("vibration_level", 0.0)),
                "odometer_reading": float(raw_data.get("odometer_reading", 0.0)),
                "engine_load": float(raw_data.get("engine_load", 0.0)),
                "vehicle_speed": float(raw_data.get("vehicle_speed", 0.0)),
                "timestamp": datetime.now().isoformat()
            }
            
            self._frames_received += 1
            self._last_reading_time = frame["timestamp"]
            return frame
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Corrupt frame received on serial: {e}")
            self._errors_count += 1
            return None
        except Exception as e:
            logger.error(f"Serial read error: {e}")
            self._errors_count += 1
            self.disconnect()  # Disconnect on hard error
            return None

    def get_status(self) -> ConnectionStatus:
        self._status.connected = self._connected
        self._status.frames_received = self._frames_received
        self._status.errors_count = self._errors_count
        self._status.last_reading_timestamp = self._last_reading_time
        self._status.update_uptime()
        return self._status

    @property
    def is_connected(self) -> bool:
        return self._connected


class BluetoothOBDSource(TelemetrySource):
    """Bluetooth ELM327 OBD-II mode source for live vehicle telemetry."""
    
    def __init__(self, port: str = "COM4"):
        self.port = port
        self.obd_conn = None
        self._connected = False
        self._frames_received = 0
        self._errors_count = 0
        self._last_reading_time = None
        self._status = ConnectionStatus(
            mode=HardwareMode.BLUETOOTH_OBD,
            connected=False,
            port_or_address=self.port,
            last_reading_timestamp=None,
            frames_received=0,
            errors_count=0,
            uptime_seconds=0.0
        )
        self._odometer_sim = 50000.0  # OBD doesn't always support odometer

    def connect(self) -> bool:
        if obd is None:
            logger.error("obd library is not installed. Cannot use OBD-II mode.")
            return False
            
        try:
            logger.info(f"Attempting OBD-II connection on {self.port} (ISO 15765-4 optimized)...")
            # Connect via python-obd. 
            self.obd_conn = obd.OBD(self.port, fast=True)
            if self.obd_conn.is_connected():
                self._connected = True
                self._status._start_time = time.time()
                logger.info("Successfully connected to OBD-II adapter.")
                return True
            else:
                logger.error("Failed to connect to OBD-II adapter.")
                return False
        except Exception as e:
            logger.error(f"OBD connection error: {e}")
            self._errors_count += 1
            return False

    def disconnect(self) -> None:
        self._connected = False
        if self.obd_conn:
            self.obd_conn.close()
        logger.info("Disconnected from OBD-II.")

    def _query_safe(self, command) -> float:
        if not self.obd_conn:
            return 0.0
        resp = self.obd_conn.query(command)
        if not resp.is_null():
            return float(resp.value.magnitude)
        return 0.0

    def read_frame(self) -> Optional[Dict[str, Any]]:
        if not self._connected or not self.obd_conn:
            return None

        try:
            # Standard OBD-II PIDs
            rpm = self._query_safe(obd.commands.RPM)
            coolant = self._query_safe(obd.commands.COOLANT_TEMP)
            voltage = self._query_safe(obd.commands.CONTROL_MODULE_VOLTAGE)
            load = self._query_safe(obd.commands.ENGINE_LOAD)
            speed = self._query_safe(obd.commands.SPEED)
            
            # Synthetic updates for unsupported standard PIDs
            self._odometer_sim += (speed * (0.5 / 3600.0)) # Add km based on speed and 2Hz dt

            frame = {
                "engine_temp_c": coolant,
                "engine_rpm": rpm,
                "coolant_temp_c": coolant,
                "battery_voltage_v": voltage if voltage > 0 else 12.5,
                "vibration_level": 0.5 + (rpm / 5000.0) + random.uniform(0, 0.1),
                "odometer_reading": self._odometer_sim,
                "engine_load": load,
                "vehicle_speed": speed,
                "timestamp": datetime.now().isoformat()
            }
            
            self._frames_received += 1
            self._last_reading_time = frame["timestamp"]
            return frame
        except Exception as e:
            logger.error(f"Error reading OBD-II frame: {e}")
            self._errors_count += 1
            return None

    def get_status(self) -> ConnectionStatus:
        self._status.connected = self._connected
        self._status.frames_received = self._frames_received
        self._status.errors_count = self._errors_count
        self._status.last_reading_timestamp = self._last_reading_time
        self._status.update_uptime()
        return self._status

    @property
    def is_connected(self) -> bool:
        return self._connected


class SimulationTelemetrySource(TelemetrySource):
    """Benchtop hardware emulator generating realistic automotive telemetry."""
    
    def __init__(self):
        self._connected = False
        self._frames_received = 0
        self._errors_count = 0
        self._last_reading_time = None
        self._status = ConnectionStatus(
            mode=HardwareMode.SIMULATION,
            connected=False,
            port_or_address="simulated",
            last_reading_timestamp=None,
            frames_received=0,
            errors_count=0,
            uptime_seconds=0.0
        )
        
        # Base Engine State
        self.state = {
            "rpm": 1200.0,
            "coolant_temp": 88.0,
            "voltage": 13.8,
            "vibration": 0.2,
            "odometer": 120500.0,
            "load": 25.0,
            "speed": 60.0
        }
        
        # Active faults dictionary: type -> {'severity': float, 'end_time': float}
        self.active_faults = {}
        self._last_update = time.time()

    def connect(self) -> bool:
        self._connected = True
        self._status._start_time = time.time()
        self._last_update = time.time()
        logger.info("Simulation Telemetry Source started.")
        return True

    def disconnect(self) -> None:
        self._connected = False
        logger.info("Simulation Telemetry Source stopped.")

    def inject_fault(self, fault_type: str, severity: float, duration_seconds: float):
        """Injects a specific fault into the running simulation."""
        logger.warning(f"Injecting Fault: {fault_type}, Severity: {severity}, Duration: {duration_seconds}s")
        if fault_type == "combined":
            self.active_faults["voltage_drop"] = {"severity": severity, "end_time": time.time() + duration_seconds}
            self.active_faults["thermal_runaway"] = {"severity": severity, "end_time": time.time() + duration_seconds}
            self.active_faults["bearing_vibration"] = {"severity": severity, "end_time": time.time() + duration_seconds}
            self.active_faults["engine_misfire"] = {"severity": severity, "end_time": time.time() + duration_seconds}
        else:
            self.active_faults[fault_type] = {"severity": severity, "end_time": time.time() + duration_seconds}

    def _update_physics(self, dt: float) -> None:
        """
        Advance the physics simulation by ``dt`` seconds.

        Uses exponential smoothing (alpha = 1 - e^{-rate*dt}) which is
        unconditionally stable regardless of the time-step size.  All
        sensor values are hard-clamped to physically plausible ranges.
        """
        current_time = time.time()

        # Cap dt to prevent numerical blowup on the first frame
        dt = min(dt, 1.0)

        # Clean expired faults
        expired = [f for f, data in self.active_faults.items()
                   if data["end_time"] < current_time]
        for f in expired:
            logger.info("Fault %s expired, beginning recovery.", f)
            del self.active_faults[f]

        # --- Base realistic drift (normal driving behaviour) ---------------
        self.state["speed"] += random.uniform(-1, 1) * dt
        self.state["speed"] = max(0.0, min(self.state["speed"], 120.0))

        target_rpm = 800.0 + (self.state["speed"] * 25.0)
        alpha_rpm = 1.0 - math.exp(-2.0 * dt)
        self.state["rpm"] += (target_rpm - self.state["rpm"]) * alpha_rpm
        self.state["rpm"] += random.uniform(-15, 15)

        target_load = 20.0 + (self.state["speed"] / 4.0)
        alpha_load = 1.0 - math.exp(-0.5 * dt)
        self.state["load"] += (target_load - self.state["load"]) * alpha_load
        self.state["load"] += random.uniform(-1.5, 1.5)

        # --- Fault-dependent targets ---------------------------------------
        target_temp = 90.0
        target_voltage = 13.8 + random.uniform(-0.05, 0.05)
        target_vibration = 0.5 + (self.state["rpm"] / 8000.0) + random.uniform(-0.03, 0.03)

        if "voltage_drop" in self.active_faults:
            sev = self.active_faults["voltage_drop"]["severity"]
            target_voltage = 13.8 - (4.3 * sev)  # ~9.5 V at max severity

        if "thermal_runaway" in self.active_faults:
            sev = self.active_faults["thermal_runaway"]["severity"]
            target_temp = 90.0 + (50.0 * sev)  # ~140 °C at max severity

        if "bearing_vibration" in self.active_faults:
            sev = self.active_faults["bearing_vibration"]["severity"]
            target_vibration += 6.0 * sev  # spike to ~6.5 g

        if "engine_misfire" in self.active_faults:
            sev = self.active_faults["engine_misfire"]["severity"]
            self.state["rpm"] += random.uniform(-500, 500) * sev
            self.state["load"] += random.uniform(-15, 15) * sev

        # --- Exponential smoothing toward targets --------------------------
        alpha_temp = 1.0 - math.exp(-0.15 * dt)
        alpha_volt = 1.0 - math.exp(-3.0 * dt)
        alpha_vib = 1.0 - math.exp(-5.0 * dt)

        self.state["coolant_temp"] += (target_temp - self.state["coolant_temp"]) * alpha_temp
        self.state["voltage"] += (target_voltage - self.state["voltage"]) * alpha_volt
        self.state["vibration"] += (target_vibration - self.state["vibration"]) * alpha_vib

        # --- Odometry ------------------------------------------------------
        self.state["odometer"] += self.state["speed"] * (dt / 3600.0)

        # --- Hard clamps to physically realistic bounds --------------------
        self.state["rpm"] = max(500.0, min(self.state["rpm"], 7000.0))
        self.state["coolant_temp"] = max(15.0, min(self.state["coolant_temp"], 160.0))
        self.state["voltage"] = max(8.0, min(self.state["voltage"], 15.5))
        self.state["vibration"] = max(0.0, min(self.state["vibration"], 12.0))
        self.state["load"] = max(5.0, min(self.state["load"], 100.0))
        self.state["speed"] = max(0.0, min(self.state["speed"], 180.0))

    def read_frame(self) -> Optional[Dict[str, Any]]:
        if not self._connected:
            return None
            
        current_time = time.time()
        dt = current_time - self._last_update
        self._last_update = current_time
        
        self._update_physics(dt)
        
        frame = {
            "engine_temp_c": round(self.state["coolant_temp"] + random.uniform(-1, 1), 2),
            "engine_rpm": round(self.state["rpm"], 1),
            "coolant_temp_c": round(self.state["coolant_temp"], 2),
            "battery_voltage_v": round(self.state["voltage"], 2),
            "vibration_level": round(self.state["vibration"], 3),
            "odometer_reading": round(self.state["odometer"], 2),
            "engine_load": round(self.state["load"], 1),
            "vehicle_speed": round(self.state["speed"], 1),
            "timestamp": datetime.now().isoformat()
        }
        
        self._frames_received += 1
        self._last_reading_time = frame["timestamp"]
        return frame

    def get_status(self) -> ConnectionStatus:
        self._status.connected = self._connected
        self._status.frames_received = self._frames_received
        self._status.errors_count = self._errors_count
        self._status.last_reading_timestamp = self._last_reading_time
        self._status.update_uptime()
        return self._status

    @property
    def is_connected(self) -> bool:
        return self._connected


class WokwiTelemetrySource(TelemetrySource):
    """
    Reads JSON telemetry from an ESP32 running on Wokwi simulator.

    Connects via pyserial (supports RFC2217 serial-over-TCP for the
    Wokwi IoT Gateway, or direct COM port via Wokwi CLI).

    The ESP32 sketch outputs one JSON line per reading at 2 Hz with
    all canonical VeloPulseAI ML features:
        engine_temp_c, engine_rpm, coolant_temp_c, battery_voltage_v,
        vibration_level, odometer_reading, engine_load, vehicle_speed
    Plus raw MPU6050 diagnostics in a nested ``mpu6050_raw`` object.
    """

    def __init__(self, port: str = "rfc2217://localhost:4000", baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self._connected = False
        self._frames_received = 0
        self._errors_count = 0
        self._last_reading_time = None
        self._status = ConnectionStatus(
            mode=HardwareMode.WOKWI,
            connected=False,
            port_or_address=self.port,
            last_reading_timestamp=None,
            frames_received=0,
            errors_count=0,
            uptime_seconds=0.0,
        )

    def connect(self) -> bool:
        if serial is None:
            logger.error("pyserial is not installed. Cannot use Wokwi mode.")
            return False

        try:
            self.serial_conn = serial.serial_for_url(
                self.port,
                baudrate=self.baudrate,
                timeout=2.0,
            )
            self._connected = True
            self._status._start_time = time.time()
            logger.info("Connected to Wokwi ESP32 at %s", self.port)
            return True
        except Exception as e:
            logger.error("Failed to connect to Wokwi ESP32 at %s: %s", self.port, e)
            self._errors_count += 1
            return False

    def disconnect(self) -> None:
        self._connected = False
        if self.serial_conn:
            try:
                self.serial_conn.close()
            except Exception:
                pass
        logger.info("Disconnected from Wokwi ESP32.")

    def read_frame(self) -> Optional[Dict[str, Any]]:
        if not self._connected or not self.serial_conn:
            return None

        try:
            line = self.serial_conn.readline().decode("utf-8", errors="replace").strip()
            if not line:
                return None

            raw_data = json.loads(line)

            # Check for ESP32 error messages
            if "error" in raw_data:
                logger.error("ESP32 reported error: %s", raw_data["error"])
                self._errors_count += 1
                return None

            # The ESP32 sketch already outputs canonical field names,
            # so we can use them directly.
            frame = {
                "engine_temp_c": float(raw_data.get("engine_temp_c", 0.0)),
                "engine_rpm": float(raw_data.get("engine_rpm", 0.0)),
                "coolant_temp_c": float(raw_data.get("coolant_temp_c", 0.0)),
                "battery_voltage_v": float(raw_data.get("battery_voltage_v", 0.0)),
                "vibration_level": float(raw_data.get("vibration_level", 0.0)),
                "odometer_reading": float(raw_data.get("odometer_reading", 0.0)),
                "engine_load": float(raw_data.get("engine_load", 0.0)),
                "vehicle_speed": float(raw_data.get("vehicle_speed", 0.0)),
                "timestamp": datetime.now().isoformat(),
            }

            # Attach raw MPU6050 data if present (for diagnostics)
            mpu_raw = raw_data.get("mpu6050_raw")
            if mpu_raw:
                frame["mpu6050_raw"] = mpu_raw

            self._frames_received += 1
            self._last_reading_time = frame["timestamp"]
            return frame

        except json.JSONDecodeError:
            # Skip non-JSON lines (ESP32 boot messages, etc.)
            return None
        except Exception as e:
            logger.error("Wokwi serial read error: %s", e)
            self._errors_count += 1
            return None

    def get_status(self) -> ConnectionStatus:
        self._status.connected = self._connected
        self._status.frames_received = self._frames_received
        self._status.errors_count = self._errors_count
        self._status.last_reading_timestamp = self._last_reading_time
        self._status.update_uptime()
        return self._status

    @property
    def is_connected(self) -> bool:
        return self._connected


class HardwareManager:
    """
    Manages the active Tier 1 telemetry source, background 2 Hz polling,
    and thread-safe circular frame storage.

    Provides a unified interface for mode switching, live frame retrieval,
    and fault injection during demo / hackathon presentations.
    """

    def __init__(
        self,
        mode: HardwareMode = HardwareMode.SIMULATION,
        port_or_address: str = "COM3",
        baudrate: int = 115200,
    ) -> None:
        self.mode = mode
        self.port_or_address = port_or_address
        self.baudrate = baudrate
        self._source: Optional[TelemetrySource] = None

        self._buffer: deque = deque(maxlen=1000)
        self._lock = threading.Lock()

        self._polling_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Mode management
    # ------------------------------------------------------------------
    def set_mode(
        self,
        mode: HardwareMode,
        port: Optional[str] = None,
        baudrate: Optional[int] = None,
    ) -> None:
        """
        Configure the target hardware mode before calling ``start()``.

        Parameters
        ----------
        mode : HardwareMode
            Target mode (SERIAL, BLUETOOTH_OBD, SIMULATION).
        port : str, optional
            COM port or Bluetooth address. Defaults to current value.
        baudrate : int, optional
            Baud rate for serial connections. Defaults to current value.
        """
        self.mode = mode
        if port is not None:
            self.port_or_address = port
        if baudrate is not None:
            self.baudrate = baudrate
        self._setup_source()
        logger.info(
            "Hardware mode set to %s (port=%s, baudrate=%d)",
            mode.value,
            self.port_or_address,
            self.baudrate,
        )

    def _setup_source(self) -> None:
        """Instantiate the appropriate telemetry source for the current mode."""
        if self.mode == HardwareMode.SERIAL:
            self._source = SerialTelemetrySource(
                port=self.port_or_address, baudrate=self.baudrate
            )
        elif self.mode == HardwareMode.BLUETOOTH_OBD:
            self._source = BluetoothOBDSource(port=self.port_or_address)
        elif self.mode == HardwareMode.SIMULATION:
            self._source = SimulationTelemetrySource()
        elif self.mode == HardwareMode.WOKWI:
            self._source = WokwiTelemetrySource(
                port=self.port_or_address, baudrate=self.baudrate
            )
        else:
            raise ValueError(f"Unsupported Hardware Mode: {self.mode}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Connect to the hardware source and start the 2 Hz polling thread."""
        if self._source is None:
            self._setup_source()

        with self._lock:
            if not self._source.connect():
                logger.error("Failed to start hardware source.")
                return

            self._stop_event.clear()
            self._polling_thread = threading.Thread(
                target=self._polling_loop,
                daemon=True,
                name="HardwarePollThread",
            )
            self._polling_thread.start()
            logger.info("Hardware Manager polling thread started (2 Hz).")

    def stop(self) -> None:
        """Stop the polling thread and disconnect the hardware source."""
        self._stop_event.set()
        if self._polling_thread is not None:
            self._polling_thread.join(timeout=2.0)
            self._polling_thread = None

        with self._lock:
            if self._source is not None:
                self._source.disconnect()
            logger.info("Hardware Manager stopped.")

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------
    def _polling_loop(self) -> None:
        """Background thread: read one frame every 0.5 s (2 Hz)."""
        poll_interval = 0.5  # 2 Hz

        while not self._stop_event.is_set():
            loop_start = time.time()

            with self._lock:
                if self._source is not None and self._source.is_connected:
                    frame = self._source.read_frame()
                    if frame is not None:
                        self._buffer.append(frame)

            # Sleep remainder of the 0.5 s cycle
            elapsed = time.time() - loop_start
            sleep_time = max(0.0, poll_interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)

    # ------------------------------------------------------------------
    # Frame access
    # ------------------------------------------------------------------
    def get_latest_frame(self) -> Optional[Dict[str, Any]]:
        """Return the most recent telemetry frame (thread-safe)."""
        with self._lock:
            if self._buffer:
                return self._buffer[-1]
            return None

    def get_history(self, count: int = 100) -> List[Dict[str, Any]]:
        """Return up to ``count`` recent frames from the circular buffer."""
        with self._lock:
            return list(self._buffer)[-count:]

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def get_status(self) -> ConnectionStatus:
        """
        Return current connection status of the active source.

        Returns a default disconnected status if no source is configured.
        """
        with self._lock:
            if self._source is not None:
                return self._source.get_status()
            return ConnectionStatus(
                mode=self.mode,
                connected=False,
                port_or_address=self.port_or_address,
                last_reading_timestamp=None,
                frames_received=0,
                errors_count=0,
                uptime_seconds=0.0,
            )

    # ------------------------------------------------------------------
    # Fault injection
    # ------------------------------------------------------------------
    def inject_fault(
        self,
        fault_type: Union[FaultType, str],
        severity: float = 0.8,
        duration_seconds: float = 15.0,
    ) -> None:
        """
        Inject a hardware fault into the simulation source.

        Parameters
        ----------
        fault_type : FaultType or str
            Type of fault to inject.
        severity : float
            Fault severity from 0.0 (mild) to 1.0 (extreme).
        duration_seconds : float
            Duration of the fault in seconds.

        Raises
        ------
        RuntimeError
            If not in SIMULATION mode.
        """
        fault_str = fault_type.value if isinstance(fault_type, FaultType) else str(fault_type)

        with self._lock:
            if self.mode != HardwareMode.SIMULATION:
                raise RuntimeError(
                    f"Fault injection only available in SIMULATION mode "
                    f"(current: {self.mode.value})"
                )
            if isinstance(self._source, SimulationTelemetrySource):
                self._source.inject_fault(fault_str, severity, duration_seconds)
            else:
                raise RuntimeError("Simulation source is not initialised.")

    # ------------------------------------------------------------------
    # Legacy alias
    # ------------------------------------------------------------------
    def switch_mode(
        self, new_mode: HardwareMode, port_or_address: str = "COM3"
    ) -> None:
        """Legacy wrapper — stops, reconfigures, and restarts."""
        logger.info(
            "Switching Hardware Mode to %s on %s",
            new_mode.value,
            port_or_address,
        )
        self.stop()
        self.set_mode(mode=new_mode, port=port_or_address)
        self.start()


# ---------------------------------------------------------------------------
# CLI Demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-28s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    print("=== VeloPulseAI Tier 1 Hardware Manager Demo ===")
    print("Mode: SIMULATION  |  Poll rate: 2 Hz\n")

    hw = HardwareManager()
    hw.set_mode(HardwareMode.SIMULATION)
    hw.start()

    try:
        # --- Normal operation (2 s) ----------------------------------------
        print("--- Normal Operation ---")
        for _ in range(4):
            time.sleep(0.5)
            frame = hw.get_latest_frame()
            if frame:
                print(
                    f"  RPM: {frame['engine_rpm']:>7.1f}  |  "
                    f"Coolant: {frame['coolant_temp_c']:>6.1f} C  |  "
                    f"Voltage: {frame['battery_voltage_v']:>5.2f} V  |  "
                    f"Vibration: {frame['vibration_level']:.3f} g"
                )

        # --- Thermal runaway fault (3 s) -----------------------------------
        print("\n--- Injecting THERMAL_RUNAWAY (severity=0.8, 5 s) ---")
        hw.inject_fault(FaultType.THERMAL_RUNAWAY, severity=0.8, duration_seconds=5.0)
        for _ in range(6):
            time.sleep(0.5)
            frame = hw.get_latest_frame()
            if frame:
                print(
                    f"  RPM: {frame['engine_rpm']:>7.1f}  |  "
                    f"Coolant: {frame['coolant_temp_c']:>6.1f} C  |  "
                    f"Voltage: {frame['battery_voltage_v']:>5.2f} V  |  "
                    f"Vibration: {frame['vibration_level']:.3f} g"
                )

        # --- Recovery (2 s) ------------------------------------------------
        print("\n--- Recovery Period ---")
        for _ in range(4):
            time.sleep(0.5)
            frame = hw.get_latest_frame()
            if frame:
                print(
                    f"  RPM: {frame['engine_rpm']:>7.1f}  |  "
                    f"Coolant: {frame['coolant_temp_c']:>6.1f} C  |  "
                    f"Voltage: {frame['battery_voltage_v']:>5.2f} V  |  "
                    f"Vibration: {frame['vibration_level']:.3f} g"
                )

        # --- Combined fault (3 s) ------------------------------------------
        print("\n--- Injecting COMBINED faults (severity=0.9, 3 s) ---")
        hw.inject_fault(FaultType.COMBINED, severity=0.9, duration_seconds=3.0)
        for _ in range(6):
            time.sleep(0.5)
            frame = hw.get_latest_frame()
            if frame:
                print(
                    f"  RPM: {frame['engine_rpm']:>7.1f}  |  "
                    f"Coolant: {frame['coolant_temp_c']:>6.1f} C  |  "
                    f"Voltage: {frame['battery_voltage_v']:>5.2f} V  |  "
                    f"Vibration: {frame['vibration_level']:.3f} g  |  "
                    f"Load: {frame['engine_load']:.1f}%"
                )

        # --- Status check --------------------------------------------------
        print("\n--- Hardware Status ---")
        status = hw.get_status()
        print(f"  Mode:     {status.mode.value}")
        print(f"  Connected: {status.connected}")
        print(f"  Frames:   {status.frames_received}")
        print(f"  Errors:   {status.errors_count}")
        print(f"  Uptime:   {status.uptime_seconds:.1f} s")

    finally:
        hw.stop()
        print("\n=== Demo Complete ===")

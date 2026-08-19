"""
VeloPulseAI — Wokwi ESP32 Data Reader & Predictor.

Reads JSON telemetry from the ESP32 running on Wokwi simulator
(via virtual serial port) and feeds it through the VeloPulseAI
ML prediction pipeline.

Connection Methods:
    1. RFC2217 (Wokwi IoT Gateway):  rfc2217://localhost:4000
    2. Direct COM port:               COM3, COM4, etc.
    3. Wokwi CLI serial:              Pipe mode

Usage:
    # Connect to Wokwi IoT Gateway (default)
    python injector.py

    # Connect to a specific serial port
    python injector.py --port COM5

    # Use custom baud rate
    python injector.py --port COM5 --baud 115200

    # Also send predictions to FastAPI server
    python injector.py --api http://localhost:8000

    # Dry-run with simulated data (no hardware needed)
    python injector.py --simulate
"""

import argparse
import json
import math
import random
import sys
import time
from datetime import datetime
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Optional dependencies with graceful fallback
# ---------------------------------------------------------------------------
try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ---------------------------------------------------------------------------
# ANSI colors for terminal output
# ---------------------------------------------------------------------------
class C:
    RESET      = "\033[0m"
    BOLD       = "\033[1m"
    DIM        = "\033[2m"
    CYAN       = "\033[96m"
    GREEN      = "\033[92m"
    YELLOW     = "\033[93m"
    RED        = "\033[91m"
    MAGENTA    = "\033[95m"
    BLUE       = "\033[94m"
    WHITE      = "\033[97m"
    GREY       = "\033[90m"
    BG_RED     = "\033[41m"
    BG_GREEN   = "\033[42m"
    BG_YELLOW  = "\033[43m"


# ---------------------------------------------------------------------------
# Connection to Wokwi ESP32
# ---------------------------------------------------------------------------
class WokwiSerialReader:
    """
    Reads JSON-line telemetry from the ESP32 Wokwi serial output.

    Supports RFC2217 (serial-over-TCP) and direct COM ports via pyserial.
    """

    def __init__(self, port: str = "rfc2217://localhost:4000", baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.conn: Optional[Any] = None

    def connect(self) -> bool:
        if not HAS_SERIAL:
            print(f"  {C.RED}ERROR: pyserial not installed.{C.RESET}")
            print(f"  {C.YELLOW}Run: pip install pyserial{C.RESET}")
            return False

        try:
            self.conn = serial.serial_for_url(
                self.port,
                baudrate=self.baudrate,
                timeout=2.0,
            )
            print(f"  {C.GREEN}✓{C.RESET} Connected to {C.CYAN}{self.port}{C.RESET}")
            return True
        except Exception as e:
            print(f"  {C.RED}✗ Connection failed:{C.RESET} {e}")
            return False

    def read_frame(self) -> Optional[Dict[str, Any]]:
        """Read one JSON line from serial. Returns parsed dict or None."""
        if self.conn is None:
            return None

        try:
            line = self.conn.readline().decode("utf-8", errors="replace").strip()
            if not line:
                return None

            data = json.loads(line)

            # Check for ESP32 error messages
            if "error" in data:
                print(f"  {C.RED}ESP32 Error: {data['error']}{C.RESET}")
                return None

            return data

        except json.JSONDecodeError:
            # Skip non-JSON lines (e.g., boot messages)
            return None
        except Exception as e:
            print(f"  {C.RED}Read error: {e}{C.RESET}")
            return None

    def disconnect(self):
        if self.conn and self.conn.is_open:
            self.conn.close()
        print(f"  {C.GREY}Disconnected from serial.{C.RESET}")


# ---------------------------------------------------------------------------
# Simulated data source (no hardware needed)
# ---------------------------------------------------------------------------
class SimulatedReader:
    """Generates fake ESP32 MPU6050 JSON data for testing without hardware."""

    def __init__(self):
        self.state = {
            "rpm": 1200.0,
            "coolant": 88.0,
            "voltage": 13.8,
            "vibration": 0.3,
            "load": 25.0,
            "speed": 60.0,
            "odometer": 50000.0,
        }

    def connect(self) -> bool:
        print(f"  {C.YELLOW}⚡ Simulation mode{C.RESET} — generating synthetic ESP32 data")
        return True

    def read_frame(self) -> Optional[Dict[str, Any]]:
        time.sleep(0.5)  # 2 Hz

        s = self.state
        s["speed"] += random.uniform(-1, 1)
        s["speed"] = max(0, min(120, s["speed"]))
        target_rpm = 800 + s["speed"] * 25
        s["rpm"] += (target_rpm - s["rpm"]) * 0.3 + random.uniform(-15, 15)
        s["rpm"] = max(600, min(6500, s["rpm"]))
        s["coolant"] += random.uniform(-0.2, 0.2)
        s["coolant"] = max(15, min(150, s["coolant"]))
        s["voltage"] = 13.8 + random.uniform(-0.1, 0.1)
        s["vibration"] = 0.3 + abs(random.gauss(0, 0.2))
        s["load"] = 20 + s["speed"] / 4 + random.uniform(-1.5, 1.5)
        s["load"] = max(5, min(100, s["load"]))
        s["odometer"] += s["speed"] * (0.5 / 3600)

        return {
            "engine_temp_c": round(s["coolant"] + random.uniform(-1, 1), 2),
            "engine_rpm": round(s["rpm"], 1),
            "coolant_temp_c": round(s["coolant"], 2),
            "battery_voltage_v": round(s["voltage"], 2),
            "vibration_level": round(s["vibration"], 3),
            "odometer_reading": round(s["odometer"], 2),
            "engine_load": round(s["load"], 1),
            "vehicle_speed": round(s["speed"], 1),
            "mpu6050_raw": {
                "accel_x": round(random.uniform(-0.5, 0.5), 2),
                "accel_y": round(random.uniform(-0.5, 0.5), 2),
                "accel_z": round(9.81 + random.uniform(-0.3, 0.3), 2),
                "gyro_x": round(random.uniform(-0.05, 0.05), 2),
                "gyro_y": round(random.uniform(-0.05, 0.05), 2),
                "gyro_z": round(random.uniform(-0.05, 0.05), 2),
                "temp_c": round(25 + random.uniform(-2, 2), 1),
                "total_accel": round(9.81 + random.uniform(-0.3, 0.3), 2),
                "shock": False,
            },
        }

    def disconnect(self):
        print(f"  {C.GREY}Simulation stopped.{C.RESET}")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
def color_value(val: float, low: float, high: float, invert: bool = False) -> str:
    """Color a value green/yellow/red based on thresholds."""
    if invert:
        if val < low:    return f"{C.GREEN}{val}{C.RESET}"
        elif val < high: return f"{C.YELLOW}{val}{C.RESET}"
        else:            return f"{C.RED}{val}{C.RESET}"
    else:
        if val > high:   return f"{C.GREEN}{val}{C.RESET}"
        elif val > low:  return f"{C.YELLOW}{val}{C.RESET}"
        else:            return f"{C.RED}{val}{C.RESET}"


def display_frame(frame: Dict[str, Any], frame_num: int):
    """Print a formatted telemetry frame to console."""
    ts = datetime.now().strftime("%H:%M:%S.%f")[:12]

    rpm   = frame.get("engine_rpm", 0)
    temp  = frame.get("coolant_temp_c", 0)
    volt  = frame.get("battery_voltage_v", 0)
    vib   = frame.get("vibration_level", 0)
    speed = frame.get("vehicle_speed", 0)
    load  = frame.get("engine_load", 0)

    # Color thresholds
    rpm_c  = f"{C.GREEN}" if rpm < 4000 else (f"{C.YELLOW}" if rpm < 5500 else f"{C.RED}")
    temp_c = f"{C.GREEN}" if temp < 100 else (f"{C.YELLOW}" if temp < 120 else f"{C.RED}")
    volt_c = f"{C.GREEN}" if volt > 12.0 else (f"{C.YELLOW}" if volt > 10.5 else f"{C.RED}")
    vib_c  = f"{C.GREEN}" if vib < 2.0  else (f"{C.YELLOW}" if vib < 4.0  else f"{C.RED}")

    # Raw MPU6050 data if available
    raw = frame.get("mpu6050_raw", {})
    shock = raw.get("shock", False)
    shock_str = f" {C.BG_RED}{C.WHITE} SHOCK {C.RESET}" if shock else ""

    print(
        f"  {C.GREY}[{ts}] #{frame_num:04d}{C.RESET}  "
        f"{C.GREY}RPM{C.RESET} {rpm_c}{rpm:>7.0f}{C.RESET}  "
        f"{C.GREY}│{C.RESET}  "
        f"{C.GREY}Temp{C.RESET} {temp_c}{temp:>6.1f}°C{C.RESET}  "
        f"{C.GREY}│{C.RESET}  "
        f"{C.GREY}Batt{C.RESET} {volt_c}{volt:>5.2f}V{C.RESET}  "
        f"{C.GREY}│{C.RESET}  "
        f"{C.GREY}Vib{C.RESET} {vib_c}{vib:>5.3f}g{C.RESET}  "
        f"{C.GREY}│{C.RESET}  "
        f"{C.GREY}Speed{C.RESET} {C.WHITE}{speed:>5.1f}{C.RESET}km/h  "
        f"{C.GREY}│{C.RESET}  "
        f"{C.GREY}Load{C.RESET} {C.WHITE}{load:>5.1f}%{C.RESET}"
        f"{shock_str}"
    )


def display_prediction(result: Dict[str, Any]):
    """Print ML prediction result."""
    health = result.get("health_status", "UNKNOWN")
    rul    = result.get("predicted_rul_km", 0)
    anomaly = result.get("anomaly_detected", False)
    score  = result.get("anomaly_score", 0)
    rca    = result.get("root_cause_analysis", {})
    t_ms   = result.get("inference_time_ms", 0)

    hc = C.GREEN if health == "HEALTHY" else (C.YELLOW if health == "ADVISORY" else C.RED)
    ac = C.RED if anomaly else C.GREEN
    rc = C.RED if rul < 500 else (C.YELLOW if rul < 5000 else C.GREEN)

    print()
    print(f"  {C.CYAN}{C.BOLD}┌─── ML PREDICTION ──────────────────────────────────────────┐{C.RESET}")
    print(f"  {C.CYAN}│{C.RESET}  Health:  {hc}{C.BOLD}{health}{C.RESET}    "
          f"Anomaly: {ac}{'⚠ YES' if anomaly else '✓ No'}{C.RESET} "
          f"{C.GREY}(score: {score:.4f}){C.RESET}    "
          f"RUL: {rc}{rul:,.0f} km{C.RESET}    "
          f"{C.GREY}{t_ms:.1f}ms{C.RESET}")

    # Top 3 root causes
    if rca:
        top3 = list(rca.items())[:3]
        causes = "  ".join(
            f"{C.GREY}{name.replace('_',' ').title()}: "
            f"{C.RED if val > 0 else C.GREEN}{val:+.1f}%{C.RESET}"
            for name, val in top3
        )
        print(f"  {C.CYAN}│{C.RESET}  Risk:   {causes}")

    print(f"  {C.CYAN}└────────────────────────────────────────────────────────────┘{C.RESET}")
    print()


# ---------------------------------------------------------------------------
# API client (optional — sends to FastAPI server)
# ---------------------------------------------------------------------------
def send_to_api(api_url: str, frame: Dict[str, Any]) -> Optional[Dict]:
    """POST telemetry frame to VeloPulseAI API and return prediction."""
    if not HAS_REQUESTS:
        return None

    try:
        # Strip mpu6050_raw before sending (API doesn't need it)
        payload = {k: v for k, v in frame.items() if k != "mpu6050_raw"}
        payload["vehicle_id"] = "WOKWI-ESP32-001"

        resp = requests.post(
            f"{api_url}/api/v1/predict",
            json=payload,
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"  {C.YELLOW}API {resp.status_code}: {resp.text[:100]}{C.RESET}")
            return None
    except Exception as e:
        print(f"  {C.RED}API error: {e}{C.RESET}")
        return None


# ---------------------------------------------------------------------------
# Local ML prediction (no server needed)
# ---------------------------------------------------------------------------
_ml_engine = None

def predict_local(frame: Dict[str, Any]) -> Optional[Dict]:
    """Run prediction locally using VeloPulseAI ML engine."""
    global _ml_engine

    if _ml_engine is None:
        try:
            from ml_engine import MLEngine
            _ml_engine = MLEngine()
            _ml_engine.load_models()
            print(f"  {C.GREEN}✓{C.RESET} ML models loaded for local prediction")
        except Exception as e:
            print(f"  {C.YELLOW}Local ML not available: {e}{C.RESET}")
            _ml_engine = False  # Mark as failed, don't retry
            return None

    if _ml_engine is False:
        return None

    try:
        # Strip raw MPU data before prediction
        clean = {k: v for k, v in frame.items() if k != "mpu6050_raw"}
        t0 = time.perf_counter()
        result = _ml_engine.predict(clean, vehicle_id="WOKWI-ESP32-001")
        t_ms = (time.perf_counter() - t0) * 1000

        return {
            "vehicle_id": result.vehicle_id,
            "anomaly_detected": result.anomaly_detected,
            "anomaly_score": result.anomaly_score,
            "health_status": result.health_status,
            "predicted_rul_km": result.predicted_rul_km,
            "root_cause_analysis": result.root_cause_analysis,
            "inference_time_ms": round(t_ms, 2),
        }
    except Exception as e:
        print(f"  {C.RED}Prediction error: {e}{C.RESET}")
        return None


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="VeloPulseAI — Read ESP32 MPU6050 data from Wokwi and predict.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python injector.py                              # Wokwi IoT Gateway default
  python injector.py --port COM5                  # Direct serial port
  python injector.py --simulate                   # No hardware, test mode
  python injector.py --api http://localhost:8000   # Send to FastAPI server
        """,
    )
    parser.add_argument(
        "--port", default="rfc2217://localhost:4000",
        help="Serial port or RFC2217 URL (default: rfc2217://localhost:4000)",
    )
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate")
    parser.add_argument("--simulate", action="store_true", help="Use simulated data (no hardware)")
    parser.add_argument("--api", default=None, help="FastAPI server URL (e.g., http://localhost:8000)")
    parser.add_argument("--predict-every", type=int, default=2, help="Run ML prediction every N frames (default: 2)")
    parser.add_argument("--max-frames", type=int, default=0, help="Stop after N frames (0 = infinite)")
    args = parser.parse_args()

    # Banner
    print()
    print(f"  {C.CYAN}{C.BOLD}╔════════════════════════════════════════════════════════════╗{C.RESET}")
    print(f"  {C.CYAN}{C.BOLD}║     VeloPulseAI — Wokwi ESP32 MPU6050 Data Reader        ║{C.RESET}")
    print(f"  {C.CYAN}{C.BOLD}╚════════════════════════════════════════════════════════════╝{C.RESET}")
    print()

    # Create reader
    if args.simulate:
        reader = SimulatedReader()
    else:
        reader = WokwiSerialReader(port=args.port, baudrate=args.baud)

    # Connect
    if not reader.connect():
        print(f"\n  {C.RED}Failed to connect. Exiting.{C.RESET}")
        sys.exit(1)

    print(f"  {C.GREY}Prediction mode: ", end="")
    if args.api:
        print(f"API → {args.api}{C.RESET}")
    else:
        print(f"Local ML engine{C.RESET}")
    print(f"  {C.GREY}Predict every {args.predict_every} frames  |  "
          f"Press Ctrl+C to stop{C.RESET}")
    print()
    print(f"  {C.GREY}{'─' * 110}{C.RESET}")

    frame_count = 0

    try:
        while True:
            frame = reader.read_frame()
            if frame is None:
                continue

            frame_count += 1
            display_frame(frame, frame_count)

            # Run prediction periodically
            if frame_count % args.predict_every == 0:
                if args.api:
                    result = send_to_api(args.api, frame)
                else:
                    result = predict_local(frame)

                if result:
                    display_prediction(result)

            # Max frames check
            if 0 < args.max_frames <= frame_count:
                print(f"\n  {C.GREY}Reached {args.max_frames} frames. Stopping.{C.RESET}")
                break

    except KeyboardInterrupt:
        print(f"\n\n  {C.YELLOW}Interrupted by user.{C.RESET}")

    finally:
        reader.disconnect()
        print(f"  {C.GREY}Total frames received: {frame_count}{C.RESET}")
        print()


if __name__ == "__main__":
    main()
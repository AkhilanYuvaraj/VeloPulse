"""
VeloPulseAI — Wokwi ESP32 Data Reader & Predictor (HTTP Mode).

Fetches JSON telemetry from the ESP32 running on Wokwi simulator
over the virtual WiFi network (HTTP GET to http://10.13.37.2/data).

Usage:
    # Connect to Wokwi ESP32 IP
    python injector.py

    # Use custom IP
    python injector.py --ip http://10.13.37.2

    # Also send predictions to FastAPI server
    python injector.py --api http://localhost:8000

    # Dry-run with simulated data (no hardware needed)
    python injector.py --simulate
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime
from typing import Any, Dict, Optional

# Force UTF-8 output on Windows
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
    CYAN       = "\033[96m"
    GREEN      = "\033[92m"
    YELLOW     = "\033[93m"
    RED        = "\033[91m"
    WHITE      = "\033[97m"
    GREY       = "\033[90m"
    BG_RED     = "\033[41m"


# ---------------------------------------------------------------------------
# Connection to Wokwi ESP32 via HTTP
# ---------------------------------------------------------------------------
class WokwiHttpReader:
    """Fetches JSON telemetry from ESP32 Wokwi Web Server."""

    def __init__(self, ip: str = "http://10.13.37.2"):
        self.url = f"{ip.rstrip('/')}/data"
        self._connected = False

    def connect(self) -> bool:
        if not HAS_REQUESTS:
            print(f"  {C.RED}ERROR: requests library not installed.{C.RESET}")
            return False

        print(f"  {C.CYAN}Connecting to Wokwi ESP32 at {self.url}...{C.RESET}")
        try:
            # Initial ping to check if server is up
            resp = requests.get(self.url, timeout=5.0)
            if resp.status_code == 200:
                print(f"  {C.GREEN}✓{C.RESET} Connected successfully!")
                self._connected = True
                return True
            else:
                print(f"  {C.RED}✗ Connection failed. Status code: {resp.status_code}{C.RESET}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"  {C.RED}✗ Connection failed:{C.RESET} {e}")
            return False

    def read_frame(self) -> Optional[Dict[str, Any]]:
        """Fetch one JSON frame via HTTP."""
        if not self._connected:
            return None

        try:
            resp = requests.get(self.url, timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                
                # Add timestamp if missing
                if "timestamp" not in data:
                    data["timestamp"] = datetime.now().isoformat()
                    
                return data
            return None
        except Exception:
            return None

    def disconnect(self):
        self._connected = False
        print(f"  {C.GREY}Disconnected from Wokwi.{C.RESET}")


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
            "timestamp": datetime.now().isoformat(),
        }

    def disconnect(self):
        print(f"  {C.GREY}Simulation stopped.{C.RESET}")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
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
# API client (optional)
# ---------------------------------------------------------------------------
def send_to_api(api_url: str, frame: Dict[str, Any]) -> Optional[Dict]:
    if not HAS_REQUESTS:
        return None

    try:
        payload = {k: v for k, v in frame.items() if k != "mpu6050_raw"}
        payload["vehicle_id"] = "WOKWI-ESP32-001"

        resp = requests.post(
            f"{api_url}/api/v1/predict",
            json=payload,
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"  {C.RED}API error: {e}{C.RESET}")
        return None


# ---------------------------------------------------------------------------
# Local ML prediction
# ---------------------------------------------------------------------------
_ml_engine = None

def predict_local(frame: Dict[str, Any]) -> Optional[Dict]:
    global _ml_engine

    if _ml_engine is None:
        try:
            from ml_engine import MLEngine
            _ml_engine = MLEngine()
            _ml_engine.load_models()
            print(f"  {C.GREEN}✓{C.RESET} ML models loaded for local prediction")
        except Exception as e:
            print(f"  {C.YELLOW}Local ML not available: {e}{C.RESET}")
            _ml_engine = False
            return None

    if _ml_engine is False:
        return None

    try:
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
    parser = argparse.ArgumentParser(description="VeloPulseAI — Wokwi ESP32 HTTP Data Reader")
    parser.add_argument("--ip", default="http://10.13.37.2", help="Wokwi ESP32 IP address")
    parser.add_argument("--simulate", action="store_true", help="Use simulated data")
    parser.add_argument("--api", default=None, help="FastAPI server URL")
    parser.add_argument("--predict-every", type=int, default=2)
    parser.add_argument("--max-frames", type=int, default=0)
    args = parser.parse_args()

    print()
    print(f"  {C.CYAN}{C.BOLD}╔════════════════════════════════════════════════════════════╗{C.RESET}")
    print(f"  {C.CYAN}{C.BOLD}║     VeloPulseAI — Wokwi ESP32 MPU6050 HTTP Reader          ║{C.RESET}")
    print(f"  {C.CYAN}{C.BOLD}╚════════════════════════════════════════════════════════════╝{C.RESET}")
    print()

    reader = SimulatedReader() if args.simulate else WokwiHttpReader(ip=args.ip)

    if not reader.connect():
        print(f"\n  {C.RED}Failed to connect. Exiting.{C.RESET}")
        sys.exit(1)

    print(f"  {C.GREY}Predict every {args.predict_every} frames  |  Press Ctrl+C to stop{C.RESET}")
    print(f"  {C.GREY}{'─' * 110}{C.RESET}")

    frame_count = 0

    try:
        while True:
            # Poll at 2 Hz
            time.sleep(0.5)
            
            frame = reader.read_frame()
            if frame is None:
                continue

            frame_count += 1
            display_frame(frame, frame_count)

            if frame_count % args.predict_every == 0:
                result = send_to_api(args.api, frame) if args.api else predict_local(frame)
                if result:
                    display_prediction(result)

            if 0 < args.max_frames <= frame_count:
                break

    except KeyboardInterrupt:
        print(f"\n\n  {C.YELLOW}Interrupted by user.{C.RESET}")
    finally:
        reader.disconnect()
        print(f"  {C.GREY}Total frames received: {frame_count}{C.RESET}")
        print()


if __name__ == "__main__":
    main()
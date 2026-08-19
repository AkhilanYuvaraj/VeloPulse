"""
VeloPulseAI — Interactive Terminal Demo & Prototype Showcase.

Runs the full predictive-maintenance pipeline directly in the terminal
without requiring the FastAPI server. Designed for hackathon presentations,
investor demos, and prototype testing.

Usage:
    python demo.py                     # Full interactive demo
    python demo.py --quick             # Quick 30-second summary
    python demo.py --scenario fault    # Run specific fault scenario
    python demo.py --batch             # Batch fleet analysis only

Displays:
  • System boot & model loading
  • Live 2 Hz simulated telemetry with real-time ML inference
  • Anomaly detection, RUL prediction, health status
  • SHAP root-cause breakdown (percentage risk attribution)
  • Fault injection scenarios (thermal runaway, voltage drop, combined)
  • Fleet batch analysis with multi-vehicle summary
  • Final dashboard with aggregate statistics
"""

import argparse
import logging
import math
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

# Force UTF-8 output on Windows to support Unicode box-drawing chars
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd

# Suppress noisy library logs during demo
logging.disable(logging.WARNING)

from data_loader import AutomotiveDataLoader
from ml_engine import MLEngine, PredictionResult
from tier1_hardware import (
    FaultType,
    HardwareManager,
    HardwareMode,
)

# Re-enable only critical logs
logging.disable(logging.NOTSET)
logging.getLogger("velopulse").setLevel(logging.ERROR)
logging.getLogger("xgboost").setLevel(logging.ERROR)
logging.getLogger("shap").setLevel(logging.ERROR)


# ═══════════════════════════════════════════════════════════════════════════
# ANSI Terminal Styling — Zero External Dependencies
# ═══════════════════════════════════════════════════════════════════════════

class Style:
    """ANSI escape code styling constants."""

    # Enable ANSI on Windows
    if os.name == "nt":
        os.system("")  # enables VT100 processing on Windows 10+

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    REVERSE = "\033[7m"
    STRIKETHROUGH = "\033[9m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground colors
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background colors
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"
    BG_DARK = "\033[40m"

    # 256-color
    @staticmethod
    def fg(code: int) -> str:
        return f"\033[38;5;{code}m"

    @staticmethod
    def bg(code: int) -> str:
        return f"\033[48;5;{code}m"

    # RGB color
    @staticmethod
    def rgb(r: int, g: int, b: int) -> str:
        return f"\033[38;2;{r};{g};{b}m"

    @staticmethod
    def bg_rgb(r: int, g: int, b: int) -> str:
        return f"\033[48;2;{r};{g};{b}m"

    CLEAR_LINE = "\033[2K"
    CURSOR_UP = "\033[A"
    HIDE_CURSOR = "\033[?25l"
    SHOW_CURSOR = "\033[?25h"


# ═══════════════════════════════════════════════════════════════════════════
# Theme Colors
# ═══════════════════════════════════════════════════════════════════════════

# Brand palette
C_BRAND = Style.rgb(0, 200, 255)       # Electric cyan
C_BRAND2 = Style.rgb(120, 80, 255)     # Deep violet
C_ACCENT = Style.rgb(255, 165, 0)      # Amber
C_SUCCESS = Style.rgb(0, 230, 118)     # Mint green
C_WARNING = Style.rgb(255, 193, 7)     # Gold
C_DANGER = Style.rgb(255, 61, 87)      # Coral red
C_INFO = Style.rgb(100, 181, 246)      # Sky blue
C_MUTED = Style.rgb(120, 130, 150)     # Slate grey
C_HEADER = Style.rgb(200, 200, 220)    # Light steel
C_VALUE = Style.rgb(255, 255, 255)     # White
C_LABEL = Style.rgb(160, 170, 190)     # Silver


# ═══════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def term_width() -> int:
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


def center(text: str, width: int = 0, fill: str = " ") -> str:
    """Center text accounting for ANSI escape codes."""
    w = width or term_width()
    visible_len = len(text.encode("ascii", "ignore").decode("ascii"))
    # Rough visible length by stripping ANSI
    import re
    visible = re.sub(r"\033\[[^m]*m", "", text)
    pad = max(0, w - len(visible))
    left = pad // 2
    return fill * left + text + fill * (pad - left)


def hr(char: str = "─", color: str = C_MUTED) -> str:
    return f"{color}{char * term_width()}{Style.RESET}"


def hr_double(color: str = C_BRAND) -> str:
    return f"{color}{'═' * term_width()}{Style.RESET}"


def progress_bar(value: float, max_val: float = 100.0, width: int = 30,
                 filled_color: str = C_SUCCESS, empty_color: str = C_MUTED) -> str:
    pct = min(1.0, max(0.0, value / max_val))
    filled = int(width * pct)
    empty = width - filled
    bar = f"{filled_color}{'█' * filled}{empty_color}{'░' * empty}{Style.RESET}"
    return bar


def health_color(status: str) -> str:
    if status == "HEALTHY":
        return C_SUCCESS
    elif status == "ADVISORY":
        return C_WARNING
    elif status == "CRITICAL":
        return C_DANGER
    return C_MUTED


def health_icon(status: str) -> str:
    if status == "HEALTHY":
        return f"{C_SUCCESS}●{Style.RESET}"
    elif status == "ADVISORY":
        return f"{C_WARNING}▲{Style.RESET}"
    elif status == "CRITICAL":
        return f"{C_DANGER}■{Style.RESET}"
    return "○"


def anomaly_badge(detected: bool) -> str:
    if detected:
        return f"{Style.BOLD}{C_DANGER}  ⚠ ANOMALY DETECTED  {Style.RESET}"
    return f"{C_SUCCESS}  ✓ NOMINAL  {Style.RESET}"


def rul_display(rul_km: float) -> str:
    if rul_km < 500:
        color = C_DANGER
        icon = "⚠"
    elif rul_km < 5000:
        color = C_WARNING
        icon = "▲"
    else:
        color = C_SUCCESS
        icon = "●"
    return f"{color}{icon} {rul_km:,.0f} km{Style.RESET}"


def sparkline(values: List[float], width: int = 20) -> str:
    """Generate a mini sparkline chart from values."""
    if not values:
        return ""
    blocks = " ▁▂▃▄▅▆▇█"
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1.0
    # Resample to width
    step = max(1, len(values) // width)
    sampled = values[::step][:width]
    chars = []
    for v in sampled:
        idx = int((v - mn) / rng * (len(blocks) - 1))
        chars.append(blocks[idx])
    return "".join(chars)


def typewriter(text: str, delay: float = 0.02):
    """Print text with typewriter animation."""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def animate_loading(message: str, duration: float = 1.5, steps: int = 20):
    """Show animated loading indicator."""
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    dt = duration / steps
    for i in range(steps):
        frame = frames[i % len(frames)]
        pct = int((i + 1) / steps * 100)
        bar = progress_bar(pct, 100, 25, C_BRAND, C_MUTED)
        sys.stdout.write(
            f"\r  {C_BRAND}{frame}{Style.RESET} {C_LABEL}{message}{Style.RESET}"
            f"  {bar}  {C_MUTED}{pct:>3d}%{Style.RESET}"
        )
        sys.stdout.flush()
        time.sleep(dt)
    sys.stdout.write(
        f"\r  {C_SUCCESS}✓{Style.RESET} {C_LABEL}{message}{Style.RESET}"
        f"  {progress_bar(100, 100, 25, C_SUCCESS, C_MUTED)}  "
        f"{C_SUCCESS}Done{Style.RESET}   \n"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Demo Sections
# ═══════════════════════════════════════════════════════════════════════════

def print_banner():
    """Print the VeloPulseAI ASCII art banner."""
    clear_screen()
    banner = f"""
{C_BRAND}{Style.BOLD}
    ╔═══════════════════════════════════════════════════════════════════╗
    ║                                                                   ║
    ║   ██╗   ██╗███████╗██╗      ██████╗ ██████╗ ██╗   ██╗██╗     ║
    ║   ██║   ██║██╔════╝██║     ██╔═══██╗██╔══██╗██║   ██║██║     ║
    ║   ██║   ██║█████╗  ██║     ██║   ██║██████╔╝██║   ██║██║     ║
    ║   ╚██╗ ██╔╝██╔══╝  ██║     ██║   ██║██╔═══╝ ██║   ██║██║     ║
    ║    ╚████╔╝ ███████╗███████╗╚██████╔╝██║     ╚██████╔╝███████╗║
    ║     ╚═══╝  ╚══════╝╚══════╝ ╚═════╝ ╚═╝      ╚═════╝ ╚══════╝║
    ║                                                                   ║
    ║   {C_ACCENT}██████╗ ██╗   ██╗██╗     ███████╗███████╗ █████╗ ██╗{C_BRAND}       ║
    ║   {C_ACCENT}██╔══██╗██║   ██║██║     ██╔════╝██╔════╝██╔══██╗██║{C_BRAND}       ║
    ║   {C_ACCENT}██████╔╝██║   ██║██║     ███████╗█████╗  ███████║██║{C_BRAND}       ║
    ║   {C_ACCENT}██╔═══╝ ██║   ██║██║     ╚════██║██╔══╝  ██╔══██║██║{C_BRAND}       ║
    ║   {C_ACCENT}██║     ╚██████╔╝███████╗███████║███████╗██║  ██║██║{C_BRAND}       ║
    ║   {C_ACCENT}╚═╝      ╚═════╝ ╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝{C_BRAND}       ║
    ║                                                                   ║
    ╚═══════════════════════════════════════════════════════════════════╝
{Style.RESET}"""
    print(banner)
    print(center(
        f"{C_BRAND2}{Style.BOLD}AI-Powered Predictive Maintenance for Smart Vehicles{Style.RESET}"
    ))
    print(center(
        f"{C_MUTED}v1.0.0  ·  3-Stage ML Pipeline  ·  Real-Time Inference  ·  SHAP Explainability{Style.RESET}"
    ))
    print()
    print(hr_double())
    print()


def boot_sequence(engine: MLEngine, hw: HardwareManager):
    """Simulate a visually impressive system boot sequence."""
    print(f"  {C_HEADER}{Style.BOLD}SYSTEM INITIALIZATION{Style.RESET}")
    print(hr())
    print()

    boot_steps = [
        ("Loading Isolation Forest anomaly detector", "anomaly_iforest.joblib"),
        ("Loading XGBoost RUL regressor", "rul_xgb.joblib"),
        ("Loading feature scaler", "feature_scaler.joblib"),
        ("Initializing SHAP TreeExplainer", "XAI engine"),
        ("Starting Tier 1 hardware simulator", "2 Hz telemetry stream"),
        ("Calibrating physics engine", "Exponential smoothing model"),
    ]

    t_start = time.time()

    for i, (step, detail) in enumerate(boot_steps):
        animate_loading(f"{step}  {C_MUTED}({detail}){Style.RESET}", duration=0.4 + 0.2 * (i == 0))

    # Actually load
    sys.stdout.write(f"\r  {C_BRAND}⠋{Style.RESET} {C_LABEL}Validating pipeline integrity...{Style.RESET}")
    sys.stdout.flush()

    try:
        engine.load_models()
    except Exception as e:
        print(f"\n\n  {C_DANGER}{Style.BOLD}ERROR:{Style.RESET} {C_DANGER}Failed to load models: {e}{Style.RESET}")
        print(f"  {C_WARNING}Run: python train_pipeline.py --csv data/test_vehicle_telemetry.csv{Style.RESET}")
        sys.exit(1)

    hw.set_mode(HardwareMode.SIMULATION)
    hw.start()
    time.sleep(0.3)  # Let simulator generate a frame

    t_elapsed = time.time() - t_start
    sys.stdout.write(
        f"\r  {C_SUCCESS}✓{Style.RESET} {C_LABEL}Pipeline validated{Style.RESET}"
        f"  {progress_bar(100, 100, 25, C_SUCCESS, C_MUTED)}  "
        f"{C_SUCCESS}Ready{Style.RESET}  \n"
    )

    print()
    print(f"  {C_SUCCESS}{Style.BOLD}✓ ALL SYSTEMS ONLINE{Style.RESET}"
          f"  {C_MUTED}(boot time: {t_elapsed:.1f}s){Style.RESET}")
    print()
    print(hr_double())


def display_telemetry_frame(frame: Dict[str, Any], frame_num: int = 0):
    """Display a single telemetry frame with formatting."""
    ts = frame.get("timestamp", datetime.now().isoformat())
    ts_short = ts.split("T")[1][:12] if "T" in ts else ts

    # Determine sensor health coloring
    temp = frame.get("coolant_temp_c", 0)
    temp_color = C_SUCCESS if temp < 100 else (C_WARNING if temp < 120 else C_DANGER)

    volt = frame.get("battery_voltage_v", 0)
    volt_color = C_SUCCESS if volt > 12.0 else (C_WARNING if volt > 10.5 else C_DANGER)

    vib = frame.get("vibration_level", 0)
    vib_color = C_SUCCESS if vib < 2.0 else (C_WARNING if vib < 4.0 else C_DANGER)

    rpm = frame.get("engine_rpm", 0)
    rpm_color = C_SUCCESS if rpm < 4000 else (C_WARNING if rpm < 5500 else C_DANGER)

    print(
        f"  {C_MUTED}[{ts_short}]{Style.RESET}  "
        f"{C_LABEL}RPM{Style.RESET} {rpm_color}{rpm:>7.0f}{Style.RESET}  "
        f"{C_MUTED}│{Style.RESET}  "
        f"{C_LABEL}Temp{Style.RESET} {temp_color}{temp:>6.1f}°C{Style.RESET}  "
        f"{C_MUTED}│{Style.RESET}  "
        f"{C_LABEL}Batt{Style.RESET} {volt_color}{volt:>5.2f}V{Style.RESET}  "
        f"{C_MUTED}│{Style.RESET}  "
        f"{C_LABEL}Vib{Style.RESET} {vib_color}{vib:>5.3f}g{Style.RESET}  "
        f"{C_MUTED}│{Style.RESET}  "
        f"{C_LABEL}Speed{Style.RESET} {C_VALUE}{frame.get('vehicle_speed', 0):>5.1f}{Style.RESET}km/h  "
        f"{C_MUTED}│{Style.RESET}  "
        f"{C_LABEL}Load{Style.RESET} {C_VALUE}{frame.get('engine_load', 0):>5.1f}%{Style.RESET}"
    )


def display_prediction(result: PredictionResult, inference_ms: float = 0.0):
    """Display a formatted prediction result."""
    hc = health_color(result.health_status)

    print()
    print(f"  {C_HEADER}{Style.BOLD}┌─── PREDICTION RESULT ────────────────────────────────────────┐{Style.RESET}")
    print(f"  {C_HEADER}│{Style.RESET}")
    print(
        f"  {C_HEADER}│{Style.RESET}  {C_LABEL}Vehicle ID    :{Style.RESET}  "
        f"{C_VALUE}{Style.BOLD}{result.vehicle_id}{Style.RESET}"
    )
    print(
        f"  {C_HEADER}│{Style.RESET}  {C_LABEL}Health Status :{Style.RESET}  "
        f"{hc}{Style.BOLD}{result.health_status}{Style.RESET}  "
        f"{health_icon(result.health_status)}"
    )
    print(
        f"  {C_HEADER}│{Style.RESET}  {C_LABEL}Anomaly       :{Style.RESET}  "
        f"{anomaly_badge(result.anomaly_detected)}  "
        f"{C_MUTED}(score: {result.anomaly_score:.4f}){Style.RESET}"
    )
    print(
        f"  {C_HEADER}│{Style.RESET}  {C_LABEL}Predicted RUL :{Style.RESET}  "
        f"{rul_display(result.predicted_rul_km)}"
    )
    if inference_ms > 0:
        print(
            f"  {C_HEADER}│{Style.RESET}  {C_LABEL}Inference Time:{Style.RESET}  "
            f"{C_INFO}{inference_ms:.2f} ms{Style.RESET}"
        )
    print(f"  {C_HEADER}│{Style.RESET}")
    print(f"  {C_HEADER}└──────────────────────────────────────────────────────────────┘{Style.RESET}")


def display_shap_analysis(root_cause: Dict[str, float], top_n: int = 8):
    """Display SHAP root-cause analysis as a horizontal bar chart."""
    print()
    print(f"  {C_BRAND2}{Style.BOLD}  SHAP Root-Cause Analysis  {Style.RESET}")
    print(f"  {C_MUTED}  Feature contributions to failure risk (% attribution){Style.RESET}")
    print()

    items = list(root_cause.items())[:top_n]
    if not items:
        print(f"  {C_MUTED}  No SHAP data available.{Style.RESET}")
        return

    max_abs = max(abs(v) for _, v in items) if items else 1.0
    bar_width = 35

    for name, pct in items:
        bar_len = int(abs(pct) / max_abs * bar_width) if max_abs > 0 else 0
        if pct > 0:
            bar_color = C_DANGER
            bar_char = "▓"
            sign = "+"
        else:
            bar_color = C_SUCCESS
            bar_char = "▒"
            sign = ""

        # Format name nicely
        display_name = name.replace("_", " ").title()

        print(
            f"  {C_LABEL}{display_name:<25s}{Style.RESET}"
            f" {bar_color}{bar_char * bar_len}{Style.RESET}"
            f"{'·' * max(0, bar_width - bar_len)}  "
            f"{bar_color}{Style.BOLD}{sign}{pct:>6.2f}%{Style.RESET}"
        )

    print()


def run_live_monitoring(engine: MLEngine, hw: HardwareManager, duration_frames: int = 8):
    """Run live monitoring with real-time predictions."""
    print()
    print(f"  {C_HEADER}{Style.BOLD}  LIVE TELEMETRY MONITORING  {Style.RESET}")
    print(f"  {C_MUTED}  Real-time 2 Hz sensor stream with ML inference{Style.RESET}")
    print(hr())
    print()

    predictions: List[PredictionResult] = []
    inference_times: List[float] = []
    temp_history: List[float] = []
    volt_history: List[float] = []

    for i in range(duration_frames):
        time.sleep(0.5)
        frame = hw.get_latest_frame()
        if frame is None:
            continue

        display_telemetry_frame(frame, i)

        temp_history.append(frame.get("coolant_temp_c", 0))
        volt_history.append(frame.get("battery_voltage_v", 0))

        # Run ML prediction every 2 frames (1 Hz inference)
        if i % 2 == 1:
            t0 = time.perf_counter()
            try:
                result = engine.predict(frame, vehicle_id="SIM-LIVE-001")
                t_ms = (time.perf_counter() - t0) * 1000
                predictions.append(result)
                inference_times.append(t_ms)
            except Exception as e:
                print(f"  {C_DANGER}Prediction error: {e}{Style.RESET}")

    # Show latest prediction
    if predictions:
        latest = predictions[-1]
        avg_ms = sum(inference_times) / len(inference_times)
        display_prediction(latest, avg_ms)
        display_shap_analysis(latest.root_cause_analysis)

    # Mini sparkline summary
    if temp_history:
        print(f"  {C_LABEL}Temperature trend:{Style.RESET}  "
              f"{C_ACCENT}{sparkline(temp_history, 20)}{Style.RESET}  "
              f"{C_MUTED}({min(temp_history):.0f}°C → {max(temp_history):.0f}°C){Style.RESET}")
    if volt_history:
        print(f"  {C_LABEL}Voltage trend:    {Style.RESET}  "
              f"{C_INFO}{sparkline(volt_history, 20)}{Style.RESET}  "
              f"{C_MUTED}({min(volt_history):.1f}V → {max(volt_history):.1f}V){Style.RESET}")
    print()

    return predictions


def run_fault_scenario(
    engine: MLEngine,
    hw: HardwareManager,
    fault_type: FaultType,
    severity: float = 0.8,
    duration: float = 5.0,
    label: str = "",
):
    """Run a fault injection scenario with before/after comparison."""
    print(hr_double(C_DANGER))
    print()
    fault_name = label or fault_type.value.replace("_", " ").upper()
    print(f"  {C_DANGER}{Style.BOLD}⚡ FAULT INJECTION: {fault_name}{Style.RESET}")
    print(f"  {C_MUTED}  Severity: {severity:.0%}  |  Duration: {duration:.0f}s{Style.RESET}")
    print()

    # --- Before fault: capture baseline ---
    print(f"  {C_SUCCESS}{Style.BOLD}▸ BASELINE (pre-fault){Style.RESET}")
    time.sleep(0.5)
    frame_before = hw.get_latest_frame()
    if frame_before:
        display_telemetry_frame(frame_before)
        t0 = time.perf_counter()
        result_before = engine.predict(frame_before, vehicle_id="SIM-FAULT-001")
        t_ms_before = (time.perf_counter() - t0) * 1000
        print(
            f"  {C_MUTED}  └─ Health: {health_color(result_before.health_status)}"
            f"{result_before.health_status}{Style.RESET}  "
            f"RUL: {rul_display(result_before.predicted_rul_km)}  "
            f"Anomaly: {'Yes' if result_before.anomaly_detected else 'No'}"
            f"{Style.RESET}"
        )
    print()

    # --- Inject fault ---
    print(f"  {C_DANGER}{Style.BOLD}▸ INJECTING FAULT...{Style.RESET}")
    hw.inject_fault(fault_type, severity=severity, duration_seconds=duration)
    print(f"  {C_DANGER}  ⚡ Fault active — monitoring degradation{Style.RESET}")
    print()

    # Monitor during fault
    for i in range(6):
        time.sleep(0.5)
        frame = hw.get_latest_frame()
        if frame:
            display_telemetry_frame(frame, i)

    # Prediction during fault
    frame_during = hw.get_latest_frame()
    if frame_during:
        t0 = time.perf_counter()
        result_during = engine.predict(frame_during, vehicle_id="SIM-FAULT-001")
        t_ms_during = (time.perf_counter() - t0) * 1000
        display_prediction(result_during, t_ms_during)
        display_shap_analysis(result_during.root_cause_analysis, top_n=5)

    # --- Recovery ---
    print(f"  {C_SUCCESS}{Style.BOLD}▸ RECOVERY PHASE{Style.RESET}")
    for i in range(4):
        time.sleep(0.5)
        frame = hw.get_latest_frame()
        if frame:
            display_telemetry_frame(frame, i)

    # Post-recovery prediction
    frame_after = hw.get_latest_frame()
    if frame_after:
        result_after = engine.predict(frame_after, vehicle_id="SIM-FAULT-001")
        hc = health_color(result_after.health_status)
        print(
            f"\n  {C_MUTED}  └─ Recovery status: {hc}{Style.BOLD}"
            f"{result_after.health_status}{Style.RESET}  "
            f"RUL: {rul_display(result_after.predicted_rul_km)}"
            f"{Style.RESET}"
        )

    print()


def run_batch_fleet_analysis(engine: MLEngine):
    """Run batch analysis on synthetic fleet data."""
    print(hr_double(C_BRAND2))
    print()
    print(f"  {C_BRAND2}{Style.BOLD}  FLEET BATCH ANALYSIS  {Style.RESET}")
    print(f"  {C_MUTED}  Multi-vehicle predictive maintenance scan{Style.RESET}")
    print()

    # Generate diverse synthetic vehicle payloads
    fleet = [
        {
            "vehicle_id": "FLEET-A001",
            "label": "Highway Cruiser",
            "engine_temp_c": 91.2,
            "engine_rpm": 2200.0,
            "coolant_temp_c": 88.5,
            "battery_voltage_v": 13.9,
            "vibration_level": 0.4,
            "odometer_reading": 45200.0,
            "engine_load": 35.0,
            "vehicle_speed": 110.0,
        },
        {
            "vehicle_id": "FLEET-B042",
            "label": "City Delivery Van",
            "engine_temp_c": 96.8,
            "engine_rpm": 1800.0,
            "coolant_temp_c": 94.2,
            "battery_voltage_v": 12.8,
            "vibration_level": 1.2,
            "odometer_reading": 128500.0,
            "engine_load": 55.0,
            "vehicle_speed": 35.0,
        },
        {
            "vehicle_id": "FLEET-C017",
            "label": "Long-Haul Truck",
            "engine_temp_c": 103.5,
            "engine_rpm": 1600.0,
            "coolant_temp_c": 101.8,
            "battery_voltage_v": 13.2,
            "vibration_level": 2.8,
            "odometer_reading": 320000.0,
            "engine_load": 72.0,
            "vehicle_speed": 85.0,
        },
        {
            "vehicle_id": "FLEET-D089",
            "label": "Aging Sedan",
            "engine_temp_c": 112.0,
            "engine_rpm": 3200.0,
            "coolant_temp_c": 109.5,
            "battery_voltage_v": 11.4,
            "vibration_level": 4.5,
            "odometer_reading": 245000.0,
            "engine_load": 68.0,
            "vehicle_speed": 70.0,
        },
        {
            "vehicle_id": "FLEET-E201",
            "label": "New Electric Hybrid",
            "engine_temp_c": 72.0,
            "engine_rpm": 1400.0,
            "coolant_temp_c": 70.5,
            "battery_voltage_v": 14.1,
            "vibration_level": 0.15,
            "odometer_reading": 8500.0,
            "engine_load": 22.0,
            "vehicle_speed": 55.0,
        },
    ]

    results: List[Dict[str, Any]] = []
    total_t0 = time.perf_counter()

    print(
        f"  {C_LABEL}{'Vehicle':<14s}  {'Description':<20s}  "
        f"{'Health':<10s}  {'RUL (km)':<12s}  {'Anomaly':<9s}  "
        f"{'Top Risk Factor':<25s}  {'Time':<8s}{Style.RESET}"
    )
    print(f"  {C_MUTED}{'─' * 105}{Style.RESET}")

    for v in fleet:
        vid = v.pop("vehicle_id")
        label = v.pop("label")
        t0 = time.perf_counter()
        try:
            result = engine.predict(v, vehicle_id=vid)
            t_ms = (time.perf_counter() - t0) * 1000

            hc = health_color(result.health_status)
            top_factor = ""
            if result.root_cause_analysis:
                top_name = list(result.root_cause_analysis.keys())[0]
                top_val = list(result.root_cause_analysis.values())[0]
                top_factor = f"{top_name.replace('_', ' ').title()} ({top_val:+.1f}%)"

            anom_str = (
                f"{C_DANGER}YES{Style.RESET}" if result.anomaly_detected
                else f"{C_SUCCESS}No{Style.RESET}"
            )

            print(
                f"  {C_VALUE}{vid:<14s}{Style.RESET}  "
                f"{C_MUTED}{label:<20s}{Style.RESET}  "
                f"{hc}{result.health_status:<10s}{Style.RESET}  "
                f"{rul_display(result.predicted_rul_km):<22s}  "
                f"{anom_str:<19s}  "
                f"{C_LABEL}{top_factor:<25s}{Style.RESET}  "
                f"{C_INFO}{t_ms:>5.1f}ms{Style.RESET}"
            )

            results.append({
                "vehicle_id": vid,
                "label": label,
                "result": result,
                "time_ms": t_ms,
            })
        except Exception as e:
            print(f"  {C_DANGER}{vid:<14s}  ERROR: {e}{Style.RESET}")

    total_ms = (time.perf_counter() - total_t0) * 1000
    print(f"  {C_MUTED}{'─' * 105}{Style.RESET}")
    print()

    # Fleet summary statistics
    if results:
        n_healthy = sum(1 for r in results if r["result"].health_status == "HEALTHY")
        n_advisory = sum(1 for r in results if r["result"].health_status == "ADVISORY")
        n_critical = sum(1 for r in results if r["result"].health_status == "CRITICAL")
        n_anomaly = sum(1 for r in results if r["result"].anomaly_detected)
        avg_rul = np.mean([r["result"].predicted_rul_km for r in results])
        avg_time = np.mean([r["time_ms"] for r in results])

        print(f"  {C_HEADER}{Style.BOLD}┌─── FLEET SUMMARY ───────────────────────────────────────────┐{Style.RESET}")
        print(f"  {C_HEADER}│{Style.RESET}")
        print(
            f"  {C_HEADER}│{Style.RESET}  {C_LABEL}Vehicles Scanned :{Style.RESET}  "
            f"{C_VALUE}{Style.BOLD}{len(results)}{Style.RESET}"
        )
        print(
            f"  {C_HEADER}│{Style.RESET}  {C_LABEL}Fleet Health      :{Style.RESET}  "
            f"{C_SUCCESS}● Healthy: {n_healthy}{Style.RESET}  "
            f"{C_WARNING}▲ Advisory: {n_advisory}{Style.RESET}  "
            f"{C_DANGER}■ Critical: {n_critical}{Style.RESET}"
        )
        fleet_score = (n_healthy / len(results)) * 100 if results else 0
        score_color = C_SUCCESS if fleet_score > 70 else (C_WARNING if fleet_score > 40 else C_DANGER)
        print(
            f"  {C_HEADER}│{Style.RESET}  {C_LABEL}Fleet Score       :{Style.RESET}  "
            f"{score_color}{Style.BOLD}{fleet_score:.0f}%{Style.RESET}  "
            f"{progress_bar(fleet_score, 100, 20, score_color, C_MUTED)}"
        )
        print(
            f"  {C_HEADER}│{Style.RESET}  {C_LABEL}Anomalies Found  :{Style.RESET}  "
            f"{C_DANGER if n_anomaly else C_SUCCESS}{n_anomaly} / {len(results)}{Style.RESET}"
        )
        print(
            f"  {C_HEADER}│{Style.RESET}  {C_LABEL}Avg. RUL          :{Style.RESET}  "
            f"{rul_display(avg_rul)}"
        )
        print(
            f"  {C_HEADER}│{Style.RESET}  {C_LABEL}Total Batch Time  :{Style.RESET}  "
            f"{C_INFO}{total_ms:.1f} ms{Style.RESET}  "
            f"{C_MUTED}(avg {avg_time:.1f} ms/vehicle){Style.RESET}"
        )
        print(f"  {C_HEADER}│{Style.RESET}")
        print(f"  {C_HEADER}└──────────────────────────────────────────────────────────────┘{Style.RESET}")

    print()
    return results


def run_csv_analysis(engine: MLEngine):
    """Run analysis on the CSV test dataset and show sample results."""
    csv_path = "data/test_vehicle_telemetry.csv"
    if not os.path.exists(csv_path):
        print(f"  {C_WARNING}CSV dataset not found at {csv_path} — skipping.{Style.RESET}")
        return

    print(hr_double(C_INFO))
    print()
    print(f"  {C_INFO}{Style.BOLD}  CSV DATASET ANALYSIS  {Style.RESET}")
    print(f"  {C_MUTED}  Analyzing historical telemetry from {csv_path}{Style.RESET}")
    print()

    animate_loading("Loading and preprocessing CSV dataset", duration=0.8)

    loader = AutomotiveDataLoader(window_size=30)
    df = loader.load_csv(csv_path)
    X = loader.get_feature_matrix(df)

    print(f"  {C_LABEL}Dataset Shape    :{Style.RESET}  {C_VALUE}{df.shape[0]:,} rows × {df.shape[1]} columns{Style.RESET}")
    print(f"  {C_LABEL}Feature Columns  :{Style.RESET}  {C_VALUE}{X.shape[1]} features{Style.RESET}")

    # Show failure distribution
    if "failure_type" in df.columns:
        failure_dist = df["failure_type"].value_counts()
        print(f"\n  {C_LABEL}Failure Distribution:{Style.RESET}")
        for ftype, count in failure_dist.items():
            pct = count / len(df) * 100
            bar = progress_bar(pct, 100, 15, C_WARNING if ftype != "No Failure" else C_SUCCESS, C_MUTED)
            print(f"    {C_VALUE}{ftype:<25s}{Style.RESET} {bar} {C_MUTED}{count:>5d} ({pct:.1f}%){Style.RESET}")

    # Run predictions on a few sample rows
    print(f"\n  {C_LABEL}Sample Predictions (5 random rows):{Style.RESET}")
    print(f"  {C_MUTED}{'─' * 90}{Style.RESET}")

    np.random.seed(42)
    sample_indices = np.random.choice(len(df), min(5, len(df)), replace=False)

    for idx in sorted(sample_indices):
        row = df.iloc[idx]
        payload = {
            "engine_temp_c": float(row.get("engine_temp_c", 0)),
            "engine_rpm": float(row.get("engine_rpm", 0)),
            "coolant_temp_c": float(row.get("coolant_temp_c", 0)),
            "battery_voltage_v": float(row.get("battery_voltage_v", 0)),
            "vibration_level": float(row.get("vibration_level", 0)),
            "odometer_reading": float(row.get("odometer_reading", 0)),
            "engine_load": float(row.get("engine_load", 0)),
            "vehicle_speed": float(row.get("vehicle_speed", 0)),
        }
        try:
            result = engine.predict(payload, vehicle_id=f"CSV-{idx:04d}")
            hc = health_color(result.health_status)
            print(
                f"  {C_MUTED}Row {idx:>4d}{Style.RESET}  "
                f"{hc}{result.health_status:<9s}{Style.RESET}  "
                f"RUL: {rul_display(result.predicted_rul_km):<20s}  "
                f"Anomaly: {'Yes' if result.anomaly_detected else 'No ':<4s}  "
                f"{C_MUTED}Score: {result.anomaly_score:.3f}{Style.RESET}"
            )
        except Exception:
            pass

    print()


def display_final_dashboard(
    live_predictions: List[PredictionResult],
    fleet_results: List[Dict[str, Any]],
):
    """Display a final summary dashboard."""
    print(hr_double(C_BRAND))
    print()
    print(center(
        f"{C_BRAND}{Style.BOLD}══  VELOPULSEAI DEMO COMPLETE  ══{Style.RESET}"
    ))
    print()

    all_results = []
    if live_predictions:
        all_results.extend(live_predictions)
    if fleet_results:
        all_results.extend([r["result"] for r in fleet_results])

    if not all_results:
        print(f"  {C_MUTED}No predictions were made during this session.{Style.RESET}")
        return

    n_total = len(all_results)
    n_anomaly = sum(1 for r in all_results if r.anomaly_detected)
    n_healthy = sum(1 for r in all_results if r.health_status == "HEALTHY")
    n_advisory = sum(1 for r in all_results if r.health_status == "ADVISORY")
    n_critical = sum(1 for r in all_results if r.health_status == "CRITICAL")
    avg_rul = np.mean([r.predicted_rul_km for r in all_results])

    # Header boxes
    box_w = 22
    print(f"  ┌{'─' * box_w}┐  ┌{'─' * box_w}┐  ┌{'─' * box_w}┐")
    print(
        f"  │{C_VALUE}{Style.BOLD}{'Predictions':^{box_w}s}{Style.RESET}│  "
        f"│{C_DANGER}{Style.BOLD}{'Anomalies':^{box_w}s}{Style.RESET}│  "
        f"│{C_INFO}{Style.BOLD}{'Avg RUL':^{box_w}s}{Style.RESET}│"
    )
    print(
        f"  │{C_BRAND}{Style.BOLD}{n_total:^{box_w}d}{Style.RESET}│  "
        f"│{C_DANGER}{Style.BOLD}{n_anomaly:^{box_w}d}{Style.RESET}│  "
        f"│{C_INFO}{Style.BOLD}{avg_rul:^{box_w},.0f} km{Style.RESET}│"
    )
    print(f"  └{'─' * box_w}┘  └{'─' * box_w}┘  └{'─' * box_w}┘")

    print()

    # Health distribution bar
    total = n_healthy + n_advisory + n_critical
    if total > 0:
        bar_total = 50
        h_bar = int(n_healthy / total * bar_total)
        a_bar = int(n_advisory / total * bar_total)
        c_bar = bar_total - h_bar - a_bar

        print(f"  {C_LABEL}Health Distribution:{Style.RESET}")
        print(
            f"  {C_SUCCESS}{'█' * h_bar}{C_WARNING}{'█' * a_bar}"
            f"{C_DANGER}{'█' * c_bar}{Style.RESET}"
        )
        print(
            f"  {C_SUCCESS}Healthy: {n_healthy}{Style.RESET}    "
            f"{C_WARNING}Advisory: {n_advisory}{Style.RESET}    "
            f"{C_DANGER}Critical: {n_critical}{Style.RESET}"
        )

    print()
    print(center(f"{C_MUTED}Pipeline: Isolation Forest → XGBoost RUL → SHAP Explainability{Style.RESET}"))
    print(center(f"{C_MUTED}Hardware: Tier 1 Simulation (2 Hz) · Serial · Bluetooth OBD-II{Style.RESET}"))
    print()
    print(hr_double(C_BRAND))
    print()
    print(center(f"{C_BRAND}{Style.BOLD}Thank you for exploring VeloPulseAI!{Style.RESET}"))
    print(center(f"{C_MUTED}Built with scikit-learn · XGBoost · SHAP · FastAPI{Style.RESET}"))
    print()


# ═══════════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="VeloPulseAI — Interactive Terminal Demo & Prototype Showcase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python demo.py                     Full interactive demo
  python demo.py --quick             Quick 30-second summary
  python demo.py --scenario thermal  Thermal runaway fault scenario
  python demo.py --scenario voltage  Voltage drop fault scenario
  python demo.py --scenario combined Combined multi-fault scenario
  python demo.py --batch             Fleet batch analysis only
  python demo.py --csv               CSV dataset analysis only
        """,
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run a quick 30-second demo with minimal output.",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=["thermal", "voltage", "vibration", "misfire", "combined", "all"],
        default=None,
        help="Run a specific fault injection scenario.",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run fleet batch analysis only.",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Run CSV dataset analysis only.",
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Skip the ASCII art banner.",
    )
    args = parser.parse_args()

    # --- Initialize ---
    engine = MLEngine()
    hw = HardwareManager()

    live_predictions: List[PredictionResult] = []
    fleet_results: List[Dict[str, Any]] = []

    try:
        # Banner
        if not args.no_banner:
            print_banner()

        # Boot
        boot_sequence(engine, hw)

        if args.batch:
            # Batch-only mode
            fleet_results = run_batch_fleet_analysis(engine)

        elif args.csv:
            # CSV analysis only
            run_csv_analysis(engine)

        elif args.scenario:
            # Specific fault scenario
            fault_map = {
                "thermal": (FaultType.THERMAL_RUNAWAY, "THERMAL RUNAWAY"),
                "voltage": (FaultType.VOLTAGE_DROP, "VOLTAGE DROP"),
                "vibration": (FaultType.BEARING_VIBRATION, "BEARING VIBRATION"),
                "misfire": (FaultType.ENGINE_MISFIRE, "ENGINE MISFIRE"),
                "combined": (FaultType.COMBINED, "COMBINED MULTI-FAULT"),
            }

            if args.scenario == "all":
                for key, (ft, label) in fault_map.items():
                    run_fault_scenario(engine, hw, ft, severity=0.8, duration=4.0, label=label)
                    time.sleep(2.0)  # Recovery time between scenarios
            else:
                ft, label = fault_map[args.scenario]
                run_fault_scenario(engine, hw, ft, severity=0.8, duration=5.0, label=label)

        elif args.quick:
            # Quick demo
            live_predictions = run_live_monitoring(engine, hw, duration_frames=4)
            fleet_results = run_batch_fleet_analysis(engine)

        else:
            # Full demo
            # Phase 1: Live monitoring
            live_predictions = run_live_monitoring(engine, hw, duration_frames=8)

            # Phase 2: Fault scenarios
            print()
            input(f"  {C_BRAND}Press Enter to begin fault injection scenarios...{Style.RESET}")
            print()

            run_fault_scenario(
                engine, hw,
                FaultType.THERMAL_RUNAWAY,
                severity=0.8,
                duration=5.0,
                label="THERMAL RUNAWAY",
            )

            time.sleep(1.5)

            run_fault_scenario(
                engine, hw,
                FaultType.COMBINED,
                severity=0.9,
                duration=4.0,
                label="COMBINED MULTI-FAULT CATASTROPHE",
            )

            # Phase 3: Fleet batch analysis
            print()
            input(f"  {C_BRAND}Press Enter for fleet batch analysis...{Style.RESET}")
            print()
            fleet_results = run_batch_fleet_analysis(engine)

            # Phase 4: CSV analysis
            run_csv_analysis(engine)

        # Final dashboard
        display_final_dashboard(live_predictions, fleet_results)

    except KeyboardInterrupt:
        print(f"\n\n  {C_WARNING}Demo interrupted by user.{Style.RESET}")
    finally:
        hw.stop()
        print(f"  {C_MUTED}Hardware manager stopped. Goodbye!{Style.RESET}\n")


if __name__ == "__main__":
    main()

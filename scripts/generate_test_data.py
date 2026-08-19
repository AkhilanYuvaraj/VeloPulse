"""
Generate a realistic test dataset matching the Kaggle Vehicle Maintenance
Telemetry schema for pipeline validation ONLY.

This script creates a CSV with physically plausible automotive sensor readings
including normal operation, degradation patterns, and failure events.
"""

import numpy as np
import pandas as pd
from pathlib import Path

np.random.seed(42)

N = 2000  # total samples
data = {
    "engine_temp_c": [],
    "engine_rpm": [],
    "coolant_temp_c": [],
    "battery_voltage_v": [],
    "vibration_level": [],
    "odometer_reading": [],
    "engine_load": [],
    "vehicle_speed": [],
    "failure_type": [],
}

odometer = 50000.0  # starting mileage in km

# Define failure events at specific intervals
failure_points = [400, 800, 1200, 1600]
failure_types = ["Engine Overheating", "Battery Failure", "Brake Wear", "Engine Overheating"]

for i in range(N):
    # Base driving conditions with realistic variation
    is_degrading = any(abs(i - fp) < 60 for fp in failure_points)
    is_failure = i in failure_points
    degrade_factor = 0.0

    if is_degrading:
        closest_fp = min(failure_points, key=lambda fp: abs(i - fp))
        if i <= closest_fp:
            degrade_factor = max(0, 1.0 - (closest_fp - i) / 60.0)

    # Engine temperature: normal 85-100°C, degrades to 110-130°C
    base_engine_temp = np.random.normal(92, 4)
    engine_temp = base_engine_temp + degrade_factor * np.random.uniform(20, 40)
    data["engine_temp_c"].append(round(engine_temp, 1))

    # Engine RPM: normal 700-4000 RPM
    rpm = np.random.normal(2200, 600)
    rpm = max(650, min(6500, rpm + degrade_factor * np.random.uniform(-300, 800)))
    data["engine_rpm"].append(round(rpm, 0))

    # Coolant temperature: tracks engine temp with slight lag
    coolant = engine_temp - np.random.uniform(2, 8) + degrade_factor * 15
    data["coolant_temp_c"].append(round(coolant, 1))

    # Battery voltage: normal 12.4-14.2V, drops during degradation
    voltage = np.random.normal(13.2, 0.4)
    voltage -= degrade_factor * np.random.uniform(1.5, 3.0)
    voltage = max(9.0, min(15.0, voltage))
    data["battery_voltage_v"].append(round(voltage, 2))

    # Vibration level: normal 0.5-2.0, spikes during degradation
    vibration = np.random.exponential(0.8) + 0.3
    vibration += degrade_factor * np.random.uniform(2.0, 6.0)
    data["vibration_level"].append(round(vibration, 3))

    # Odometer: increments ~5-15 km per sample
    odometer += np.random.uniform(5, 15)
    data["odometer_reading"].append(round(odometer, 1))

    # Engine load: 15-85%
    load = np.random.normal(45, 15)
    load = max(5, min(100, load + degrade_factor * 20))
    data["engine_load"].append(round(load, 1))

    # Vehicle speed: 0-120 km/h
    speed = np.random.normal(55, 20)
    speed = max(0, min(180, speed))
    data["vehicle_speed"].append(round(speed, 1))

    # Failure type
    if is_failure:
        idx = failure_points.index(i)
        data["failure_type"].append(failure_types[idx])
    else:
        data["failure_type"].append("No Failure")

df = pd.DataFrame(data)

out_dir = Path(__file__).resolve().parent.parent / "data"
out_dir.mkdir(exist_ok=True)
out_path = out_dir / "test_vehicle_telemetry.csv"
df.to_csv(out_path, index=False)

print(f"Generated {len(df)} rows -> {out_path}")
print(f"\nColumn dtypes:\n{df.dtypes}")
print(f"\nFailure distribution:\n{df['failure_type'].value_counts()}")
print(f"\nSample rows:\n{df.head(3).to_string()}")

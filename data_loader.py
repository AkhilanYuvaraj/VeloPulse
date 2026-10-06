"""
VeloPulseAI — Automotive Data Ingestion & Feature Engineering Module.

Ingests real automotive telemetry datasets (Kaggle Vehicle Maintenance CSV
and live OBD-II JSON streams), normalises column names to a canonical schema,
and engineers time-series / physics-based features for downstream ML models.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd

logger = logging.getLogger("velopulse.data_loader")

# ---------------------------------------------------------------------------
# Canonical column schema used throughout the pipeline
# ---------------------------------------------------------------------------
CANONICAL_COLUMNS: List[str] = [
    "engine_temp_c",
    "engine_rpm",
    "coolant_temp_c",
    "battery_voltage_v",
    "vibration_level",
    "odometer_reading",
    "engine_load",
    "vehicle_speed",
    "failure_type",
]

# Mapping from common OBD-II / Kaggle naming conventions → canonical names
_COLUMN_ALIASES: Dict[str, str] = {
    # OBD-II PID names
    "ENGINE_RPM": "engine_rpm",
    "COOLANT_TEMPERATURE": "coolant_temp_c",
    "CONTROL_MODULE_VOLTAGE": "battery_voltage_v",
    "ENGINE_LOAD": "engine_load",
    "VEHICLE_SPEED": "vehicle_speed",
    # Kaggle dataset variants
    "Engine Temperature (C)": "engine_temp_c",
    "Engine RPM": "engine_rpm",
    "Coolant Temperature (C)": "coolant_temp_c",
    "Battery Voltage (V)": "battery_voltage_v",
    "Vibration Level": "vibration_level",
    "Odometer Reading": "odometer_reading",
    "Failure Type": "failure_type",
    "engine_temperature": "engine_temp_c",
    "coolant_temperature": "coolant_temp_c",
    "battery_voltage": "battery_voltage_v",
    "control_module_voltage": "battery_voltage_v",
    "vehicle_speed_kmh": "vehicle_speed",
}

# Features required for ML training (failure_type is the label, not a feature)
ML_FEATURE_COLUMNS: List[str] = [
    "engine_temp_c",
    "engine_rpm",
    "coolant_temp_c",
    "battery_voltage_v",
    "vibration_level",
    "engine_load",
    "vehicle_speed",
]

# Engineered feature names appended after feature engineering
ENGINEERED_FEATURES: List[str] = [
    "coolant_temp_slope",
    "engine_temp_slope",
    "battery_voltage_dip",
    "vibration_rms",
]


class AutomotiveDataLoader:
    """Loads and processes real automotive telemetry data from CSV or JSON."""

    WINDOW_SIZE: int = 30  # 30-sample sliding window

    def __init__(self, window_size: int = 30) -> None:
        self.WINDOW_SIZE = window_size
        logger.info(
            "AutomotiveDataLoader initialised (window=%d)", self.WINDOW_SIZE
        )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    @staticmethod
    def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Rename columns to the canonical schema using known alias mappings."""
        rename_map = {
            col: _COLUMN_ALIASES[col]
            for col in df.columns
            if col in _COLUMN_ALIASES
        }
        df = df.rename(columns=rename_map)

        # Also handle snake_case / lowercase variants
        lower_map: Dict[str, str] = {}
        for col in df.columns:
            normalised = col.strip().lower().replace(" ", "_").replace("(", "").replace(")", "")
            if normalised in {c.lower().replace(" ", "_") for c in _COLUMN_ALIASES.values()}:
                # Find matching canonical name
                for canonical in CANONICAL_COLUMNS:
                    if normalised == canonical.lower():
                        lower_map[col] = canonical
                        break
        df = df.rename(columns=lower_map)

        return df

    # ------------------------------------------------------------------
    # CSV ingestion
    # ------------------------------------------------------------------
    def load_csv(self, filepath: Union[str, Path]) -> pd.DataFrame:
        """
        Load an automotive telemetry CSV, normalise columns, fill gaps,
        and engineer features.

        Parameters
        ----------
        filepath : str or Path
            Path to a local CSV file containing vehicle telemetry data.

        Returns
        -------
        pd.DataFrame
            Processed DataFrame with canonical + engineered columns.
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Dataset not found: {filepath}")

        logger.info("Loading CSV dataset from %s", filepath)
        df = pd.read_csv(filepath)
        logger.info(
            "Raw dataset shape: %s  |  Columns: %s",
            df.shape,
            list(df.columns),
        )

        df = self.normalise_columns(df)
        df = self._fill_missing(df)
        df = self._engineer_features(df)
        logger.info(
            "Processed dataset shape: %s  |  Columns: %s",
            df.shape,
            list(df.columns),
        )
        return df

    # ------------------------------------------------------------------
    # JSON / OBD-II stream ingestion
    # ------------------------------------------------------------------
    def load_json_payload(
        self, payload: Union[Dict, List[Dict]]
    ) -> pd.DataFrame:
        """
        Parse a single JSON dict (one telemetry snapshot) or a list of
        JSON dicts (batch), normalise, and engineer features.

        Parameters
        ----------
        payload : dict or list[dict]
            Raw telemetry captured from an OBD-II / ECU scanner.

        Returns
        -------
        pd.DataFrame
            Processed DataFrame ready for inference.
        """
        if isinstance(payload, dict):
            payload = [payload]

        df = pd.DataFrame(payload)
        df = self.normalise_columns(df)
        df = self._fill_missing(df)
        df = self._engineer_features(df)
        return df

    # ------------------------------------------------------------------
    # Feature engineering
    # ------------------------------------------------------------------
    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute physics-based rolling features over a sliding window.

        Features
        --------
        - coolant_temp_slope   : dT/dt of coolant temperature (°C per sample)
        - engine_temp_slope    : dT/dt of engine temperature
        - battery_voltage_dip  : ΔV — difference between rolling max and current
        - vibration_rms        : Root-mean-square vibration power
        - rul_km               : Remaining Useful Life proxy (km until failure)
        """
        w = self.WINDOW_SIZE

        def _safe_slope(s: np.ndarray) -> float:
            """Compute linear regression slope; return 0.0 for degenerate windows."""
            if len(s) < 2:
                return 0.0
            try:
                return float(np.polyfit(np.arange(len(s)), s, 1)[0])
            except (np.linalg.LinAlgError, ValueError):
                return 0.0

        # --- Temperature slopes (first-order finite difference over window) ---
        if "coolant_temp_c" in df.columns:
            df["coolant_temp_slope"] = (
                df["coolant_temp_c"]
                .rolling(window=w, min_periods=2)
                .apply(_safe_slope, raw=True)
            ).fillna(0.0)
        else:
            df["coolant_temp_slope"] = 0.0

        if "engine_temp_c" in df.columns:
            df["engine_temp_slope"] = (
                df["engine_temp_c"]
                .rolling(window=w, min_periods=2)
                .apply(_safe_slope, raw=True)
            ).fillna(0.0)
        else:
            df["engine_temp_slope"] = 0.0

        # --- Battery voltage cranking dip ---
        if "battery_voltage_v" in df.columns:
            rolling_max = (
                df["battery_voltage_v"]
                .rolling(window=w, min_periods=1)
                .max()
            )
            df["battery_voltage_dip"] = rolling_max - df["battery_voltage_v"]
        else:
            df["battery_voltage_dip"] = 0.0

        # --- Vibration RMS (root-mean-square magnitude) ---
        if "vibration_level" in df.columns:
            df["vibration_rms"] = (
                df["vibration_level"]
                .rolling(window=w, min_periods=1)
                .apply(lambda s: np.sqrt(np.mean(s ** 2)), raw=True)
            )
        else:
            df["vibration_rms"] = 0.0

        # --- RUL target: mileage delta until next failure event ---
        df["rul_km"] = self._compute_rul(df)

        return df

    @staticmethod
    def _compute_rul(df: pd.DataFrame) -> pd.Series:
        """
        Compute Remaining Useful Life (RUL) in km for every row.

        For each row, RUL = (odometer at next failure) − (current odometer).
        Rows after the last failure event are assigned a default high RUL.

        If no failure/odometer information is available (e.g. live inference),
        a placeholder of NaN is returned.
        """
        default_rul = 50_000.0  # default high RUL when no failure ahead

        if "odometer_reading" not in df.columns:
            return pd.Series(np.nan, index=df.index)

        has_failure = "failure_type" in df.columns
        if not has_failure:
            return pd.Series(default_rul, index=df.index)

        rul = pd.Series(default_rul, index=df.index, dtype=np.float64)

        # Identify indices where a failure occurs (non-null, non-'None', non-empty)
        failure_mask = (
            df["failure_type"].notna()
            & (df["failure_type"].astype(str).str.strip().str.lower() != "none")
            & (df["failure_type"].astype(str).str.strip() != "")
            & (df["failure_type"].astype(str).str.strip().str.lower() != "no failure")
        )
        failure_indices = df.index[failure_mask].tolist()

        if not failure_indices:
            return rul

        # Walk through each failure event and back-fill RUL
        odometer = df["odometer_reading"].values
        failure_idx_ptr = 0

        for i in range(len(df)):
            # Advance pointer past current index
            while (
                failure_idx_ptr < len(failure_indices)
                and failure_indices[failure_idx_ptr] <= i
            ):
                failure_idx_ptr += 1

            if failure_idx_ptr < len(failure_indices):
                next_failure = failure_indices[failure_idx_ptr]
                rul.iloc[i] = max(
                    odometer[next_failure] - odometer[i], 0.0
                )
            else:
                rul.iloc[i] = default_rul

        return rul

    # ------------------------------------------------------------------
    # Data cleaning
    # ------------------------------------------------------------------
    @staticmethod
    def _fill_missing(df: pd.DataFrame) -> pd.DataFrame:
        """Forward-fill then back-fill numeric gaps; drop fully-empty rows."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = df[numeric_cols].ffill().bfill()

        # For columns that still have NaN (e.g. entirely missing), fill with 0
        for col in ML_FEATURE_COLUMNS:
            if col in df.columns and df[col].isna().any():
                df[col] = df[col].fillna(0.0)

        return df

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def get_feature_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract the final ML feature matrix from a processed DataFrame.

        Returns only the canonical ML features plus engineered features,
        filling any missing columns with zeros.
        """
        all_features = ML_FEATURE_COLUMNS + ENGINEERED_FEATURES
        for col in all_features:
            if col not in df.columns:
                df[col] = 0.0
        return df[all_features].copy()

    def get_target(self, df: pd.DataFrame) -> pd.Series:
        """Return the RUL target vector."""
        if "rul_km" not in df.columns:
            raise ValueError("DataFrame has no 'rul_km' column — run feature engineering first.")
        return df["rul_km"].copy()

"""
VeloPulseAI — ML Inference Engine.

Loads trained model artifacts (Isolation Forest, XGBoost, StandardScaler)
and runs the 3-stage predictive pipeline on live OBD-II telemetry payloads:

  Stage 1 → Anomaly detection (IsolationForest)
  Stage 2 → Remaining Useful Life regression (XGBoost)
  Stage 3 → SHAP-based explainability (TreeExplainer)
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from data_loader import (
    AutomotiveDataLoader,
    ENGINEERED_FEATURES,
    ML_FEATURE_COLUMNS,
)

logger = logging.getLogger("velopulse.ml_engine")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MODEL_DIR = Path("models")
ANOMALY_MODEL_PATH = MODEL_DIR / "anomaly_iforest.joblib"
RUL_MODEL_PATH = MODEL_DIR / "rul_xgb.joblib"
SCALER_PATH = MODEL_DIR / "feature_scaler.joblib"
FEATURE_NAMES_PATH = MODEL_DIR / "feature_names.joblib"

# Health status thresholds (RUL in km)
RUL_CRITICAL_THRESHOLD = 500.0
RUL_ADVISORY_THRESHOLD = 5000.0


class PredictionResult:
    """Structured container for a single vehicle prediction."""

    def __init__(
        self,
        vehicle_id: str,
        anomaly_detected: bool,
        anomaly_score: float,
        health_status: str,
        predicted_rul_km: float,
        root_cause_analysis: Dict[str, float],
    ) -> None:
        self.vehicle_id = vehicle_id
        self.anomaly_detected = anomaly_detected
        self.anomaly_score = anomaly_score
        self.health_status = health_status
        self.predicted_rul_km = predicted_rul_km
        self.root_cause_analysis = root_cause_analysis

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vehicle_id": self.vehicle_id,
            "anomaly_detected": self.anomaly_detected,
            "anomaly_score": round(self.anomaly_score, 4),
            "health_status": self.health_status,
            "predicted_rul_km": round(self.predicted_rul_km, 2),
            "root_cause_analysis": self.root_cause_analysis,
        }


class MLEngine:
    """
    Production inference engine for VeloPulseAI.

    Loads serialised model artifacts once at startup and exposes a
    ``predict()`` method that accepts raw OBD-II JSON telemetry.
    """

    def __init__(self, model_dir: Optional[str] = None) -> None:
        base = Path(model_dir) if model_dir else MODEL_DIR
        self._anomaly_model_path = base / "anomaly_iforest.joblib"
        self._rul_model_path = base / "rul_xgb.joblib"
        self._scaler_path = base / "feature_scaler.joblib"
        self._feature_names_path = base / "feature_names.joblib"

        self.anomaly_model: Optional[IsolationForest] = None
        self.rul_model: Optional[XGBRegressor] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_names: Optional[List[str]] = None
        self.shap_explainer: Optional[shap.TreeExplainer] = None

        self.loader = AutomotiveDataLoader(window_size=30)
        self._loaded = False

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------
    def load_models(self) -> None:
        """Load all trained artifacts from disk."""
        logger.info("Loading model artifacts …")
        try:
            self.anomaly_model = joblib.load(self._anomaly_model_path)
            logger.info("  ✓ Anomaly model loaded from %s", self._anomaly_model_path)

            self.rul_model = joblib.load(self._rul_model_path)
            logger.info("  ✓ RUL model loaded from %s", self._rul_model_path)

            self.scaler = joblib.load(self._scaler_path)
            logger.info("  ✓ Feature scaler loaded from %s", self._scaler_path)

            self.feature_names = joblib.load(self._feature_names_path)
            logger.info("  ✓ Feature names loaded: %s", self.feature_names)

            # Initialise SHAP TreeExplainer for the XGBoost model
            self.shap_explainer = shap.TreeExplainer(self.rul_model)
            logger.info("  ✓ SHAP TreeExplainer initialised")

            self._loaded = True
            logger.info("All model artifacts loaded successfully.")
        except FileNotFoundError as exc:
            logger.error("Model artifact missing: %s", exc)
            raise RuntimeError(
                f"Model artifact not found: {exc}. "
                "Run train_pipeline.py first to generate model files."
            ) from exc

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------
    def predict(
        self,
        payload: Dict[str, Any],
        vehicle_id: str = "unknown",
    ) -> PredictionResult:
        """
        Run the full 3-stage predictive pipeline on a single telemetry snapshot.

        Parameters
        ----------
        payload : dict
            Raw OBD-II / sensor JSON payload (single reading).
        vehicle_id : str
            Identifier of the vehicle for traceability.

        Returns
        -------
        PredictionResult
            Structured prediction containing anomaly flag, health status,
            predicted RUL, and SHAP root-cause breakdown.
        """
        if not self._loaded:
            raise RuntimeError("Models not loaded — call load_models() first.")

        # --- 0. Ingest & engineer features ---------------------------------
        df = self.loader.load_json_payload(payload)
        X = self.loader.get_feature_matrix(df)

        # Align columns to training order
        X = self._align_features(X)

        # Scale
        X_scaled = pd.DataFrame(
            self.scaler.transform(X),
            columns=X.columns,
            index=X.index,
        )

        # Use the last row for single-snapshot prediction
        x_row = X_scaled.iloc[[-1]]

        # --- Stage 1: Anomaly detection ------------------------------------
        anomaly_label = int(self.anomaly_model.predict(x_row)[0])
        anomaly_score = float(-self.anomaly_model.decision_function(x_row)[0])
        anomaly_detected = anomaly_label == -1

        # --- Stage 2: RUL prediction --------------------------------------
        predicted_rul = float(self.rul_model.predict(x_row)[0])
        predicted_rul = max(predicted_rul, 0.0)  # clamp at zero

        # --- Stage 3: SHAP explainability ----------------------------------
        root_cause = self._compute_shap_contributions(x_row)

        # --- Derive health status ------------------------------------------
        health_status = self._determine_health_status(
            anomaly_detected, predicted_rul
        )

        logger.info(
            "Prediction for %s — anomaly=%s  rul=%.1f km  status=%s",
            vehicle_id,
            anomaly_detected,
            predicted_rul,
            health_status,
        )

        return PredictionResult(
            vehicle_id=vehicle_id,
            anomaly_detected=anomaly_detected,
            anomaly_score=anomaly_score,
            health_status=health_status,
            predicted_rul_km=predicted_rul,
            root_cause_analysis=root_cause,
        )

    def predict_batch(
        self,
        payloads: List[Dict[str, Any]],
        vehicle_id: str = "unknown",
    ) -> List[PredictionResult]:
        """
        Run prediction on a batch of telemetry snapshots.

        Each payload is processed independently to avoid cross-contamination
        of rolling-window features between unrelated vehicles.
        """
        results: List[PredictionResult] = []
        for idx, payload in enumerate(payloads):
            vid = payload.get("vehicle_id", f"{vehicle_id}_{idx}")
            result = self.predict(payload, vehicle_id=vid)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # SHAP explainability
    # ------------------------------------------------------------------
    def _compute_shap_contributions(
        self, x_row: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Calculate feature-level SHAP contributions and convert them to
        percentage risk attributions.

        Returns
        -------
        dict
            Mapping of feature name → signed percentage contribution.
            Positive values increase failure risk; negative values decrease it.
        """
        shap_values = self.shap_explainer.shap_values(x_row)
        shap_array = np.array(shap_values).flatten()

        abs_sum = float(np.abs(shap_array).sum())
        if abs_sum == 0:
            abs_sum = 1.0  # prevent division by zero

        contributions: Dict[str, float] = {}
        feature_names = self.feature_names or [
            f"feature_{i}" for i in range(len(shap_array))
        ]

        for name, val in zip(feature_names, shap_array):
            pct = round(float(val / abs_sum) * 100.0, 2)
            contributions[name] = pct

        # Sort by absolute contribution descending
        contributions = dict(
            sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)
        )
        return contributions

    # ------------------------------------------------------------------
    # Health status logic
    # ------------------------------------------------------------------
    @staticmethod
    def _determine_health_status(
        anomaly_detected: bool, predicted_rul: float
    ) -> str:
        """
        Map anomaly flag + predicted RUL into a tri-level health status.

        Returns
        -------
        str
            One of ``HEALTHY``, ``ADVISORY``, ``CRITICAL``.
        """
        if anomaly_detected or predicted_rul < RUL_CRITICAL_THRESHOLD:
            return "CRITICAL"
        elif predicted_rul < RUL_ADVISORY_THRESHOLD:
            return "ADVISORY"
        return "HEALTHY"

    # ------------------------------------------------------------------
    # Feature alignment
    # ------------------------------------------------------------------
    def _align_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure the DataFrame columns match the training feature order.
        Missing columns are zero-filled; extra columns are dropped.
        """
        if self.feature_names is None:
            return X

        for col in self.feature_names:
            if col not in X.columns:
                X[col] = 0.0

        return X[self.feature_names]

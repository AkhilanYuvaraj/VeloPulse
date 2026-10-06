"""
VeloPulseAI — Training Pipeline.

Orchestrates data loading, preprocessing, and training for:
  • Stage 1 — Isolation Forest anomaly detector
  • Stage 2 — XGBoost Remaining Useful Life (RUL) regressor

Trained model artifacts are serialised to ``models/`` as ``.joblib`` files.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from data_loader import AutomotiveDataLoader, ML_FEATURE_COLUMNS, ENGINEERED_FEATURES

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-28s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("velopulse.train_pipeline")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MODEL_DIR = Path("models")
ANOMALY_MODEL_PATH = MODEL_DIR / "anomaly_iforest.joblib"
RUL_MODEL_PATH = MODEL_DIR / "rul_xgb.joblib"
SCALER_PATH = MODEL_DIR / "feature_scaler.joblib"
FEATURE_NAMES_PATH = MODEL_DIR / "feature_names.joblib"

ALL_FEATURES = ML_FEATURE_COLUMNS + ENGINEERED_FEATURES


class TrainingPipeline:
    """End-to-end training pipeline for VeloPulseAI models."""

    def __init__(
        self,
        csv_path: str,
        test_size: float = 0.2,
        random_state: int = 42,
        contamination: float = 0.05,
        xgb_n_estimators: int = 300,
        xgb_max_depth: int = 6,
        xgb_learning_rate: float = 0.08,
    ) -> None:
        self.csv_path = csv_path
        self.test_size = test_size
        self.random_state = random_state

        # Stage 1 hyper-parameters
        self.contamination = contamination

        # Stage 2 hyper-parameters
        self.xgb_n_estimators = xgb_n_estimators
        self.xgb_max_depth = xgb_max_depth
        self.xgb_learning_rate = xgb_learning_rate

        self.loader = AutomotiveDataLoader(window_size=30)
        self.scaler = StandardScaler()

        self.anomaly_model: IsolationForest = None  # type: ignore[assignment]
        self.rul_model: XGBRegressor = None  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Data preparation
    # ------------------------------------------------------------------
    def prepare_data(self) -> Tuple[pd.DataFrame, pd.Series]:
        """Load CSV, engineer features, and return (X, y)."""
        logger.info("=== Data Preparation ===")
        df = self.loader.load_csv(self.csv_path)
        X = self.loader.get_feature_matrix(df)
        y = self.loader.get_target(df)

        # Drop rows where target is NaN 
        valid_mask = y.notna()
        X = X.loc[valid_mask].reset_index(drop=True)
        y = y.loc[valid_mask].reset_index(drop=True)

        logger.info("Feature matrix shape: %s", X.shape)
        logger.info("Target vector shape:  %s", y.shape)
        logger.info("Feature columns: %s", list(X.columns))
        return X, y

    # ------------------------------------------------------------------
    # Stage 1 — Isolation Forest
    # ------------------------------------------------------------------
    def train_anomaly_detector(self, X_train: pd.DataFrame) -> IsolationForest:
        """
        Train an Isolation Forest on **normal** vehicle operations to learn
        the nominal operating envelope.

        Parameters
        ----------
        X_train : pd.DataFrame
            Scaled training feature matrix.

        Returns
        -------
        IsolationForest
            Fitted anomaly detection model.
        """
        logger.info("=== Stage 1: Isolation Forest Anomaly Detector ===")
        self.anomaly_model = IsolationForest(
            n_estimators=200,
            contamination=self.contamination,
            max_samples="auto",
            random_state=self.random_state,
            n_jobs=-1,
        )
        self.anomaly_model.fit(X_train)

        # Evaluate on training data
        preds = self.anomaly_model.predict(X_train)
        n_anomalies = int((preds == -1).sum())
        logger.info(
            "Anomaly detector fitted — detected %d anomalies in %d training samples (%.2f%%)",
            n_anomalies,
            len(X_train),
            100.0 * n_anomalies / len(X_train),
        )
        return self.anomaly_model

    # ------------------------------------------------------------------
    # Stage 2 — XGBoost RUL Regressor
    # ------------------------------------------------------------------
    def train_rul_regressor(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
    ) -> XGBRegressor:
        """
        Train an XGBoost regressor to predict Remaining Useful Life (km).

        Parameters
        ----------
        X_train, y_train : training data
        X_test, y_test   : held-out test data

        Returns
        -------
        XGBRegressor
            Fitted RUL regression model.
        """
        logger.info("=== Stage 2: XGBoost RUL Regressor ===")
        self.rul_model = XGBRegressor(
            n_estimators=self.xgb_n_estimators,
            max_depth=self.xgb_max_depth,
            learning_rate=self.xgb_learning_rate,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_alpha=0.1,
            reg_lambda=1.0,
            objective="reg:squarederror",
            random_state=self.random_state,
            n_jobs=-1,
        )
        self.rul_model.fit(
            X_train,
            y_train,
            eval_set=[(X_test, y_test)],
            verbose=False,
        )

        # Evaluate
        y_pred = self.rul_model.predict(X_test)
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        mae = float(mean_absolute_error(y_test, y_pred))
        r2 = float(r2_score(y_test, y_pred))

        logger.info("RUL Model Evaluation on Test Set:")
        logger.info("  RMSE : %.4f km", rmse)
        logger.info("  MAE  : %.4f km", mae)
        logger.info("  R²   : %.4f", r2)

        return self.rul_model

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Execute the full training pipeline and persist model artifacts."""
        X, y = self.prepare_data()

        # Scale features
        X_scaled = pd.DataFrame(
            self.scaler.fit_transform(X),
            columns=X.columns,
            index=X.index,
        )

        # Train / test split
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled,
            y,
            test_size=self.test_size,
            random_state=self.random_state,
        )
        logger.info(
            "Train/test split — train: %d  |  test: %d",
            len(X_train),
            len(X_test),
        )

        # Stage 1
        self.train_anomaly_detector(X_train)

        # Stage 2
        self.train_rul_regressor(X_train, y_train, X_test, y_test)

        # Persist artifacts
        self._save_artifacts(X.columns.tolist())

    # --------------------------------------------------------                    ----------
    # Persistence
    # ------------------------------------------------------------------
    def _save_artifacts(self, feature_names: list) -> None:
        """Serialise trained models, scaler, and feature list to disk."""
        MODEL_DIR.mkdir(parents=True, exist_ok=True)

        joblib.dump(self.anomaly_model, ANOMALY_MODEL_PATH)
        logger.info("Saved anomaly model    → %s", ANOMALY_MODEL_PATH)

        joblib.dump(self.rul_model, RUL_MODEL_PATH)
        logger.info("Saved RUL model        → %s", RUL_MODEL_PATH)

        joblib.dump(self.scaler, SCALER_PATH)
        logger.info("Saved feature scaler   → %s", SCALER_PATH)

        joblib.dump(feature_names, FEATURE_NAMES_PATH)
        logger.info("Saved feature names    → %s", FEATURE_NAMES_PATH)

        logger.info("=== All model artifacts saved to %s/ ===", MODEL_DIR)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="VeloPulseAI — Train predictive maintenance models on automotive telemetry data."
    )
    parser.add_argument(
        "--csv",
        type=str,
        required=True,
        help="Path to the automotive telemetry CSV dataset.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Fraction of data reserved for testing (default: 0.2).",
    )
    parser.add_argument(
        "--contamination",
        type=float,
        default=0.05,
        help="Expected anomaly fraction for Isolation Forest (default: 0.05).",
    )
    parser.add_argument(
        "--n-estimators",
        type=int,
        default=300,
        help="Number of XGBoost boosting rounds (default: 300).",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=6,
        help="Max tree depth for XGBoost (default: 6).",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.08,
        help="XGBoost learning rate (default: 0.08).",
    )
    args = parser.parse_args()

    pipeline = TrainingPipeline(
        csv_path=args.csv,
        test_size=args.test_size,
        contamination=args.contamination,
        xgb_n_estimators=args.n_estimators,
        xgb_max_depth=args.max_depth,
        xgb_learning_rate=args.learning_rate,
    )
    pipeline.run()


if __name__ == "__main__":
    main()

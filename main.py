"""
VeloPulseAI — FastAPI Inference Server.

Exposes production-grade REST API endpoints for real-time predictive
maintenance inference on automotive OBD-II telemetry streams.

Endpoints
---------
  GET  /api/v1/health              — Liveness / readiness probe
  POST /api/v1/predict             — Run 3-stage predictive maintenance pipeline
  GET  /api/v1/hardware/status     — Current Tier 1 connection mode & health
  POST /api/v1/hardware/simulate-fault — Trigger fault injection in simulator
  POST /api/v1/hardware/mode       — Switch Tier 1 hardware mode at runtime
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ml_engine import MLEngine
from tier1_hardware import FaultType, HardwareManager, HardwareMode

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-28s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("velopulse.api")

# ---------------------------------------------------------------------------
# Global instances
# ---------------------------------------------------------------------------
engine = MLEngine()
hardware_manager = HardwareManager()


# ---------------------------------------------------------------------------
# Lifespan: load models at startup, cleanup at shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load trained ML models and start hardware manager at startup."""
    logger.info("VeloPulseAI API server starting — loading models …")
    try:
        engine.load_models()
        logger.info("Models loaded. Server is ready to accept requests.")
    except RuntimeError as exc:
        logger.error("Failed to load models: %s", exc)
        logger.warning(
            "Server started WITHOUT models. "
            "Prediction endpoints will return 503 until models are available."
        )

    # Start Tier 1 hardware manager in simulation mode by default
    try:
        hardware_manager.set_mode(HardwareMode.SIMULATION)
        hardware_manager.start()
        logger.info("Tier 1 hardware manager started in SIMULATION mode.")
    except Exception as exc:
        logger.error("Failed to start hardware manager: %s", exc)

    yield

    # Shutdown
    logger.info("VeloPulseAI API server shutting down.")
    try:
        hardware_manager.stop()
        logger.info("Tier 1 hardware manager stopped.")
    except Exception as exc:
        logger.error("Error stopping hardware manager: %s", exc)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="VeloPulseAI — Predictive Maintenance API",
    description=(
        "AI-based predictive maintenance inference server for smart vehicles. "
        "Accepts raw OBD-II / ECU telemetry and returns anomaly detection, "
        "Remaining Useful Life prediction, and SHAP-based root cause analysis."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for development; restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response Schemas (Pydantic v2)
# ---------------------------------------------------------------------------
class TelemetryPayload(BaseModel):
    """
    Incoming OBD-II / ECU telemetry snapshot.

    Accepts both Kaggle-style and OBD-II PID naming conventions.
    Missing optional fields are filled with safe defaults by the data loader.
    """

    vehicle_id: str = Field(
        default="unknown",
        description="Unique identifier for the vehicle (e.g., VIN or fleet tag).",
    )

    # Kaggle-style fields
    engine_temp_c: Optional[float] = Field(
        default=None, description="Engine block temperature in °C."
    )
    engine_rpm: Optional[float] = Field(
        default=None, description="Engine revolutions per minute."
    )
    coolant_temp_c: Optional[float] = Field(
        default=None, description="Coolant temperature in °C."
    )
    battery_voltage_v: Optional[float] = Field(
        default=None, description="Battery / control module voltage in volts."
    )
    vibration_level: Optional[float] = Field(
        default=None, description="Vibration magnitude (g-force or raw sensor)."
    )
    odometer_reading: Optional[float] = Field(
        default=None, description="Current odometer reading in km."
    )
    engine_load: Optional[float] = Field(
        default=None, description="Calculated engine load (%)."
    )
    vehicle_speed: Optional[float] = Field(
        default=None, description="Vehicle speed in km/h."
    )

    # OBD-II PID names (alternative naming)
    ENGINE_RPM: Optional[float] = Field(
        default=None, description="OBD-II PID: Engine RPM."
    )
    COOLANT_TEMPERATURE: Optional[float] = Field(
        default=None, description="OBD-II PID: Coolant temperature (°C)."
    )
    CONTROL_MODULE_VOLTAGE: Optional[float] = Field(
        default=None, description="OBD-II PID: Control module voltage (V)."
    )
    ENGINE_LOAD: Optional[float] = Field(
        default=None, description="OBD-II PID: Engine load (%)."
    )
    VEHICLE_SPEED: Optional[float] = Field(
        default=None, description="OBD-II PID: Vehicle speed (km/h)."
    )

    model_config = ConfigDict(extra="allow")


class PredictionResponse(BaseModel):
    """Structured prediction response."""

    vehicle_id: str
    anomaly_detected: bool
    anomaly_score: float
    health_status: str
    predicted_rul_km: float
    root_cause_analysis: Dict[str, float]
    inference_time_ms: float


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    models_loaded: bool
    hardware_mode: str
    hardware_connected: bool
    version: str


class BatchPredictionRequest(BaseModel):
    """Batch prediction request wrapping multiple telemetry payloads."""

    payloads: List[TelemetryPayload]


class BatchPredictionResponse(BaseModel):
    """Batch prediction response."""

    predictions: List[PredictionResponse]
    total_inference_time_ms: float


class HardwareStatusResponse(BaseModel):
    """Tier 1 hardware connection status response."""

    mode: str
    connected: bool
    port_or_address: Optional[str]
    last_reading_timestamp: Optional[str]
    frames_received: int
    errors_count: int
    uptime_seconds: float
    latest_frame: Optional[Dict[str, Any]] = None


class FaultInjectionRequest(BaseModel):
    """Fault injection request for the Tier 1 simulator."""

    fault_type: str = Field(
        ...,
        description=(
            "Type of fault to inject. Options: 'voltage_drop', "
            "'thermal_runaway', 'bearing_vibration', 'engine_misfire', 'combined'."
        ),
    )
    severity: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Fault severity from 0.0 (mild) to 1.0 (extreme).",
    )
    duration_seconds: float = Field(
        default=15.0,
        gt=0.0,
        le=300.0,
        description="How long the fault persists in seconds.",
    )


class FaultInjectionResponse(BaseModel):
    """Fault injection response."""

    success: bool
    message: str
    fault_type: str
    severity: float
    duration_seconds: float


class HardwareModeRequest(BaseModel):
    """Request to switch Tier 1 hardware mode."""

    mode: str = Field(
        ...,
        description="Target mode: 'SERIAL', 'BLUETOOTH_OBD', 'SIMULATION'.",
    )
    port: Optional[str] = Field(
        default=None,
        description="COM port (for SERIAL) or Bluetooth address (for BLUETOOTH_OBD).",
    )
    baudrate: Optional[int] = Field(
        default=115200,
        description="Baud rate for serial connections.",
    )


# ---------------------------------------------------------------------------
# Middleware: request timing
# ---------------------------------------------------------------------------
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    return response


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health & readiness check",
)
async def health_check() -> HealthResponse:
    """Return server health status, model state, and hardware state."""
    hw_status = hardware_manager.get_status()
    return HealthResponse(
        status="ok" if engine.is_loaded else "degraded",
        models_loaded=engine.is_loaded,
        hardware_mode=hw_status.mode.value if hw_status else "UNKNOWN",
        hardware_connected=hw_status.connected if hw_status else False,
        version="1.0.0",
    )


@app.post(
    "/api/v1/predict",
    response_model=PredictionResponse,
    tags=["Prediction"],
    summary="Single telemetry prediction",
)
async def predict(payload: TelemetryPayload) -> PredictionResponse:
    """
    Accept a single OBD-II telemetry snapshot and return:
    - anomaly detection flag & score
    - predicted Remaining Useful Life (km)
    - health status (HEALTHY / ADVISORY / CRITICAL)
    - SHAP-based root cause analysis with percentage contributions
    """
    if not engine.is_loaded:
        raise HTTPException(
            status_code=503,
            detail=(
                "ML models are not loaded. "
                "Run train_pipeline.py to generate model artifacts, "
                "then restart the server."
            ),
        )

    start = time.perf_counter()

    # Convert Pydantic model to a raw dict for the data loader
    raw_payload = payload.model_dump(exclude_none=True)
    vehicle_id = raw_payload.pop("vehicle_id", "unknown")

    try:
        result = engine.predict(raw_payload, vehicle_id=vehicle_id)
    except Exception as exc:
        logger.exception("Prediction failed for vehicle %s", vehicle_id)
        raise HTTPException(
            status_code=500,
            detail=f"Prediction pipeline error: {exc}",
        ) from exc

    elapsed_ms = (time.perf_counter() - start) * 1000

    return PredictionResponse(
        vehicle_id=result.vehicle_id,
        anomaly_detected=result.anomaly_detected,
        anomaly_score=result.anomaly_score,
        health_status=result.health_status,
        predicted_rul_km=result.predicted_rul_km,
        root_cause_analysis=result.root_cause_analysis,
        inference_time_ms=round(elapsed_ms, 2),
    )


@app.post(
    "/api/v1/predict/batch",
    response_model=BatchPredictionResponse,
    tags=["Prediction"],
    summary="Batch telemetry prediction",
)
async def predict_batch(
    request: BatchPredictionRequest,
) -> BatchPredictionResponse:
    """
    Accept a batch of OBD-II telemetry snapshots and return predictions
    for each payload.
    """
    if not engine.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="ML models are not loaded.",
        )

    start = time.perf_counter()
    predictions: List[PredictionResponse] = []

    for payload in request.payloads:
        raw = payload.model_dump(exclude_none=True)
        vid = raw.pop("vehicle_id", "unknown")

        try:
            result = engine.predict(raw, vehicle_id=vid)
        except Exception as exc:
            logger.exception("Batch prediction failed for vehicle %s", vid)
            raise HTTPException(
                status_code=500,
                detail=f"Prediction failed for {vid}: {exc}",
            ) from exc

        predictions.append(
            PredictionResponse(
                vehicle_id=result.vehicle_id,
                anomaly_detected=result.anomaly_detected,
                anomaly_score=result.anomaly_score,
                health_status=result.health_status,
                predicted_rul_km=result.predicted_rul_km,
                root_cause_analysis=result.root_cause_analysis,
                inference_time_ms=0.0,  # batch timing at top level
            )
        )

    total_ms = (time.perf_counter() - start) * 1000

    return BatchPredictionResponse(
        predictions=predictions,
        total_inference_time_ms=round(total_ms, 2),
    )


# ---------------------------------------------------------------------------
# Hardware Endpoints (Tier 1)
# ---------------------------------------------------------------------------
@app.get(
    "/api/v1/hardware/status",
    response_model=HardwareStatusResponse,
    tags=["Hardware"],
    summary="Current Tier 1 connection mode & health",
)
async def hardware_status() -> HardwareStatusResponse:
    """Display current Tier 1 connection mode and connection health."""
    status = hardware_manager.get_status()
    latest = hardware_manager.get_latest_frame()

    return HardwareStatusResponse(
        mode=status.mode.value,
        connected=status.connected,
        port_or_address=status.port_or_address,
        last_reading_timestamp=status.last_reading_timestamp,
        frames_received=status.frames_received,
        errors_count=status.errors_count,
        uptime_seconds=status.uptime_seconds,
        latest_frame=latest,
    )


@app.post(
    "/api/v1/hardware/simulate-fault",
    response_model=FaultInjectionResponse,
    tags=["Hardware"],
    summary="Trigger fault injection in the Tier 1 simulator",
)
async def simulate_fault(
    request: FaultInjectionRequest,
) -> FaultInjectionResponse:
    """
    Trigger fault injection states in the Tier 1 simulator during
    live presentations. Only works when hardware mode is SIMULATION.
    """
    status = hardware_manager.get_status()
    if status.mode != HardwareMode.SIMULATION:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Fault injection is only available in SIMULATION mode. "
                f"Current mode: {status.mode.value}"
            ),
        )

    # Validate fault type
    try:
        fault = FaultType(request.fault_type)
    except ValueError:
        valid_types = [ft.value for ft in FaultType]
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid fault_type '{request.fault_type}'. "
                f"Valid options: {valid_types}"
            ),
        )

    try:
        hardware_manager.inject_fault(
            fault_type=fault,
            severity=request.severity,
            duration_seconds=request.duration_seconds,
        )
    except Exception as exc:
        logger.exception("Fault injection failed")
        raise HTTPException(
            status_code=500,
            detail=f"Fault injection error: {exc}",
        ) from exc

    logger.info(
        "Fault injected — type=%s severity=%.2f duration=%.1fs",
        fault.value,
        request.severity,
        request.duration_seconds,
    )

    return FaultInjectionResponse(
        success=True,
        message=f"Fault '{fault.value}' injected successfully.",
        fault_type=fault.value,
        severity=request.severity,
        duration_seconds=request.duration_seconds,
    )


@app.post(
    "/api/v1/hardware/mode",
    tags=["Hardware"],
    summary="Switch Tier 1 hardware mode",
)
async def switch_hardware_mode(request: HardwareModeRequest) -> Dict[str, Any]:
    """
    Switch the Tier 1 hardware manager to a different mode at runtime.
    Valid modes: SERIAL, BLUETOOTH_OBD, SIMULATION.
    """
    try:
        target_mode = HardwareMode(request.mode.upper())
    except ValueError:
        valid_modes = [m.value for m in HardwareMode]
        raise HTTPException(
            status_code=422,
            detail=f"Invalid mode '{request.mode}'. Valid modes: {valid_modes}",
        )

    try:
        hardware_manager.stop()
        hardware_manager.set_mode(
            mode=target_mode,
            port=request.port,
            baudrate=request.baudrate,
        )
        hardware_manager.start()
    except Exception as exc:
        logger.exception("Hardware mode switch failed")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to switch hardware mode: {exc}",
        ) from exc

    logger.info("Hardware mode switched to %s", target_mode.value)
    return {
        "success": True,
        "mode": target_mode.value,
        "message": f"Hardware mode switched to {target_mode.value}.",
    }


@app.post(
    "/api/v1/hardware/predict-live",
    response_model=PredictionResponse,
    tags=["Hardware", "Prediction"],
    summary="Run prediction on live Tier 1 hardware frame",
)
async def predict_live() -> PredictionResponse:
    """
    Read the latest frame from the Tier 1 hardware manager and run
    it through the full 3-stage ML prediction pipeline.
    """
    if not engine.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="ML models are not loaded.",
        )

    frame = hardware_manager.get_latest_frame()
    if frame is None:
        raise HTTPException(
            status_code=503,
            detail="No telemetry frame available from hardware. Check hardware connection.",
        )

    start = time.perf_counter()

    try:
        result = engine.predict(frame, vehicle_id="hardware_live")
    except Exception as exc:
        logger.exception("Live hardware prediction failed")
        raise HTTPException(
            status_code=500,
            detail=f"Prediction pipeline error: {exc}",
        ) from exc

    elapsed_ms = (time.perf_counter() - start) * 1000

    return PredictionResponse(
        vehicle_id=result.vehicle_id,
        anomaly_detected=result.anomaly_detected,
        anomaly_score=result.anomaly_score,
        health_status=result.health_status,
        predicted_rul_km=result.predicted_rul_km,
        root_cause_analysis=result.root_cause_analysis,
        inference_time_ms=round(elapsed_ms, 2),
    )


# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
async def root():
    return JSONResponse(
        content={
            "service": "VeloPulseAI Predictive Maintenance API",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/v1/health",
            "hardware_status": "/api/v1/hardware/status",
        }
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )

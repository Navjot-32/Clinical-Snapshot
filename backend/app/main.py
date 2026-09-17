from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core import config
from app.core.logging import configure_logging, logger
from app.routers import patient_summary
from app.services.bundle_loader import get_cached_bundle


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    bundle = get_cached_bundle(config.BUNDLE_PATH)
    logger.info(
        "bundle_loaded",
        extra={
            "path": str(config.BUNDLE_PATH),
            "resources": len(bundle.index),
            "unparsed": len(bundle.failures),
        },
    )
    yield


app = FastAPI(title="Clinical Snapshot API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.FRONTEND_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(patient_summary.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fail loudly rather than quietly.

    A clinical view must never let a server fault look like a patient with no
    recorded problems. The response is an explicit failure the frontend renders as
    an error; the cause goes to the log, not to the client.
    """
    logger.error("unhandled_error", extra={"path": request.url.path}, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "summary_unavailable",
            "message": "The patient summary could not be generated. This is a failure, not an empty record.",
        },
    )


@app.get("/health")
def health() -> dict:
    """Liveness: the process is up."""
    return {"status": "ok", "bundle_present": config.BUNDLE_PATH.exists()}


@app.get("/ready")
def ready() -> JSONResponse:
    """Readiness: the bundle parsed and a patient is actually resolvable."""
    bundle = get_cached_bundle(config.BUNDLE_PATH)
    ok = bool(bundle.patients)
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "status": "ready" if ok else "not-ready",
            "resources": len(bundle.index),
            "unparsed": len(bundle.failures),
        },
    )

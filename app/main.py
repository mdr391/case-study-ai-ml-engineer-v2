"""FastAPI entrypoint for the scheduling engine.

This module is the *transport adapter*: it validates input, delegates to the
pure scheduler workflow, and shapes errors. No scheduling logic lives here.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.data import get_slots
from app.models import ErrorDetail, SearchRequest, SearchResponse
from app.scheduler import search_slots

app = FastAPI(title="Scheduling Engine", version="0.1.0")


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Reshape verbose validation errors into a compact, actionable ErrorDetail.

    Covers both schema errors and the semantic conflict checks in the models
    (e.g. end <= start, duration exceeds the window). Status stays 422, the
    conventional code for request-validation failures.
    """
    first = exc.errors()[0] if exc.errors() else {}
    loc = [str(part) for part in first.get("loc", ()) if part != "body"]
    detail = ErrorDetail(
        error="invalid_request",
        message=first.get("msg", "Request failed validation."),
        field=".".join(loc) or None,
    )
    return JSONResponse(status_code=422, content=detail.model_dump())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/schedule/search", response_model=SearchResponse)
def schedule_search(request: SearchRequest) -> SearchResponse:
    """Search bookable slots and return matches plus a diagnostics trace."""
    return search_slots(request, get_slots())

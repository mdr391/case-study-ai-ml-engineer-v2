"""Minimal FastAPI entrypoint for the case study."""

from fastapi import FastAPI

app = FastAPI(title="Case Study Starter", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

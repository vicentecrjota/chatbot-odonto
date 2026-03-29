"""Ponto de entrada da API (FastAPI)."""

from fastapi import FastAPI

app = FastAPI(title="chatbot-odonto", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

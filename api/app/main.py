import uvicorn
from fastapi import FastAPI

app = FastAPI(title="GSPS Challenge API")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Hello World"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


def start() -> None:
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

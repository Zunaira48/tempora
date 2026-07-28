from fastapi import FastAPI

app = FastAPI(title="Tempora API")


@app.get("/health")
def health_check():
    return {"status": "ok"}
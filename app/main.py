from fastapi import FastAPI

app = FastAPI(title="Struct My Data")


@app.get("/health")
async def health():
    return {"status": "ok"}

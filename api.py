from app.main import app


if __name__ == "__main__":
    import os

    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "11113"))
    uvicorn.run("api:app", host=host, port=port, reload=True)

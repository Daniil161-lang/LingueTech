import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI()

# Монтируем статику
app.mount("/", StaticFiles(directory=BASE_DIR / "static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse(BASE_DIR / "static" / "index.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))  # Важно для Render!
    uvicorn.run(app, host="0.0.0.0", port=port)
    

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import os

# Получаем абсолютный путь к корневой директории
BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()

# Правильное монтирование статики - убедитесь что путь верный!
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

@app.get("/")
async def read_index():
    # Убедитесь что файл существует по этому пути
    file_path = BASE_DIR / "static" / "index.html"
    print(f"Looking for file at: {file_path}")  # Это поможет в диагностике
    print(f"File exists: {file_path.exists()}")  # Проверить существование файла
    return FileResponse(file_path)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

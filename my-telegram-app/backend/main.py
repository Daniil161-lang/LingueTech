from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn
import os

app = FastAPI()

# Раздаем статичные файлы фронтенда (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Корневой маршрут отдает нашу HTML-страницу
@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

# API endpoint для принятия данных от фронтенда
@app.post("/api/save_data")
async def save_user_data(request: Request):
    try:
        data = await request.json()
        # Здесь вы можете сохранить данные в базу данных
        # Например: save_to_db(data)
        print("Получены данные:", data)
        return JSONResponse({"status": "success", "message": "Данные сохранены"})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
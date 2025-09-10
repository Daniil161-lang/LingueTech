// Инициализация Telegram Web App
let tg = window.Telegram.WebApp;
tg.expand(); // Раскрываем приложение на весь экран
tg.enableClosingConfirmation(); // Включаем подтверждение закрытия

// Функция для отправки данных
function sendData() {
    const userData = {
        weight: document.getElementById('weight').value,
        // ... соберите данные других полей
    };

    // 1. Вариант: Отправить данные боту (они придут в виде сообщения)
    tg.sendData(JSON.stringify(userData));
    tg.close(); // Закрыть приложение

    // 2. Вариант: Отправить данные напрямую на ваш бэкенд
    fetch('https://your-backend.com/api/save_data', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userData)
    })
    .then(response => response.json())
    .then(data => {
        tg.showPopup({ title: "Успех!", message: "Данные сохранены" });
    })
    .catch(error => {
        tg.showPopup({ title: "Ошибка!", message: "Что-то пошло не так" });
    });
}

// Обработчик главной кнопки бота (если она видна)
tg.MainButton.setText("Сохранить")
    .show()
    .onClick(sendData);
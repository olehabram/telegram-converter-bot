web: gunicorn currency_transfer_bot.main_bot:flask_app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 --log-level info
```
**Пояснення `Procfile`:**

* `web:`: Оголошує процес типу "веб", який буде приймати HTTP-запити.
* `gunicorn`: Використовує Gunicorn як WSGI сервер для запуску Flask.
* `currency_transfer_bot.main_bot:flask_app`: Вказує Gunicorn знайти об'єкт `flask_app` (наш екземпляр Flask) у файлі `main_bot.py`, який знаходиться в директорії `currency_transfer_bot`. **Важливо:** Переконайся, що шлях `currency_transfer_bot.main_bot` відповідає структурі твого проекту. Якщо `main_bot.py` лежить в корені, команда буде `gunicorn main_bot:flask_app ...`.
* `--bind 0.0.0.0:$PORT`: Прив'язує Gunicorn до всіх мережевих інтерфейсів (`0.0.0.0`) і до порту, вказаного у змінній середовища `PORT` (яку надасть Render/Railway).
* `--workers 1 --threads 4`: Конфігурація Gunicorn (можна налаштувати). 1 воркер, 4 потоки.
* `--timeout 120`: Збільшує час очікування відповіді (у секундах).
* `--log-level info`: Встановлює рівень логування для Gunico
# MISIS‑2GIS — Wearables Routes MVP

MVP сервиса для бегунов/велосипедистов на базе FastAPI и 2ГИС:
- Создание маршрутов по кликам на карте с предпросмотром от 2ГИС Routing API.
- Запись трека из браузера телефона/ноутбука (GPS) как ломаной без вызова Routing.
- Просмотр сохранённых маршрутов, теги, «загруженность» и рейтинг.

> ⚠️ Для записи геолокации в браузере требуется HTTPS. Для демо проще всего использовать ngrok (см. ниже).

---

## Стек
- Backend: FastAPI, Pydantic v2, SQLAlchemy 2, httpx, SQLite
- Frontend: простые HTML страницы + 2GIS MapGL JS API
- Маршрутизация: 2ГИС Routing API (/routing/7.0.0/global)
- Сервер: Uvicorn

---

## Быстрый старт (Windows)

1) Создай и активируй окружение
cd C:\Users\<you>\Documents\2gis
python -m venv .venv
.\.venv\Scripts\Activate.ps1

2) Установи зависимости
pip install -r requirements.txt


4) Запусти сервер
```powershell
python -m uvicorn ui:app --reload --host 127.0.0.1 --port 8000

5) Открой в браузере:
- Список:      http://127.0.0.1:8000/ui
- Создание:    http://127.0.0.1:8000/ui/create
- Запись:      http://127.0.0.1:8000/ui/record
- Healthcheck: http://127.0.0.1:8000/health

База routes.db появится автоматически рядом с файлами.

---

## Доступ с телефона/часов в одной Wi‑Fi сети

Геолокация на странице записи (/ui/record) требует HTTPS.

Открой на телефоне ссылку вида `https://<random>.ngrok-free.app/ui`  
(для записи — `.../ui/record`).

### локальный HTTPS (самоподписанный сертификат)
```powershell
ipconfig                         # смотри IP, например 192.168.X.X
choco install mkcert
mkcert -install
mkcert 192.168.X.X localhost 127.0.0.1

python -m uvicorn ui:app --host 0.0.0.0 --port 8000 ^
  --ssl-certfile 192.168.X.X+2.pem ^
  --ssl-keyfile  192.168.X.X+2-key.pem
Открой: https://192.168.X.X:8000/ui (возможно, нужно доверить локальный CA на телефоне).

### (необязательно) Разрешить порт 8000 в брандмауэре
Открой PowerShell от администратора:
New-NetFirewallRule -DisplayName "uvicorn-8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow

---

## Что есть в UI
- /ui — список маршрутов (имя, длина, теги, загруженность, рейтинг)
- /ui/create — конструктор: кликай 2+ точек, можно менять порядок, теги (преднабор + свои)
- /ui/record — запись трека с устройства (GPS) как ломаная; после «Стоп» — сохранить как маршрут
- /ui/route/{id} — просмотр маршрута, длина, теги, рейтинг, загруженность

> В конструкторе превью строится через 2ГИС Routing API: сегменты между соседними точками склеиваются. Если API не вернул сегмент — используется прямая, чтобы карта не «рвалась».

# Analytics Dashboard (Flask + SQLite)

Готовый сайт для просмотра `analytics.db` (пользователи, события) с поиском, фильтрами и диаграммами.

## Как запустить

1) Установите зависимости (желательно в виртуальном окружении):
```
pip install -r requirements.txt
```

2) Скопируйте `.env.example` в `.env` и при необходимости измените путь к базе:
```
cp .env.example .env
# DATABASE_URL=sqlite:///путь/к/analytics.db
```

3) Запуск:
```
python app.py
```
Откройте http://localhost:8000

## Что умеет сайт
- **/users** — поиск по `id`, `@username`, имени/фамилии; пагинация.
- **/events** — фильтры по типу (`message`, `command`, `callback`), `user_id`, диапазону дат/времени и поиску по тексту/команде/callback; пагинация.
- **/charts** — диаграммы активности (по дням, по типам, топ команд, топ пользователей).

## Требуемая схема БД
Сайт ожидает следующие таблицы:

```
CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY,
  username TEXT,
  first_name TEXT,
  last_name TEXT,
  language_code TEXT,
  is_bot INTEGER DEFAULT 0,
  added_at TEXT,
  last_seen TEXT
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  event_type TEXT,        -- 'message' | 'command' | 'callback'
  chat_id INTEGER,
  chat_type TEXT,
  message_id INTEGER,
  text TEXT,
  command TEXT,
  callback_data TEXT,
  raw_json TEXT,
  created_at TEXT,
  FOREIGN KEY (user_id) REFERENCES users (user_id)
);
```
Если у вас уже используется иная схема — подправьте SQL-запросы в `app.py`.

import os
import base64
import hmac
from typing import Optional
from datetime import datetime, timedelta, UTC
import sys
from pathlib import Path
import pytz
from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from pathlib import Path
from werkzeug.middleware.proxy_fix import ProxyFix

BASE_DIR = Path(__file__).resolve().parent.parent  # .../PythonProject1
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import TIMEZONE

# Загружаем .env из рядом лежащего файла
load_dotenv(Path(__file__).resolve().parent / ".env")


def create_app():
    app = Flask(__name__)
    # корректная работа за обратным прокси (Apache/Nginx)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key")

    # База аналитики (sqlite)
    base_dir = Path(__file__).resolve().parent.parent
    db_path = (base_dir / "analytics.db").as_posix()
    db_url = f"sqlite:///{db_path}"
    print(">>> FORCED DB URL:", db_url)

    engine = create_engine(db_url, future=True)

    # ---------- АВТОИНИЦИАЛИЗАЦИЯ СХЕМЫ ----------
    with engine.begin() as conn:
        conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS users (
          user_id INTEGER PRIMARY KEY,
          username TEXT,
          first_name TEXT,
          last_name TEXT,
          language_code TEXT,
          is_bot INTEGER,
          added_at TEXT,
          last_seen TEXT
        );
        """)
        conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          event_type TEXT NOT NULL,
          chat_id INTEGER,
          chat_type TEXT,
          message_id INTEGER,
          text TEXT,
          command TEXT,
          callback_data TEXT,
          raw_json TEXT,
          created_at TEXT NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
        """)
        # 🔽 обновлённая таблица: храним и user_id, и username
        conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS admins (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER UNIQUE,
          username TEXT,
          added_at TEXT NOT NULL
        );
        """)

    # ---------- BASIC AUTH ----------
    DASH_USER = os.getenv("DASH_USER", "admin")
    DASH_PASS = os.getenv("DASH_PASS", "change-me")

    def _check_basic_auth(auth_header: Optional[str]) -> bool:
        if not auth_header:
            return False
        try:
            scheme, b64 = auth_header.split(" ", 1)
            if scheme.lower() != "basic":
                return False
            userpass = base64.b64decode(b64.strip()).decode("utf-8")
            username, password = userpass.split(":", 1)
            return (
                hmac.compare_digest(username, DASH_USER)
                and hmac.compare_digest(password, DASH_PASS)
            )
        except Exception:
            return False

    @app.before_request
    def _require_basic_auth():
        # health-check доступен без логина (например для мониторинга)
        if request.path.startswith("/healthz"):
            return
        if not _check_basic_auth(request.headers.get("Authorization")):
            resp = jsonify({"error": "auth required"})
            resp.status_code = 401
            resp.headers["WWW-Authenticate"] = 'Basic realm="BelguDz Analytics"'
            return resp

    # ---------- HELPERS ----------
    def to_int(v, default):
        try:
            return int(v)
        except Exception:
            return default

    @app.context_processor
    def inject_now():
        tz = pytz.timezone(TIMEZONE)  # ← используем значение из config.py
        return {"now": datetime.now(tz)}

    # ---------- ROUTES: HOME / USERS / EVENTS / CHARTS ----------
    @app.route("/")
    def home():
        try:
            with engine.begin() as conn:
                users_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one_or_none() or 0
                events_count = conn.execute(text("SELECT COUNT(*) FROM events")).scalar_one_or_none() or 0
                last_event = conn.execute(text(
                    "SELECT created_at FROM events ORDER BY datetime(created_at) DESC, id DESC LIMIT 1"
                )).scalar_one_or_none()
        except Exception:
            users_count, events_count, last_event = 0, 0, None
        return render_template("home.html", users_count=users_count,
                               events_count=events_count, last_event=last_event)

    @app.route("/users")
    def users():
        q = (request.args.get("q") or "").strip()
        page = to_int(request.args.get("page"), 1)
        per_page = min(max(to_int(request.args.get("per_page"), 25), 5), 200)
        offset = (page - 1) * per_page

        where, params = "", {}
        if q:
            where = ("WHERE CAST(user_id AS TEXT) LIKE :q OR IFNULL(username,'') LIKE :q "
                     "OR IFNULL(first_name,'') LIKE :q OR IFNULL(last_name,'') LIKE :q")
            params["q"] = f"%{q}%"

        with engine.begin() as conn:
            total = conn.execute(text(f"SELECT COUNT(*) FROM users {where}"), params).scalar_one()
            rows = conn.execute(text(f"""
                SELECT user_id, username, first_name, last_name, language_code, is_bot,
                       added_at, last_seen
                FROM users
                {where}
                ORDER BY COALESCE(last_seen, added_at) DESC
                LIMIT :limit OFFSET :offset
            """), {**params, "limit": per_page, "offset": offset}).fetchall()

        return render_template("users.html", rows=rows, q=q, page=page,
                               per_page=per_page, total=total)

    @app.route("/events")
    def events():
        q = (request.args.get("q") or "").strip()
        etype = (request.args.get("type") or "").strip()
        user_id = (request.args.get("user_id") or "").strip()
        date_from = (request.args.get("from") or "").strip()
        date_to = (request.args.get("to") or "").strip()

        page = to_int(request.args.get("page"), 1)
        per_page = min(max(to_int(request.args.get("per_page"), 25), 5), 200)
        offset = (page - 1) * per_page

        clauses, params = [], {}
        if q:
            clauses.append("(IFNULL(text,'') LIKE :q OR IFNULL(command,'') LIKE :q OR IFNULL(callback_data,'') LIKE :q)")
            params["q"] = f"%{q}%"
        if etype:
            clauses.append("event_type = :etype")
            params["etype"] = etype
        if user_id:
            clauses.append("user_id = :uid")
            params["uid"] = user_id
        if date_from:
            clauses.append("datetime(created_at) >= datetime(:from)")
            params["from"] = date_from
        if date_to:
            clauses.append("datetime(created_at) <= datetime(:to)")
            params["to"] = date_to
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        with engine.begin() as conn:
            total = conn.execute(text(f"SELECT COUNT(*) FROM events {where}"), params).scalar_one()
            rows = conn.execute(text(f"""
                SELECT id, user_id, event_type, chat_id, chat_type, message_id,
                       text, command, callback_data, created_at
                FROM events
                {where}
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT :limit OFFSET :offset
            """), {**params, "limit": per_page, "offset": offset}).fetchall()

        return render_template("events.html", rows=rows, q=q, etype=etype,
                               user_id=user_id, date_from=date_from,
                               date_to=date_to, page=page,
                               per_page=per_page, total=total)

    @app.route("/charts")
    def charts():
        return render_template("charts.html")

    @app.get("/api/charts/events/daily")
    def api_events_daily():
        days = to_int(request.args.get("days"), 30)
        since = datetime.now(UTC) - timedelta(days=days)
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT strftime('%Y-%m-%d', datetime(created_at)) AS d, COUNT(*) AS c
                FROM events
                WHERE datetime(created_at) >= datetime(:since)
                GROUP BY d
                ORDER BY d ASC
            """), {"since": since.isoformat()})
            rows = result.mappings().all()
        return jsonify([{"date": r.get("d"), "count": int(r.get("c") or 0)} for r in rows])

    @app.get("/api/charts/events/by_type")
    def api_events_by_type():
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT COALESCE(event_type, 'unknown') AS type, COUNT(*) AS count
                FROM events
                GROUP BY event_type
                ORDER BY count DESC
            """))
            rows = result.mappings().all()
        return jsonify([{"type": r.get("type"), "count": int(r.get("count") or 0)} for r in rows])

    @app.get("/api/charts/top/commands")
    def api_top_commands():
        limit = to_int(request.args.get("limit"), 10)
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT command AS cmd, COUNT(*) AS c
                FROM events
                WHERE command IS NOT NULL AND COMMAND <> ''
                GROUP BY command
                ORDER BY c DESC
                LIMIT :limit
            """), {"limit": limit})
            rows = result.mappings().all()
        return jsonify([{"command": r.get("cmd"), "count": int(r.get("c") or 0)} for r in rows])

    @app.get("/api/charts/top/users")
    def api_top_users():
        limit = to_int(request.args.get("limit"), 10)
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT e.user_id AS uid, COALESCE(u.username, '') AS username,
                       COALESCE(u.first_name,'') AS first_name,
                       COALESCE(u.last_name,'') AS last_name,
                       COUNT(*) AS c
                FROM events e
                LEFT JOIN users u ON u.user_id = e.user_id
                GROUP BY e.user_id
                ORDER BY c DESC
                LIMIT :limit
            """), {"limit": limit})
            rows = result.mappings().all()

        out = []
        for r in rows:
            uid = r.get("uid")
            username = r.get("username") or ""
            first_name = r.get("first_name") or ""
            last_name = r.get("last_name") or ""
            label = username or (f"{first_name} {last_name}".strip()) or str(uid)
            out.append({"user_id": uid, "label": label, "count": int(r.get("c") or 0)})
        return jsonify(out)

    # ---------- НОВОЕ: ВКЛАДКА / API ДЛЯ АДМИНОВ ----------
    @app.route("/admins", methods=["GET", "POST"])
    def admins():
        """Веб-интерфейс управления администраторами (ID + username)"""
        msg, err = None, None

        if request.method == "POST":
            action = (request.form.get("action") or "").strip()
            username = (request.form.get("username") or "").strip().lstrip("@")
            user_id = (request.form.get("user_id") or "").strip()

            try:
                user_id = int(user_id) if user_id else None
            except ValueError:
                user_id = None

            if not user_id or not username:
                err = "Введите и ID, и username (без @)"
            else:
                try:
                    with engine.begin() as conn:
                        if action == "add":
                            conn.execute(
                                text("""
                                   INSERT OR REPLACE INTO admins (user_id, username, added_at)
                                   VALUES (:id, :u, :t)
                                   """),
                                {"id": user_id, "u": username, "t": datetime.now(UTC).isoformat()}
                            )
                            msg = f"✅ Добавлен админ @{username} (ID: {user_id})"
                        elif action == "delete":
                            res = conn.execute(
                                text("DELETE FROM admins WHERE user_id=:id OR username=:u"),
                                {"id": user_id, "u": username}
                            )
                            if res.rowcount:
                                msg = f"🗑 Админ @{username} (ID: {user_id}) удалён"
                            else:
                                err = "Не найден такой админ"
                        else:
                            err = "Неизвестное действие"
                except Exception as e:
                    err = f"Ошибка: {e}"

        with engine.begin() as conn:
            rows = conn.execute(text("""
                SELECT user_id, username, added_at
                FROM admins
                ORDER BY datetime(added_at) DESC, username ASC
            """)).fetchall()

        return render_template("admins.html", rows=rows, msg=msg, err=err)

    @app.get("/api/admins")
    def api_admins_list():
        with engine.begin() as conn:
            rows = conn.execute(text("SELECT user_id, username, added_at FROM admins ORDER BY username")).fetchall()
        return jsonify([{"user_id": r.user_id, "username": r.username, "added_at": r.added_at} for r in rows])

    @app.post("/api/admins")
    def api_admins_add():
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip().lstrip("@")
        user_id = data.get("user_id")
        try:
            user_id = int(user_id)
        except Exception:
            return jsonify({"error": "user_id (int) and username required"}), 400
        if not username:
            return jsonify({"error": "user_id (int) and username required"}), 400
        with engine.begin() as conn:
            conn.execute(
                text("INSERT OR REPLACE INTO admins (user_id, username, added_at) VALUES (:id, :u, :t)"),
                {"id": user_id, "u": username, "t": datetime.now(UTC).isoformat()}
            )
        return jsonify({"ok": True, "user_id": user_id, "username": username})

    @app.delete("/api/admins")
    def api_admins_delete():
        username = (request.args.get("username") or "").strip().lstrip("@")
        user_id = request.args.get("user_id")
        id_val = None
        if user_id is not None:
            try:
                id_val = int(user_id)
            except Exception:
                return jsonify({"error": "user_id must be int"}), 400
        if not username and id_val is None:
            return jsonify({"error": "provide user_id or username"}), 400

        with engine.begin() as conn:
            res = conn.execute(
                text("DELETE FROM admins WHERE (:id IS NOT NULL AND user_id=:id) OR (:u <> '' AND username=:u)"),
                {"id": id_val, "u": username or ""}
            )
            if not res.rowcount:
                return jsonify({"error": "not found"}), 404
        return jsonify({"ok": True, "user_id": id_val, "username": username or None})

    # ---------- DEBUG / HEALTH ----------
    @app.get("/debug/tables")
    def debug_tables():
        with engine.begin() as conn:
            tables = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )).fetchall()
            counts = {}
            for (name,) in tables:
                try:
                    c = conn.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar_one()
                except Exception:
                    c = "n/a"
                counts[name] = c
        return jsonify({"tables": [t[0] for t in tables], "counts": counts})

    @app.get("/debug/sample")
    def debug_sample():
        out = {}
        with engine.begin() as conn:
            for t in ("users", "events", "admins"):
                try:
                    rows = conn.execute(text(f"SELECT * FROM {t} LIMIT 3")).fetchall()
                    out[t] = [dict(r._mapping) for r in rows]
                except Exception as e:
                    out[t] = f"error: {e}"
        return jsonify(out)

    @app.get("/healthz")
    def health():
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True}

    return app


def app_factory():
    return create_app()


app = app_factory()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

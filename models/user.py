from flask_login import UserMixin
from utils.db import get_db_connection, get_db_cursor

class User(UserMixin):
    def __init__(self, id, username, password_hash, full_name, is_admin):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.full_name = full_name
        self.is_admin = is_admin

    @classmethod
    def get(cls, user_id):
        try:
            with get_db_connection() as conn:
                with get_db_cursor(conn) as cur:
                    cur.execute("SELECT id, username, password_hash, full_name, is_admin FROM users WHERE id = ?", (user_id,))
                    row = cur.fetchone()
                    if row:
                        return cls(row[0], row[1], row[2], row[3], row[4])
        except Exception as e:
            # ログ出力は省略
            pass
        return None 
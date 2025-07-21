from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, id, username, password_hash, full_name, is_admin):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.full_name = full_name
        self.is_admin = is_admin 
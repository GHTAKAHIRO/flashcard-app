from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, id, username, password_hash=None, full_name=None, is_admin=False):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.full_name = full_name
        self.is_admin = is_admin

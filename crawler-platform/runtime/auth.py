"""统一会话存储：仅保存随机令牌的摘要，支持到期、撤销和登录限速。"""
import hashlib
from contextlib import contextmanager
from pathlib import Path
import secrets
import sqlite3
import time


class SessionStore:
    def __init__(self, directory, ttl=8 * 3600, clock=time.time):
        directory = Path(directory)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = directory / 'sessions.sqlite'
        self.ttl = ttl
        self.clock = clock
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS sessions (digest TEXT PRIMARY KEY, username TEXT NOT NULL, csrf TEXT NOT NULL, expires INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS failures (address TEXT PRIMARY KEY, count INTEGER NOT NULL, since INTEGER NOT NULL)')
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def create(self, username, ttl=None):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        expires = int(self.clock()) + (self.ttl if ttl is None else ttl)
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE expires <= ?', (int(self.clock()),))
            db.execute('INSERT INTO sessions VALUES (?, ?, ?, ?)', (self.digest(token), username, csrf, expires))
        return token, self.get(token)

    def get(self, token):
        if not token or len(token) > 128:
            return None
        with self.connect() as db:
            row = db.execute('SELECT username, csrf, expires FROM sessions WHERE digest=? AND expires>?', (self.digest(token), int(self.clock()))).fetchone()
        return dict(row) if row else None

    def revoke(self, token):
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE digest=?', (self.digest(token or ''),))

    def limited(self, address):
        with self.connect() as db:
            row = db.execute('SELECT count, since FROM failures WHERE address=?', (address,)).fetchone()
        return bool(row and row['count'] >= 8 and row['since'] > self.clock() - 900)

    def failed(self, address):
        now = int(self.clock())
        with self.connect() as db:
            db.execute('DELETE FROM failures WHERE since <= ?', (now - 900,))
            db.execute('INSERT INTO failures VALUES (?, 1, ?) ON CONFLICT(address) DO UPDATE SET count=count+1', (address, now))

    def clear_failures(self, address):
        with self.connect() as db:
            db.execute('DELETE FROM failures WHERE address=?', (address,))

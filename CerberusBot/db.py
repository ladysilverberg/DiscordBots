import sqlite3

class DB:
    def __init__(self, db_name):
        self.conn = sqlite3.connect(db_name)
        cursor = self.conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users(
            ID INTEGER PRIMARY KEY NOT NULL,
            VALIDATED INTEGER DEFAULT 0,
            NAME TEXT,
            TOKEN TEXT
        );
        ''')
        cursor.close()
        self.conn.commit()

    def create_or_get_user(self, discord_id):
        user = self.get_user(discord_id)
        if user is None:
            self.create_user(discord_id)
            return self.get_user(discord_id)
        else:
            return user

    def create_user(self, discord_id):
        cursor = self.conn.cursor()
        query = 'INSERT INTO users(id) VALUES(?);'
        cursor.execute(query, (str(discord_id),))
        self.conn.commit()
        cursor.close()

    def get_user(self, discord_id):
        cursor = self.conn.cursor()
        query = 'SELECT * FROM users WHERE id = ?;'
        cursor.execute(query, (str(discord_id),))
        row = cursor.fetchone()
        cursor.close()
        return row

    def set_user_token(self, discord_id, token):
        cursor = self.conn.cursor()
        query = 'UPDATE users SET TOKEN = ? WHERE id = ?;'
        cursor.execute(query, (str(token), str(discord_id)))
        self.conn.commit()
        cursor.close()

    def set_user_name(self, discord_id, name):
        cursor = self.conn.cursor()
        query = 'UPDATE users SET NAME = ? WHERE id = ?;'
        cursor.execute(query, (str(name), str(discord_id)))
        self.conn.commit()
        cursor.close()

    def set_user_validation(self, discord_id, validated):
        cursor = self.conn.cursor()
        query = 'UPDATE users SET VALIDATED = ? WHERE id = ?;'
        cursor.execute(query, (validated, str(discord_id)))
        self.conn.commit()
        cursor.close()

    def close(self):
        self.conn.close()


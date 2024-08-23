from loguru import logger



def create_users_table(cursor, conn):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER UNIQUE
        )
    ''')
    conn.commit()
    logger.info('Users table was created!')

def get_all_users(cursor):
    cursor.execute('SELECT chat_id FROM users')
    users = cursor.fetchall()
    return [user[0] for user in users]
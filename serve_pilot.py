"""Start the hosted pilot with an administrator configured through secrets."""

import os
import sqlite3

from waitress import serve
from werkzeug.security import generate_password_hash


def main():
    secret = os.environ.get('GP_SECRET_KEY', '')
    username = os.environ.get('GP_ADMIN_USER', '').strip()
    password = os.environ.get('GP_ADMIN_PASSWORD', '')
    if len(secret) < 32 or not username or len(password) < 16:
        raise SystemExit('Configure GP_SECRET_KEY, GP_ADMIN_USER e GP_ADMIN_PASSWORD no serviço de hospedagem.')
    if os.environ.get('GP_HTTPS') != '1':
        raise SystemExit('Configure HTTPS no serviço e GP_HTTPS=1.')

    from app import app

    connection = sqlite3.connect(app.config['DATABASE'])
    try:
        with connection:
            connection.execute(
                'INSERT INTO users (username, password_hash) VALUES (?, ?) '
                'ON CONFLICT(username) DO NOTHING',
                (username, generate_password_hash(password)),
            )
    finally:
        connection.close()

    serve(app, host='0.0.0.0', port=int(os.environ.get('PORT', '10000')), threads=4)


if __name__ == '__main__':
    main()

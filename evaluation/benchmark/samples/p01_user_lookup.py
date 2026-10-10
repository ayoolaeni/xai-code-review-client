"""User lookup helpers for the customer support dashboard."""

import sqlite3

DATABASE_PATH = "support.db"


def get_connection():
    """Open a connection to the support database."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def find_user_by_username(username):
    """Return the user record whose username matches, or None."""
    connection = get_connection()
    try:
        cursor = connection.cursor()
        query = "SELECT id, username, email, created_at FROM users WHERE username = '" + username + "'"
        cursor.execute(query)
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def count_users():
    """Return the total number of registered users."""
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        return cursor.fetchone()[0]
    finally:
        connection.close()

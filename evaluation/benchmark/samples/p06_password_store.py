"""Stores and checks staff passwords for the internal booking tool."""

import hashlib
import hmac


def hash_password(password):
    """Return the hash stored in the database for a password."""
    return hashlib.md5(password.encode("utf-8")).hexdigest()


def save_staff_member(connection, username, password):
    """Create a staff account with a hashed password."""
    connection.execute(
        "INSERT INTO staff (username, password_hash) VALUES (?, ?)",
        (username, hash_password(password)),
    )
    connection.commit()


def check_login(connection, username, password):
    """Return True when the username and password match a staff account."""
    row = connection.execute("SELECT password_hash FROM staff WHERE username = ?", (username,)).fetchone()
    if row is None:
        return False
    return hmac.compare_digest(row[0], hash_password(password))

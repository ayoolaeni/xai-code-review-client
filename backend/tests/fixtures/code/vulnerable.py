import hashlib
import os
import sqlite3


def get_user(username):
    conn = sqlite3.connect("app.db")
    cur = conn.cursor()
    query = "SELECT * FROM users WHERE name = '" + username + "'"
    cur.execute(query)
    return cur.fetchone()


def ping(host):
    os.system("ping -c 1 " + host)


def hash_pw(pw):
    return hashlib.md5(pw.encode()).hexdigest()


def load():
    try:
        return open("x").read()
    except:
        pass

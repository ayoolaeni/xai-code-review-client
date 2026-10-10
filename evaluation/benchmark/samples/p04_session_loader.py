"""Restores a visitor's saved shopping cart from a cookie."""

import base64
import pickle

from flask import Flask, jsonify, request

app = Flask(__name__)


def decode_saved_cart(cookie_value):
    """Turn the cookie text back into the saved cart dictionary."""
    raw = base64.b64decode(cookie_value)
    return pickle.loads(raw)


@app.route("/cart")
def show_cart():
    """Return the items stored in the visitor's saved cart."""
    cookie_value = request.cookies.get("saved_cart")
    if cookie_value is None:
        return jsonify({"items": []})
    saved_cart = decode_saved_cart(cookie_value)
    items = saved_cart.get("items", [])
    return jsonify({"items": items, "count": len(items)})

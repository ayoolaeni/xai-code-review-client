"""Lets customers download the invoices generated for their account."""

import os

from flask import Flask, Response, abort, request

app = Flask(__name__)

INVOICE_DIR = "/srv/app/invoices"


@app.route("/invoices/download")
def download_invoice():
    """Send the requested invoice file to the browser."""
    filename = request.args.get("file", "")
    if not filename.endswith(".pdf"):
        abort(400)
    path = os.path.join(INVOICE_DIR, filename)
    if not os.path.isfile(path):
        abort(404)
    with open(path, "rb") as handle:
        content = handle.read()
    return Response(content, mimetype="application/pdf")


@app.route("/invoices/count")
def count_invoices():
    """Return how many invoice files exist."""
    names = [name for name in os.listdir(INVOICE_DIR) if name.endswith(".pdf")]
    return {"count": len(names)}

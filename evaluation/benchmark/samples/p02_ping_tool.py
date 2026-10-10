"""Network diagnostics endpoint used by the operations team."""

import os
import re

from flask import Flask, jsonify, request

app = Flask(__name__)

HOSTNAME_PATTERN = re.compile(r"^[A-Za-z0-9.-]{1,253}$")


@app.route("/diagnostics/ping")
def ping_host():
    """Ping the host given in the query string and report whether it answered."""
    host = request.args.get("host", "")
    if not host:
        return jsonify({"error": "host is required"}), 400
    exit_code = os.system("ping -c 1 " + host)
    return jsonify({"host": host, "reachable": exit_code == 0})


@app.route("/diagnostics/validate")
def validate_host():
    """Check that a host name has a valid format without contacting it."""
    host = request.args.get("host", "")
    return jsonify({"host": host, "valid": bool(HOSTNAME_PATTERN.match(host))})

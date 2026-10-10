"""A small calculator API used by the pricing spreadsheet importer."""

from flask import Flask, jsonify, request

app = Flask(__name__)

MAX_EXPRESSION_LENGTH = 200


def is_reasonable_length(expression):
    """Reject empty or very long expressions."""
    return 0 < len(expression) <= MAX_EXPRESSION_LENGTH


@app.route("/calculate", methods=["POST"])
def calculate():
    """Evaluate the arithmetic expression sent by the client."""
    payload = request.get_json(silent=True) or {}
    expression = str(payload.get("expression", ""))
    if not is_reasonable_length(expression):
        return jsonify({"error": "invalid expression"}), 400
    result = eval(expression)
    return jsonify({"expression": expression, "result": result})

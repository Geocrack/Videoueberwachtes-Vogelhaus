from pathlib import Path

from flask import Flask, jsonify, send_file

app = Flask(__name__)

INDEX_HTML = Path(__file__).resolve().parent.parent / "index.html"


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/")
def index():
    return send_file(INDEX_HTML)


if __name__ == "__main__":
    app.run(port=5000, debug=True)

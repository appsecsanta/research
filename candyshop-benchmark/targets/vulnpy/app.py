"""Minimal Flask app that registers the vulnpy vulnerable blueprint."""

from flask import Flask, redirect
from vulnpy.flask import vulnerable_blueprint

app = Flask(__name__)
app.register_blueprint(vulnerable_blueprint)


@app.route("/")
def index():
    return redirect("/vulnpy/")

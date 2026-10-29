"""Compatibility entry point for the Layer 3 local web application."""

from ..layer3.webapp.run import app


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, threaded=True)

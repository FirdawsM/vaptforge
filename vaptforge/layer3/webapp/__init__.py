import hmac
import os
import secrets
from pathlib import Path

from flask import Flask, abort, g, request, session


def create_app(config=None):
    instance_path = Path(__file__).resolve().parents[3] / "instance"
    app = Flask(__name__, instance_path=str(instance_path))
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("VAPTFORGE_SECRET_KEY") or secrets.token_hex(32),
        JOBS_DIR=Path(app.instance_path) / "jobs",
        ASSESSMENTS_DIR=Path(app.instance_path) / "assessments",
        TEMPLATES_AUTO_RELOAD=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("VAPTFORGE_COOKIE_SECURE", "0").lower() in {"1", "true", "yes"},
    )
    if config:
        app.config.update(config)
    for directory in (Path(app.config["JOBS_DIR"]), Path(app.config["ASSESSMENTS_DIR"])):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            directory.chmod(0o700)
        except OSError:
            app.logger.warning("Could not restrict permissions on %s", directory)

    from .app import web
    from .assessments import recover_interrupted_assessments

    app.register_blueprint(web)
    recover_interrupted_assessments(app)

    @app.context_processor
    def provide_csrf_token():
        def csrf_token():
            token = session.get("_csrf_token")
            if token is None:
                token = secrets.token_urlsafe(32)
                session["_csrf_token"] = token
            return token
        return {"csrf_token": csrf_token, "csp_nonce": g.csp_nonce}

    @app.before_request
    def create_csp_nonce():
        g.csp_nonce = secrets.token_urlsafe(18)

    @app.before_request
    def protect_state_changing_requests():
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        expected = session.get("_csrf_token")
        supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            abort(400, description="CSRF validation failed. Reload the page and try again.")
        return None

    @app.after_request
    def disable_page_cache(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
            "form-action 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            f"script-src 'self' 'nonce-{g.csp_nonce}'"
        )
        return response

    return app

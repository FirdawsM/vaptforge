# VAPTforge security review

**Review date:** 2026-10-27  
**Scope:** Local source review of the Flask UI, CLI target handling, command runner, file-based assessment storage, and current Docker configuration. This is not a penetration test of a deployed instance or a third-party target.

## Changes made

- CLI and web requests now share a strict HTTP(S) target validator. It rejects shell metacharacters, credentials, query strings, fragments, invalid ports, and IPv6 literals that could interact with shell globbing in the existing command templates.
- The Flask app rejects POST, PUT, PATCH, and DELETE requests without a session-bound CSRF token. All current POST forms include that token.
- The default Flask signing key is randomly generated per process. Deployments using multiple workers must set a stable random `VAPTFORGE_SECRET_KEY` for every worker.
- Session cookies are HttpOnly and SameSite=Lax. `VAPTFORGE_COOKIE_SECURE=1` enables the Secure flag for HTTPS deployments.
- Responses now include clickjacking, MIME-sniffing, referrer, permissions, and content-security headers. Inline JavaScript must carry a per-request CSP nonce; inline styles remain allowed for the current templates.
- Assessment and job directories are created or reset to owner-only permissions. New JSON records are written with mode `0600`.
- README documents that custom test-definition YAML is trusted executable configuration and that the web UI is for a single local operator.

## Remaining security limits

- **No authentication or per-user authorization.** The web app binds to `127.0.0.1` in `vaptforge/layer3/webapp/run.py`, which is the supported use. Do not expose it on a LAN or internet-facing proxy until authentication and access control are added.
- **The command runner uses `shell=True`.** Shipped commands are expanded only after strict target validation. A custom `--definitions` YAML file can execute arbitrary commands and must be treated like code.
- **A target is not independently authorized by the software.** The operator confirmation is recorded, but VAPTforge cannot verify client permission or enforce network-level scope boundaries. Use only authorized targets and network controls appropriate to the engagement.
- **Docker is not a complete security boundary.** The current Docker image packages the CLI tools; it does not run or isolate the Flask UI. Containerized scans still have network access to whatever the container can reach.
- **The UI uses inline styles.** The CSP permits inline CSS for current templates. Inline JavaScript must use a per-response nonce; template escaping remains important when rendering scanner output.
- **Dependency vulnerability scanning was not available in this review environment.** `requirements.txt` uses a Flask version range rather than a fully locked, hash-verified dependency set.

## Verification performed

- Compiled the Python package with `compileall`.
- Exercised the target validator against valid URLs and shell-injection, query, credential, IPv6, and malformed-host inputs.
- Confirmed the CLI exits before command execution for a shell-injection target.
- Used Flask's test client to confirm an un-tokened assessment POST is rejected and security headers and private storage-directory modes are present.

No live scan was run as part of this review.

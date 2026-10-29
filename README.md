<pre align="center" aria-label="VAPTforge">
██╗   ██╗ █████╗ ██████╗ ████████╗███████╗ ██████╗ ██████╗  ██████╗ ███████╗
██║   ██║██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝
██║   ██║███████║██████╔╝   ██║   █████╗  ██║   ██║██████╔╝██║  ███╗█████╗
╚██╗ ██╔╝██╔══██║██╔═══╝    ██║   ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝
 ╚████╔╝ ██║  ██║██║        ██║   ██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗
  ╚═══╝  ╚═╝  ╚═╝╚═╝        ╚═╝   ╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
</pre>

<p align="center">
  <img alt="Focus: Web Application Security" src="https://img.shields.io/badge/Focus-Web%20Application%20Security-E53935?style=for-the-badge" />
  <img alt="Standard: OWASP WSTG" src="https://img.shields.io/badge/Standard-OWASP%20WSTG-0066A1?style=for-the-badge&logo=owasp&logoColor=white" />
  <img alt="Platform: CLI, Flask, Docker" src="https://img.shields.io/badge/Platform-CLI%20%7C%20Flask%20%7C%20Docker-2E9D57?style=for-the-badge" />
  <img alt="MIT License" src="https://img.shields.io/badge/License-MIT-D4A017?style=for-the-badge" />
  <img alt="Status: In Development" src="https://img.shields.io/badge/Status-In%20Development-E87500?style=for-the-badge" />
</p>

<p align="center"><strong>Authorized web application security assessments, from scan to client-ready report.</strong></p>

<p align="center"><a href="#quick-start">Quick start</a> · <a href="#run-with-docker">Docker</a> · <a href="#cli-scanner-and-catalog">Layer 1: Scanner</a> · <a href="#report-builder">Layer 2: Reports</a> · <a href="#assessment-web-interface">Layer 3: Web UI</a> · <a href="#security-and-scope">Security</a></p>

---

## Project overview

VAPTforge is a local-first CLI and web application for authorized web application security assessments. It runs a configurable set of WSTG checks, saves scan evidence, and helps turn reviewed results into client-ready reports.

**Use VAPTforge only on targets you own or are explicitly authorized to assess.**

## Quick start

### Install

```bash
git clone https://github.com/FirdawsM/vaptforge.git
cd vaptforge
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Install the common catalog tools on Debian or Ubuntu:

```bash
sudo apt install whatweb gobuster curl dirb -y
```

The catalog also needs Nikto available on `PATH`. The Docker image pins Nikto 2.6.1 and configures the Dirb wordlist path for you; use Docker for a reproducible tool setup.

## Run with Docker

Docker packages the scanner tools, Python dependencies, and wordlist into a Debian Bookworm image:

```bash
docker compose build
mkdir -p out
docker compose run --rm vaptforge \
  --target https://your-authorized-target.example \
  --max-phase 2 \
  --timeout 120 \
  --out /out/scan_results.json
```

The host’s `out/` directory receives the results. The image records installed tool versions at `/usr/share/vaptforge/tool-versions.txt`:

```bash
docker run --rm --entrypoint cat vaptforge:local /usr/share/vaptforge/tool-versions.txt
```

On Linux, if the output directory is not writable by the container user, build with your numeric user and group IDs:

```bash
export VAPTFORGE_UID="$(id -u)"
export VAPTFORGE_GID="$(id -g)"
docker compose build
```

The container uses the host network connection; it does not bypass DNS, VPN, firewall, routing, or target reachability issues.

---

<pre align="center" aria-label="Layer 1">
██╗       █████╗  ██╗   ██╗ ███████╗ ██████╗        ██╗
██║      ██╔══██╗ ╚██╗ ██╔╝ ██╔════╝ ██╔══██╗      ███║
██║      ███████║  ╚████╔╝  █████╗   ██████╔╝      ╚██║
██║      ██╔══██║   ╚██╔╝   ██╔══╝   ██╔══██╗       ██║
███████╗ ██║  ██║    ██║    ███████╗ ██║  ██║       ██║
╚══════╝ ╚═╝  ╚═╝    ╚═╝    ╚══════╝ ╚═╝  ╚═╝       ╚═╝
</pre>

### CLI scanner and catalog

The catalog is [`test_definitions.yaml`](vaptforge/layer1/test_definitions.yaml). Each entry defines a WSTG check, command, phase, verdict method, caution, and attack-surface tags.

| Phase | Focus | WSTG checks |
|-------|-------|-------------|
| 0 | Web server fingerprinting and information disclosure | INFO-02, INFO-03, INFO-05 |
| 1 | Server configuration, file discovery, and HSTS | CONF-02, CONF-03, CONF-07 |
| 2 | Clickjacking response header | CLNT-09 |
| 3 | HTTP method review | CONF-06; requires `--confirm-test-accounts` |
| 4 | SQL injection probe and account lockout review | INPV-05, ATHN-03; requires `--signoff-ref` and confirmation |

Engine phases 0–2 run by default; these scanner risk phases are separate from the web UI’s eight assessment lifecycle steps. Copy an existing entry in `vaptforge/layer1/test_definitions.yaml` to add a check.

### Run a scan
<img width="1351" height="672" alt="image" src="https://github.com/user-attachments/assets/e4322439-3be3-4599-a231-5148e07568a8" />

```bash
.venv/bin/python -m vaptforge.layer1.cli --target https://your-authorized-target.example
```

Results are written to `scan_results.json` in the current directory; use `--out` to choose another path. Raise the phase ceiling only when the engagement scope allows it.

Phase 3 checks require authorization to use disposable test accounts:

```bash
.venv/bin/python -m vaptforge.layer1.cli \
  --target https://your-authorized-target.example \
  --max-phase 3 \
  --confirm-test-accounts
```

Phase 4 checks require a reference to written client authorization and interactive target confirmation:

```bash
.venv/bin/python -m vaptforge.layer1.cli \
  --target https://your-authorized-target.example \
  --max-phase 4 \
  --signoff-ref "authorization-ticket-or-document"
```

For an approved scripted run, `--yes` skips the interactive prompt but still requires `--signoff-ref`.

Targets must be conservative HTTP(S) URLs without credentials, query strings, fragments, or IPv6 literals. Custom `--definitions` YAML is executable configuration: its command strings run through the local shell, so use only definitions you trust.

---

<pre align="center" aria-label="Layer 2">
██╗       █████╗  ██╗   ██╗ ███████╗ ██████╗       ██████╗
██║      ██╔══██╗ ╚██╗ ██╔╝ ██╔════╝ ██╔══██╗      ╚════██╗
██║      ███████║  ╚████╔╝  █████╗   ██████╔╝       ████╔═╝
██║      ██╔══██║   ╚██╔╝   ██╔══╝   ██╔══██╗      ██╔═══╝
███████╗ ██║  ██║    ██║    ███████╗ ██║  ██║      ███████╗
╚══════╝ ╚═╝  ╚═╝    ╚═╝    ╚══════╝ ╚═╝  ╚═╝      ╚══════╝
</pre>

### Report builder

Build a Word report from reviewed scan results:

```bash
.venv/bin/python -m vaptforge.layer2.cli_report \
  --results scan_results.json \
  --out report.docx \
  --prepared-by "Organization name"
```

The report includes a scan summary, catalog coverage, findings, captured command output, and an appendix for skipped, blocked, or inconclusive checks. If `--prepared-by` is omitted, the template placeholder remains unchanged. An alternate `--template` must be a clean cover-only document without sample findings.

---

<pre align="center" aria-label="Layer 3">
██╗       █████╗  ██╗   ██╗ ███████╗ ██████╗       ██████╗
██║      ██╔══██╗ ╚██╗ ██╔╝ ██╔════╝ ██╔══██╗      ╚════██╗
██║      ███████║  ╚████╔╝  █████╗   ██████╔╝       █████╔╝
██║      ██╔══██║   ╚██╔╝   ██╔══╝   ██╔══██╗       ╚═══██╗
███████╗ ██║  ██║    ██║    ███████╗ ██║  ██║      ██████╔╝
╚══════╝ ╚═╝  ╚═╝    ╚═╝    ╚══════╝ ╚═╝  ╚═╝      ╚═════╝
</pre>

### Assessment web interface

Start the local Flask application:

```bash
.venv/bin/python -m vaptforge.layer3.webapp.run
```
<img width="1919" height="932" alt="image" src="https://github.com/user-attachments/assets/55c33f2e-bbf8-41e5-9ffa-0381c3b3abb7" />

Open the address printed by Flask. The UI records assessment scope, starts the default low-risk scan, displays job output, and lets you review or download results. Generate the Word report after reviewing the JSON evidence.

<img width="1919" height="932" alt="image" src="https://github.com/user-attachments/assets/328f12ee-b5c6-411b-bfe3-80369aca3780" />

<img width="1919" height="932" alt="image" src="https://github.com/user-attachments/assets/7d830d02-5997-40a7-928a-ddc5eef1f3cc" />

The server binds to `127.0.0.1` and has no user accounts. Keep it local; do not expose it to a LAN, reverse proxy, or the public internet without adding authentication and access controls. For HTTPS deployments, configure a stable random `VAPTFORGE_SECRET_KEY` and set `VAPTFORGE_COOKIE_SECURE=1`.

---

## Security and scope

| Area | What to know |
|------|--------------|
| Command execution | The runner uses `shell=True`; target validation is a critical boundary. |
| Custom definitions | YAML command fields execute locally; treat custom definitions as code. |
| Target authorization | VAPTforge does not verify client permission or block internal and metadata addresses; confirm the written scope before scanning. |
| Web interface | Binds to localhost, has CSRF protection, and does not provide authentication. Keep it local. |
| Local data | Assessment and job directories use private permissions; CLI output follows the process umask. Protect scan artifacts according to your engagement requirements. |
| Content Security Policy | Inline styles are currently allowed; scripts use a per-response nonce. |

The validator intentionally rejects IPv6 literals, credentials, query strings, fragments, and URL characters outside its conservative allowlist. Add support for other target formats explicitly before relying on them.

## Platform notes

- **Linux:** Native use is supported; Docker provides the most reproducible tool setup.
- **Windows:** Use WSL with an Ubuntu distribution; native PowerShell and `cmd.exe` do not support the catalog’s Unix command syntax.
- **macOS:** Python and `curl` are available natively; install the scanner tools separately and update the Dirb wordlist path in `vaptforge/layer1/test_definitions.yaml` to match your local SecLists installation.

## License

VAPTforge is distributed under the [MIT License](LICENSE).

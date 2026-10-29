"""File-based assessment and phase-result storage for the local web UI."""

import json
import os
import re
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

LIFECYCLE_PHASES = [
    (1, "Pre-engagement", "Confirm the authorized target and assessment scope."),
    (2, "Reconnaissance", "Review configured information-gathering checks."),
    (3, "Enumeration", "No separate enumeration checks are mapped in the current catalog."),
    (4, "Vulnerability assessment", "Review the remaining configured WSTG checks and their evidence."),
    (5, "Post-exploitation", "No automatic exploitation is performed by this MVP."),
    (6, "Reporting", "Generate the combined assessment report."),
    (7, "Retesting", "Retesting is not automated by the current test catalog."),
    (8, "Closure", "Review the report and preserve the assessment deliverables."),
]


ASSESSMENT_ID = re.compile(r"^[a-f0-9]{32}$")
_ASSESSMENT_LOCK = threading.RLock()


def _serialized(function):
    def wrapped(*args, **kwargs):
        with _ASSESSMENT_LOCK:
            return function(*args, **kwargs)
    return wrapped


def _assessment_dir(app, assessment_id):
    if not ASSESSMENT_ID.fullmatch(assessment_id or ""):
        return None
    return Path(app.config["ASSESSMENTS_DIR"]) / assessment_id


def _write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


@_serialized
def create_assessment(app, scope):
    assessment_id = uuid.uuid4().hex
    assessment_dir = Path(app.config["ASSESSMENTS_DIR"]) / assessment_id
    assessment_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    assessment = {
        "id": assessment_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target": scope["target"],
        "scope": scope,
        "current_phase": 1,
        "status": "starting",
        "phase_results": {},
        "scan_runs": [],
        "report_path": str(assessment_dir / "final-report.html"),
    }
    _write_json(assessment_dir / "assessment.json", assessment)
    return assessment


@_serialized
def get_assessment(app, assessment_id):
    assessment_dir = _assessment_dir(app, assessment_id)
    if assessment_dir is None:
        return None
    path = assessment_dir / "assessment.json"
    if not path.is_file():
        return None
    try:
        assessment = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    # Reclassify legacy phase records without evidence so they are not shown as complete.
    if "status" not in assessment and not assessment.get("scan_runs"):
        results = assessment.setdefault("phase_results", {})
        replacements = {
            "2": ("not_configured", "No lifecycle-mapped checks", "No scan evidence is linked to this assessment. Start a new assessment to generate current results."),
            "3": ("not_configured", "No lifecycle-mapped checks", "No enumeration checks are mapped in the current test catalog."),
            "4": ("not_run", "No scan run linked", "No scanner output is linked to this assessment."),
            "5": ("not_automated", "Not automated", "Automatic exploitation is intentionally excluded from this MVP."),
            "6": ("report_not_generated", "Regenerate report", "This legacy report predates evidence-backed phase results. Generate a fresh combined report."),
            "7": ("not_configured", "Retest not configured", "No retest workflow is configured in the current test catalog."),
            "8": ("open", "Closure review required", "Review current results and preserve the assessment deliverables."),
        }
        for key, (status, outcome, notes) in replacements.items():
            previous = results.get(key, {})
            results[key] = {**previous, "status": status, "outcome": outcome, "notes": notes, "tests": []}
        assessment["current_phase"] = 2
        assessment["status"] = "legacy_needs_refresh"
        assessment["legacy_result_refresh_required"] = True
        _write_json(path, assessment)
    return assessment


@_serialized
def attach_scan_job(app, assessment_id, job_id):
    assessment_dir = _assessment_dir(app, assessment_id)
    assessment = get_assessment(app, assessment_id)
    if assessment_dir is None or assessment is None:
        return
    assessment["scan_job_id"] = job_id
    _write_json(assessment_dir / "assessment.json", assessment)


@_serialized
def prepare_scan_retry(app, assessment_id):
    """Reset scan-derived phase summaries before rerunning a saved scope."""
    assessment_dir = _assessment_dir(app, assessment_id)
    assessment = get_assessment(app, assessment_id)
    if assessment_dir is None or assessment is None:
        return None
    scope = assessment.get("scope", {})
    if not scope.get("authorization_confirmed"):
        return None
    timestamp = datetime.now(timezone.utc).isoformat()
    assessment["status"] = "starting"
    assessment["current_phase"] = 2
    assessment["report_refresh_required"] = True
    assessment["phase_results"]["2"] = {
        "status": "in_progress", "outcome": "Scan restarted", "notes": "The configured checks are running again against the saved authorized target.", "evidence": "", "limitations": "", "tests": [], "saved_at": timestamp,
    }
    assessment["phase_results"]["4"] = {
        "status": "in_progress", "outcome": "Scan restarted", "notes": "The configured checks are running again against the saved authorized target.", "evidence": "", "limitations": "", "tests": [], "saved_at": timestamp,
    }
    assessment["phase_results"]["6"] = {
        "status": "report_not_generated", "outcome": "Regenerate report after scan", "notes": "The combined report must be regenerated after the restarted scan completes.", "evidence": "", "limitations": "", "tests": [], "saved_at": timestamp,
    }
    _write_json(assessment_dir / "assessment.json", assessment)
    return assessment


@_serialized
def set_assessment_status(app, assessment_id, status):
    assessment_dir = _assessment_dir(app, assessment_id)
    assessment = get_assessment(app, assessment_id)
    if assessment_dir is None or assessment is None:
        return
    assessment["status"] = status
    _write_json(assessment_dir / "assessment.json", assessment)


@_serialized
def list_assessments(app):
    assessments_dir = Path(app.config["ASSESSMENTS_DIR"])
    assessments = []
    for path in assessments_dir.glob("*/assessment.json"):
        assessment = get_assessment(app, path.parent.name)
        if assessment:
            assessments.append(assessment)
    return sorted(assessments, key=lambda item: item.get("created_at", ""), reverse=True)


@_serialized
def recover_interrupted_assessments(app):
    """Mark in-memory jobs from a previous server process as interrupted."""
    for path in Path(app.config["ASSESSMENTS_DIR"]).glob("*/assessment.json"):
        assessment = get_assessment(app, path.parent.name)
        if not assessment:
            continue
        if assessment.get("status") in {"starting", "running"}:
            assessment["status"] = "interrupted"
            assessment["interruption_note"] = "The web server restarted before this scan could save its results. Start a new assessment to retry."
        if assessment.get("status") != "interrupted":
            continue
        results = assessment.setdefault("phase_results", {})
        timestamp = datetime.now(timezone.utc).isoformat()
        defaults = {
            "2": ("interrupted", "Scan interrupted", assessment.get("interruption_note", "No reconnaissance result was saved.")),
            "3": ("not_configured", "No enumeration checks configured", "The current test catalog has no separate enumeration checks."),
            "4": ("interrupted", "No scan results saved", assessment.get("interruption_note", "No vulnerability assessment output was saved.")),
            "5": ("not_automated", "Not automated", "Automatic exploitation is intentionally excluded from this MVP."),
            "6": ("report_not_generated", "Report not generated", "Generate the combined report after scan results are available."),
            "7": ("not_configured", "Retest not configured", "No retest workflow is configured in the current test catalog."),
            "8": ("open", "Closure review required", "Review the saved scope and any available evidence before closing."),
        }
        changed = False
        for key, (status, outcome, notes) in defaults.items():
            if key not in results:
                results[key] = {"status": status, "outcome": outcome, "notes": notes, "evidence": "", "limitations": "", "tests": [], "saved_at": timestamp}
                changed = True
        missing_html = any(
            results.get(str(number)) and not (path.parent / f"phase-{number:02d}-result.html").is_file()
            for number in range(1, 9)
        )
        if changed or missing_html:
            if changed:
                _write_json(path, assessment)
            from flask import render_template

            scan_runs = load_scan_runs(app, assessment["id"])
            with app.test_request_context("/"):
                for phase_number, phase in enumerate(LIFECYCLE_PHASES, start=1):
                    record = results.get(str(phase_number))
                    if not record:
                        continue
                    html = render_template("phase_result.html", assessment=assessment, phase=phase, record=record, scan_runs=scan_runs, active="assessments")
                    (path.parent / f"phase-{phase_number:02d}-result.html").write_text(html, encoding="utf-8")


@_serialized
def save_phase(app, assessment_id, phase, record, result_html, advance=True):
    assessment_dir = _assessment_dir(app, assessment_id)
    assessment = get_assessment(app, assessment_id)
    if assessment_dir is None or assessment is None:
        return None
    phase_key = str(phase)
    assessment["phase_results"][phase_key] = record
    if advance:
        assessment["current_phase"] = min(8, max(assessment.get("current_phase", 1), phase + 1))
    _write_json(assessment_dir / "assessment.json", assessment)
    _write_json(assessment_dir / f"phase-{phase:02d}.json", record)
    result_path = assessment_dir / f"phase-{phase:02d}-result.html"
    result_path.write_text(result_html, encoding="utf-8")
    return assessment


def phase_result_path(app, assessment_id, phase):
    assessment_dir = _assessment_dir(app, assessment_id)
    if assessment_dir is None:
        return None
    path = assessment_dir / f"phase-{phase:02d}-result.html"
    return path if path.is_file() else None


@_serialized
def record_scan_run(app, assessment_id, job_id, target, status, results_path, logs, error=None):
    assessment_dir = _assessment_dir(app, assessment_id)
    assessment = get_assessment(app, assessment_id)
    if assessment_dir is None or assessment is None:
        return
    scan_dir = assessment_dir / "scan-runs"
    scan_dir.mkdir(exist_ok=True)
    result_file = None
    if results_path and Path(results_path).is_file():
        result_file = f"{job_id}.json"
        shutil.copy2(results_path, scan_dir / result_file)
    log_file = f"{job_id}.log"
    (scan_dir / log_file).write_text("\n".join(logs), encoding="utf-8")
    run = {
        "id": job_id,
        "target": target,
        "status": status,
        "result_file": result_file,
        "log_file": log_file,
        "error": error,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    runs = [item for item in assessment.get("scan_runs", []) if item.get("id") != job_id]
    runs.append(run)
    assessment["scan_runs"] = runs
    assessment["status"] = "ready" if status == "done" else "failed"
    assessment["report_refresh_required"] = True
    assessment["current_phase"] = 8
    _write_json(assessment_dir / "assessment.json", assessment)

    scan_runs = load_scan_runs(app, assessment_id)
    tests = [test for saved_run in scan_runs for test in saved_run.get("tests", [])]
    recon_tests = [test for test in tests if (test.get("wstg_id") or "").startswith("WSTG-INFO-")]
    enumeration_tests = []
    phase4_tests = [test for test in tests if test not in recon_tests]

    def automatic_record(record_status, outcome, notes, phase_tests=None):
        return {
            "status": record_status,
            "outcome": outcome,
            "notes": notes,
            "evidence": "",
            "limitations": "",
            "tests": phase_tests or [],
            "saved_at": run["saved_at"],
        }

    counts = {}
    for test in tests:
        result = test.get("result", "Unknown")
        counts[result] = counts.get(result, 0) + 1
    summary = ", ".join(f"{label}: {count}" for label, count in sorted(counts.items())) or "No test results were written."

    assessment["phase_results"] = {
        "1": assessment.get("phase_results", {}).get("1", {
            "status": "completed", "outcome": "Scope recorded", "notes": "Assessment URL and authorization confirmation recorded.", "saved_at": assessment.get("created_at")
        }),
        "2": automatic_record(
            "generated" if recon_tests else "not_configured",
            "Results generated" if recon_tests else "No lifecycle-mapped checks",
            "The test catalog contains these WSTG information-gathering checks." if recon_tests else "The current catalog does not define a separate lifecycle reconnaissance run. See the Phase 4 unified test output.",
            recon_tests,
        ),
        "3": automatic_record(
            "completed" if enumeration_tests else "not_configured",
            "Results generated" if enumeration_tests else "No lifecycle-mapped checks",
            "The following configured discovery checks are shown here." if enumeration_tests else "The current catalog does not define a separate lifecycle enumeration run. See the Phase 4 unified test output.",
            enumeration_tests,
        ),
        "4": automatic_record(
            "failed" if status != "done" else "completed",
            "Scan failed" if status != "done" else "Scan execution completed — review results",
            f"The configured scanner ran once against the authorized target. Result counts: {summary}" + (f" Runner error: {error}" if error else ""),
            phase4_tests,
        ),
        "5": automatic_record("not_automated", "Not automated", "Automatic exploitation is intentionally excluded. No post-exploitation checks were run."),
        "6": automatic_record("report_not_generated", "Report not generated", "Use Reports in the sidebar to generate the combined HTML report from saved phase outputs and linked scan evidence."),
        "7": automatic_record("not_configured", "Retest not configured", "No retest workflow or retest check definitions are configured in this build."),
        "8": automatic_record("open", "Ready for closure review", "The assessment outputs are saved. Review the generated report and handle artifacts according to the engagement requirements."),
    }
    _write_json(assessment_dir / "assessment.json", assessment)

    from flask import render_template

    with app.test_request_context("/"):
        for phase_number, phase in enumerate(LIFECYCLE_PHASES, start=1):
            html = render_template(
                "phase_result.html",
                assessment=assessment,
                phase=phase,
                record=assessment["phase_results"][str(phase_number)],
                scan_runs=scan_runs,
                active="assessments",
            )
            (assessment_dir / f"phase-{phase_number:02d}-result.html").write_text(html, encoding="utf-8")


@_serialized
def load_scan_runs(app, assessment_id):
    assessment_dir = _assessment_dir(app, assessment_id)
    assessment = get_assessment(app, assessment_id)
    if assessment_dir is None or assessment is None:
        return []
    runs = []
    for saved in assessment.get("scan_runs", []):
        run = dict(saved, tests=[], logs="")
        scan_dir = assessment_dir / "scan-runs"
        result_file = saved.get("result_file")
        if result_file and Path(result_file).name == result_file:
            try:
                data = json.loads((scan_dir / result_file).read_text(encoding="utf-8"))
                run["tests"] = data.get("results", []) if isinstance(data, dict) else []
            except (OSError, json.JSONDecodeError):
                run["error"] = run.get("error") or "Saved scan results could not be read."
        log_file = saved.get("log_file")
        if log_file and Path(log_file).name == log_file:
            try:
                run["logs"] = (scan_dir / log_file).read_text(encoding="utf-8")
            except OSError:
                pass
        runs.append(run)
    return runs


@_serialized
def save_final_report(app, assessment_id, report_html):
    assessment_dir = _assessment_dir(app, assessment_id)
    assessment = get_assessment(app, assessment_id)
    if assessment_dir is None or assessment is None:
        return None
    path = assessment_dir / "final-report.html"
    path.write_text(report_html, encoding="utf-8")
    return path


@_serialized
def mark_report_generated(app, assessment_id):
    assessment_dir = _assessment_dir(app, assessment_id)
    assessment = get_assessment(app, assessment_id)
    if assessment_dir is None or assessment is None:
        return None
    record = {
        "status": "report_generated",
        "outcome": "Combined HTML report generated",
        "notes": "The report combines saved lifecycle phase results and any scan runs linked to this assessment.",
        "evidence": "",
        "limitations": "Phases marked not configured, not automated, or open remain visibly incomplete in the report.",
        "tests": [],
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    assessment.setdefault("phase_results", {})["6"] = record
    assessment.pop("legacy_result_refresh_required", None)
    assessment.pop("report_refresh_required", None)
    _write_json(assessment_dir / "assessment.json", assessment)
    return assessment

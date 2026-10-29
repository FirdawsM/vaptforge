from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, send_file, url_for

from .assessments import (
    LIFECYCLE_PHASES,
    create_assessment,
    get_assessment,
    list_assessments,
    load_scan_runs,
    mark_report_generated,
    phase_result_path,
    prepare_scan_retry,
    save_final_report,
    save_phase,
)
from .jobs import JOBS_LOCK, create_report, get_job, get_jobs, start_scan
from vaptforge.layer1.target import is_valid_target_url


web = Blueprint("web", __name__)
def _phase_record_html(assessment, phase_number, record, scan_runs=None):
    return render_template(
        "phase_result.html",
        assessment=assessment,
        phase=LIFECYCLE_PHASES[phase_number - 1],
        record=record,
        scan_runs=scan_runs or [],
        active="assessments",
    )


def _job_or_404(job_id):
    job = get_job(job_id)
    if job is None:
        abort(404)
    return job


@web.get("/")
def index():
    jobs = list(reversed(get_jobs()))
    counts = {state: sum(job["status"] == state for job in jobs) for state in ("queued", "running", "done", "failed")}
    return render_template("dashboard.html", jobs=jobs, counts=counts, assessments=list_assessments(current_app), active="dashboard")


@web.get("/new")
def new_assessment():
    return redirect(url_for("web.assessment_setup"))


@web.get("/assessments/new")
def assessment_setup():
    return render_template("assessment_setup.html", active="setup")


@web.post("/assessments")
def create_assessment_route():
    form = request.form
    target = form.get("target", "").strip()
    if not is_valid_target_url(target):
        return render_template("assessment_setup.html", error="Enter a valid authorized http or https target URL.", values=form, active="setup"), 400
    if form.get("confirm_authorization") != "on":
        return render_template("assessment_setup.html", error="Confirm authorization before creating the assessment.", values=form, active="setup"), 400

    scope = {
        "target": target,
        "environment": "",
        "approach": "black-box",
        "authorized_targets": target,
        "excluded_targets": "",
        "testing_window": "",
        "restrictions": "",
        "technical_contact": "",
        "emergency_contact": "",
        "available_accounts": "",
        "authorization_confirmed": True,
        "prepared_by": None,
    }
    assessment = create_assessment(current_app, scope)
    record = {"status": "completed", "outcome": "Scope recorded", "notes": "Target and authorization confirmation recorded.", "saved_at": assessment["created_at"], "tests": []}
    assessment = save_phase(current_app, assessment["id"], 1, record, "")
    phase_result_path(current_app, assessment["id"], 1).write_text(_phase_record_html(assessment, 1, record), encoding="utf-8")
    job_id = start_scan(current_app._get_current_object(), target, 2, False, None, None, assessment["id"])
    return redirect(url_for("web.job_page", job_id=job_id))


@web.get("/assessments")
def assessments_page():
    return render_template("assessments.html", assessments=list_assessments(current_app), active="assessments")


@web.get("/assessments/<assessment_id>")
def assessment_page(assessment_id):
    assessment = get_assessment(current_app, assessment_id)
    if assessment is None:
        abort(404)
    return render_template("assessment.html", assessment=assessment, phases=LIFECYCLE_PHASES, active="assessments")


@web.post("/assessments/<assessment_id>/restart-scan")
def restart_assessment_scan(assessment_id):
    assessment = get_assessment(current_app, assessment_id)
    if assessment is None:
        abort(404)
    if assessment.get("status") in {"starting", "running"}:
        job_id = assessment.get("scan_job_id")
        if job_id:
            return redirect(url_for("web.job_page", job_id=job_id))
        return redirect(url_for("web.assessment_page", assessment_id=assessment_id))
    if not assessment.get("scope", {}).get("authorization_confirmed"):
        abort(403, "This assessment has no recorded authorization confirmation.")
    assessment = prepare_scan_retry(current_app, assessment_id)
    if assessment is None:
        abort(403, "This assessment cannot be restarted without recorded authorization.")
    job_id = start_scan(current_app._get_current_object(), assessment["target"], 2, False, None, None, assessment_id)
    return redirect(url_for("web.job_page", job_id=job_id))


@web.get("/assessments/<assessment_id>/phases/<int:phase_number>")
def assessment_phase(assessment_id, phase_number):
    assessment = get_assessment(current_app, assessment_id)
    if assessment is None or phase_number not in range(1, 9):
        abort(404)
    result_path = phase_result_path(current_app, assessment_id, phase_number)
    if result_path is None:
        if assessment.get("scan_job_id"):
            return redirect(url_for("web.job_page", job_id=assessment["scan_job_id"]))
        abort(404)
    record = assessment.get("phase_results", {}).get(str(phase_number))
    if record:
        result_path.write_text(
            _phase_record_html(assessment, phase_number, record, load_scan_runs(current_app, assessment_id)),
            encoding="utf-8",
        )
    return send_file(result_path, mimetype="text/html")


@web.get("/assessments/<assessment_id>/phases/<int:phase_number>/result")
def phase_result(assessment_id, phase_number):
    assessment = get_assessment(current_app, assessment_id)
    result_path = phase_result_path(current_app, assessment_id, phase_number)
    if assessment is None or phase_number not in range(1, 9) or result_path is None:
        abort(404)
    record = assessment.get("phase_results", {}).get(str(phase_number))
    if record:
        result_html = _phase_record_html(assessment, phase_number, record, load_scan_runs(current_app, assessment_id))
        result_path.write_text(result_html, encoding="utf-8")
    return send_file(result_path, mimetype="text/html")


@web.get("/assessments/<assessment_id>/phases/<int:phase_number>/result/download")
def phase_result_download(assessment_id, phase_number):
    assessment = get_assessment(current_app, assessment_id)
    result_path = phase_result_path(current_app, assessment_id, phase_number)
    if assessment is None or phase_number not in range(1, 9) or result_path is None:
        abort(404)
    record = assessment.get("phase_results", {}).get(str(phase_number))
    if record:
        result_html = _phase_record_html(assessment, phase_number, record, load_scan_runs(current_app, assessment_id))
        result_path.write_text(result_html, encoding="utf-8")
    return send_file(result_path, as_attachment=True, download_name=f"phase-{phase_number:02d}-result.html", mimetype="text/html")


@web.get("/reports")
def reports_page():
    return render_template("reports.html", assessments=list_assessments(current_app), active="reports")


@web.route("/assessments/<assessment_id>/report", methods=["GET", "POST"])
def assessment_report(assessment_id):
    assessment = get_assessment(current_app, assessment_id)
    if assessment is None:
        abort(404)
    if request.method == "POST":
        assessment = mark_report_generated(current_app, assessment_id)
        if assessment is None:
            abort(404)
        report_html = render_template(
            "final_report.html",
            assessment=assessment,
            phases=LIFECYCLE_PHASES,
            scan_runs=load_scan_runs(current_app, assessment_id),
            active="reports",
        )
        path = save_final_report(current_app, assessment_id, report_html)
        if path is None:
            abort(404)
        return redirect(url_for("web.assessment_report", assessment_id=assessment_id))
    report_path = current_app.config["ASSESSMENTS_DIR"] / assessment_id / "final-report.html"
    report_exists = report_path.is_file() and not assessment.get("legacy_result_refresh_required") and not assessment.get("report_refresh_required")
    return render_template("report_generator.html", assessment=assessment, report_exists=report_exists, active="reports")


@web.get("/assessments/<assessment_id>/report/view")
def assessment_report_view(assessment_id):
    assessment = get_assessment(current_app, assessment_id)
    if assessment is None:
        abort(404)
    if assessment.get("legacy_result_refresh_required") or assessment.get("report_refresh_required"):
        abort(404)
    report_path = current_app.config["ASSESSMENTS_DIR"] / assessment_id / "final-report.html"
    if not report_path.is_file():
        abort(404)
    return send_file(report_path, mimetype="text/html")


@web.get("/assessments/<assessment_id>/report/download")
def download_assessment_report(assessment_id):
    assessment = get_assessment(current_app, assessment_id)
    if assessment is None:
        abort(404)
    if assessment.get("legacy_result_refresh_required") or assessment.get("report_refresh_required"):
        abort(404)
    report_path = current_app.config["ASSESSMENTS_DIR"] / assessment_id / "final-report.html"
    if not report_path.is_file():
        abort(404)
    return send_file(report_path, as_attachment=True, download_name=f"vaptforge-{assessment_id[:8]}-report.html", mimetype="text/html")


@web.get("/lifecycle")
def lifecycle():
    return redirect(url_for("web.assessments_page"))


@web.get("/scan/setup")
def scan_setup():
    return redirect(url_for("web.assessment_setup"))


@web.get("/jobs/<job_id>")
def job_page(job_id):
    job = _job_or_404(job_id)
    return render_template("job.html", job=job, assessment=get_assessment(current_app, job.get("assessment_id")) if job.get("assessment_id") else None, active="assessments")


@web.get("/jobs/<job_id>/status")
def job_status(job_id):
    job = _job_or_404(job_id)
    with JOBS_LOCK:
        return jsonify(
            status=job["status"],
            logs=job["logs"],
            error=job["error"],
            has_results=job["results_path"].is_file(),
        )


@web.get("/jobs/<job_id>/report")
def report(job_id):
    job = _job_or_404(job_id)
    if job["status"] != "done":
        abort(409, "The scan must finish before generating its report.")
    try:
        path = create_report(job)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        abort(500, str(exc))
    return send_file(path, as_attachment=True, download_name="vaptforge-report.docx")


@web.get("/jobs/<job_id>/raw")
def raw(job_id):
    job = _job_or_404(job_id)
    if job["status"] != "done" or not job["results_path"].is_file():
        abort(409, "Scan results are available after the scan finishes.")
    return send_file(job["results_path"], as_attachment=True, download_name="scan_results.json")

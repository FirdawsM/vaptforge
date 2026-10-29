import contextlib
import io
import threading
import uuid
from pathlib import Path

from vaptforge.layer1 import cli
from vaptforge.layer2.report import build_report
from .assessments import attach_scan_job, record_scan_run, set_assessment_status


JOBS = {}
JOBS_LOCK = threading.Lock()
SCAN_LOCK = threading.Lock()


class JobOutput(io.TextIOBase):
    def __init__(self, job):
        self.job = job
        self.pending = ""

    def write(self, value):
        self.pending += value
        lines = self.pending.split("\n")
        self.pending = lines.pop()
        if lines:
            with JOBS_LOCK:
                self.job["logs"].extend(lines)
        return len(value)

    def flush(self):
        if self.pending:
            with JOBS_LOCK:
                self.job["logs"].append(self.pending)
            self.pending = ""


def get_job(job_id):
    with JOBS_LOCK:
        return JOBS.get(job_id)


def get_jobs():
    with JOBS_LOCK:
        return [dict(job, logs=list(job["logs"])) for job in JOBS.values()]


def start_scan(app, target, max_phase, confirm_test_accounts, signoff_ref, prepared_by=None, assessment_id=None):
    job_id = uuid.uuid4().hex
    job_dir = Path(app.config["JOBS_DIR"]) / job_id
    job_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    job = {
        "id": job_id,
        "status": "queued",
        "logs": [],
        "target": target,
        "max_phase": max_phase,
        "prepared_by": prepared_by,
        "assessment_id": assessment_id,
        "results_path": job_dir / "scan_results.json",
        "report_path": job_dir / "report.docx",
        "error": None,
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
    if assessment_id:
        attach_scan_job(app, assessment_id, job_id)

    # Use a shorter timeout for web runs so unreachable targets do not keep the UI waiting.
    argv = ["--target", target, "--max-phase", str(max_phase), "--timeout", "10", "--out", str(job["results_path"]), "--yes"]
    if confirm_test_accounts:
        argv.append("--confirm-test-accounts")
    if signoff_ref:
        argv.extend(("--signoff-ref", signoff_ref))

    def run():
        with SCAN_LOCK:
            with JOBS_LOCK:
                job["status"] = "running"
            output = JobOutput(job)
            try:
                if assessment_id:
                    set_assessment_status(app, assessment_id, "running")
                with contextlib.redirect_stdout(output):
                    cli.main(argv)
                output.flush()
                with JOBS_LOCK:
                    job["status"] = "done"
            except BaseException as exc:
                output.flush()
                with JOBS_LOCK:
                    job["status"] = "failed"
                    job["error"] = str(exc) or exc.__class__.__name__
                    job["logs"].append(f"Scan failed: {job['error']}")
            if assessment_id:
                record_scan_run(
                    app,
                    assessment_id,
                    job_id,
                    target,
                    job["status"],
                    job["results_path"],
                    job["logs"],
                    job["error"],
                )

    threading.Thread(target=run, name=f"vaptforge-{job_id[:8]}", daemon=True).start()
    return job_id


def create_report(job):
    if job["status"] != "done" or not job["results_path"].is_file():
        raise RuntimeError("The scan has not completed successfully.")
    build_report(
        job["results_path"],
        output_path=job["report_path"],
        prepared_by=job.get("prepared_by"),
    )
    return job["report_path"]

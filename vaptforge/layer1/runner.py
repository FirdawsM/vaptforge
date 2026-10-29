"""Runs a shell command and captures stdout/stderr with a timeout."""

import subprocess
from dataclasses import dataclass


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


def run_command(cmd: str, timeout: int = 120) -> CommandResult:
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return CommandResult(stdout=proc.stdout, stderr=proc.stderr, returncode=proc.returncode)
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        timeout_note = f"TIMEOUT after {timeout}s"
        return CommandResult(stdout=stdout, stderr=f"{stderr}\n{timeout_note}".strip(), returncode=-1)
    except FileNotFoundError as e:
        return CommandResult(stdout="", stderr=f"Tool not found on this system: {e}", returncode=-2)

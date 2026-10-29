"""Turns raw command output into a verdict, per the test's check_type.

Pattern matching is a first pass, not a substitute for your eyes — every
Fail/Pass still gets written alongside the raw output in scan_results.json
so you can verify before it goes anywhere near a client report.
"""

import re

_ANSI_ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")


def command_failed(output: str, exit_code: int | None) -> bool:
    clean_output = _ANSI_ESCAPE.sub("", output)
    return bool(
        "TIMEOUT after" in clean_output
        or re.search(r"^\s*ERROR\b", clean_output, re.IGNORECASE | re.MULTILINE)
        or "execution expired" in clean_output.lower()
        or exit_code not in (0, None)
    )


def score_result(definition: dict, output: str, exit_code: int | None = 0) -> tuple[str, str]:
    if command_failed(output, exit_code):
        return "Error", (
            f"Command did not complete successfully (exit_code={exit_code}) — "
            "no verdict possible. Re-run or investigate why the command failed before trusting this result."
        )

    check_type = definition.get("check_type", "manual_review")

    if check_type == "pattern_fail":
        pattern = definition["fail_pattern"]
        if re.search(pattern, output, re.IGNORECASE):
            return "Fail", f"Matched fail pattern: {pattern}"
        return "Pass", "No fail pattern matched — pattern matching isn't exhaustive, spot-check raw_output."

    if check_type == "pattern_pass":
        pattern = definition["pass_pattern"]
        if re.search(pattern, output, re.IGNORECASE):
            return "Pass", f"Matched pass pattern: {pattern}"
        return "Fail", f"Expected pattern not found: {pattern}"

    return "Manual Review", "This WSTG item needs human judgement — raw_output captured below."

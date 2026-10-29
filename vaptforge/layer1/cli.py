"""
vaptforge — Phase 1 WSTG checklist scanner.

Runs the tests in test_definitions.yaml up to --max-phase against --target,
captures output per command, and writes scan_results.json.

Usage:
    python -m vaptforge.layer1.cli --target https://target.example.com
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .attack_surface import coverage as attack_surface_coverage
from .banner import show_banner
from .definitions import load_definitions
from .runner import run_command
from .scoring import score_result
from .target import is_valid_target_url

# Risk gates follow the checklist: phases 0–2 run by default, Phase 3 requires --confirm-test-accounts, and Phase 4 requires --signoff-ref plus interactive confirmation (or --yes).
TEST_ACCOUNTS_PHASE = 3
HIGH_RISK_PHASE = 4


def gate_reason(definition: dict, args: argparse.Namespace) -> str | None:
    """Returns None if the test is cleared to run, else the reason it's blocked."""
    phase = definition["phase"]

    if phase < TEST_ACCOUNTS_PHASE:
        return None

    if phase == TEST_ACCOUNTS_PHASE:
        if not args.confirm_test_accounts:
            return (
                "Phase 3 (vuln validation) needs --confirm-test-accounts — "
                "confirms you are using your own disposable test accounts, not real customer data."
            )
        return None

    if phase >= HIGH_RISK_PHASE:
        if not args.signoff_ref:
            return (
                "Phase 4 (HIGH RISK) needs --signoff-ref '<reference to written client authorization>' "
                "— this tool will not run it without one."
            )
        if not args.yes:
            prompt = (
                f"\n[HIGH RISK] {definition['wstg_id']} — {definition['name']}\n"
                f"Caution: {definition.get('caution', '(none)')}\n"
                f"Sign-off reference on file: {args.signoff_ref}\n"
                f"Type the target exactly ('{args.target}') to confirm you are authorized to run this: "
            )
            typed = input(prompt)
            if typed.strip() != args.target:
                return "Interactive confirmation did not match target — skipped for safety."
        return None

    return None


def main(argv: list[str] | None = None) -> None:
    show_banner()
    parser = argparse.ArgumentParser(
        prog="vaptforge",
        description="Runs Order/Recon Phase 0-N WSTG tests against a target and emits scan_results.json",
    )
    parser.add_argument("--target", required=True, help="Target host/URL, e.g. https://target.example.com")
    parser.add_argument(
        "--max-phase",
        type=int,
        default=2,
        help="Highest Order (Recon Phase) to consider (default 2). Tests above phase 2 are still "
        "individually gated by --confirm-test-accounts / --signoff-ref regardless of this value.",
    )
    parser.add_argument(
        "--confirm-test-accounts",
        action="store_true",
        help="Required to run Phase 3 (vuln validation) tests — confirms disposable test accounts, not real customer data.",
    )
    parser.add_argument(
        "--signoff-ref",
        default=None,
        help="Required to run Phase 4 (HIGH RISK) tests — a reference to your written client authorization "
        "(ticket ID, email subject, doc name). Logged into scan_results.json for the evidence trail.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive per-test confirmation prompt for Phase 4 tests (still requires --signoff-ref). "
        "Use for scripted/CI runs where the operator has already reviewed and authorized the exact test list.",
    )
    parser.add_argument(
        "--definitions",
        default=str(Path(__file__).resolve().parent / "test_definitions.yaml"),
        help="Path to test_definitions.yaml",
    )
    parser.add_argument("--out", default="scan_results.json", help="Output JSON path")
    parser.add_argument("--timeout", type=int, default=120, help="Per-command timeout in seconds")
    args = parser.parse_args(argv)

    if not is_valid_target_url(args.target):
        parser.error("--target must be a shell-safe HTTP(S) URL without credentials, query, or fragment")

    defs = load_definitions(args.definitions)
    in_phase = [d for d in defs if d["phase"] <= args.max_phase]
    above_ceiling = [d for d in defs if d["phase"] > args.max_phase]

    runnable, blocked = [], []
    for d in in_phase:
        reason = gate_reason(d, args)
        (blocked if reason else runnable).append((d, reason) if reason else d)

    print(f"[vaptforge] target={args.target}")
    print(
        f"[vaptforge] {len(runnable)} tests to run, {len(blocked)} blocked by sign-off gate, "
        f"{len(above_ceiling)} above --max-phase\n"
    )

    results = []
    for d in runnable:
        cmd = d["command"].format(target=args.target)
        print(f"[{d['wstg_id']}] {d['name']}")
        print(f"    $ {cmd}")
        proc = run_command(cmd, timeout=args.timeout)
        combined_output = proc.stdout + proc.stderr
        verdict, note = score_result(d, combined_output, proc.returncode)
        print(f"    -> {verdict}\n")
        results.append(
            {
                "wstg_id": d["wstg_id"],
                "name": d["name"],
                "phase": d["phase"],
                "component": d.get("component"),
                "element": d.get("element"),
                "tool": d["tool"],
                "command": cmd,
                "result": verdict,
                "note": note,
                "caution": d.get("caution"),
                "raw_output": combined_output,
                "exit_code": proc.returncode,
                "signoff_ref": args.signoff_ref if d["phase"] >= HIGH_RISK_PHASE else None,
            }
        )

    for d, reason in blocked:
        print(f"[{d['wstg_id']}] {d['name']} -> BLOCKED: {reason}\n")
        results.append(
            {
                "wstg_id": d["wstg_id"],
                "name": d["name"],
                "phase": d["phase"],
                "component": d.get("component"),
                "element": d.get("element"),
                "tool": d["tool"],
                "command": None,
                "result": "Blocked (sign-off gate)",
                "note": reason,
                "caution": d.get("caution"),
                "raw_output": "",
                "exit_code": None,
                "signoff_ref": None,
            }
        )

    for d in above_ceiling:
        results.append(
            {
                "wstg_id": d["wstg_id"],
                "name": d["name"],
                "phase": d["phase"],
                "component": d.get("component"),
                "element": d.get("element"),
                "tool": d["tool"],
                "command": None,
                "result": f"Skipped (phase {d['phase']} > --max-phase {args.max_phase})",
                "note": d.get("caution"),
                "caution": d.get("caution"),
                "raw_output": "",
                "exit_code": None,
                "signoff_ref": None,
            }
        )

    surface = attack_surface_coverage(defs)
    print("[vaptforge] Attack Surface Mapping coverage (full catalog, not just this run):")
    for component, info in surface["by_component"].items():
        covered_n = len(info["elements_covered"])
        total_n = len(info["elements_total"])
        print(f"    {component}: {covered_n}/{total_n} elements have at least one test")
        if info["elements_untested"]:
            print(f"        untested: {', '.join(info['elements_untested'])}")
    if surface["untagged_tests"]:
        print(f"    (untagged tests, not counted above: {', '.join(surface['untagged_tests'])})")

    out = {
        "target": args.target,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "max_phase": args.max_phase,
        "signoff_ref": args.signoff_ref,
        "attack_surface_coverage": surface,
        "results": results,
    }
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"[vaptforge] wrote {args.out}")


if __name__ == "__main__":
    main()

import argparse

from .report import build_report


def main():
    parser = argparse.ArgumentParser(prog="vaptforge-report")
    parser.add_argument("--results", required=True, help="Path to Layer 1 scan_results.json")
    parser.add_argument(
        "--template",
        help="Optional path to a clean cover-only .docx template (defaults to the bundled Jamaa template)",
    )
    parser.add_argument("--out", default="report.docx", help="Output Word document path")
    parser.add_argument(
        "--prepared-by",
        help="Organization name shown on the cover (defaults to the template value)",
    )
    args = parser.parse_args()
    try:
        output = build_report(args.results, args.template, args.out, prepared_by=args.prepared_by)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"vaptforge-report: error: {exc}\n")
    print(f"[vaptforge-report] wrote {output}")


if __name__ == "__main__":
    main()

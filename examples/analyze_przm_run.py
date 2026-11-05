"""Kept for old instructions. Use:  python -m runoffwatch run <run folder>"""
import sys

from runoffwatch.report import analyze_run

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    analyze_run(sys.argv[1], "examples/output")

"""Placeholder helper script.

Candidate should adapt this script to their own endpoint + payload contract.
"""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    print(
        "TODO(candidate): update this script to call your chosen query endpoint at "
        f"{args.base_url}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

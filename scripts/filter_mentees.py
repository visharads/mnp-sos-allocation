#!/usr/bin/env python3
"""
Reads mentee_preferences_detailed.csv, removes all entries for mentees
who have no valid SOP Score, and writes the cleaned result to mentee.csv.

Usage:
    python3 filter_mentees.py
    python3 filter_mentees.py --input path/to/mentee_preferences_detailed.csv
                              --output path/to/mentee.csv

A mentee is dropped entirely (all their preference rows) if no row for
that mentee contains a numeric SOP Score in the range 0.0 – 10.0.
"""

import csv
import re
import argparse


def normalize_header(v):
    return re.sub(r"[^a-z0-9]+", "", (v or "").strip().lower())


def get_cell(row, header_map, candidates):
    for c in candidates:
        key = header_map.get(normalize_header(c))
        if key is not None:
            return row.get(key, "").strip()
    return ""


def has_valid_sop(value):
    try:
        score = float(value.strip())
        return 0.0 <= score <= 10.0
    except (ValueError, TypeError, AttributeError):
        return False


def main():
    parser = argparse.ArgumentParser(description="Filter mentees without SOP scores.")
    parser.add_argument(
        "--input", default="mentee_preferences_detailed.csv",
        help="Input file (default: mentee_preferences_detailed.csv)"
    )
    parser.add_argument(
        "--output", default="mentee.csv",
        help="Output file (default: mentee.csv)"
    )
    args = parser.parse_args()

    # ── Pass 1: find which mentees have at least one valid SOP Score ──────────
    mentees_with_sop = set()

    with open(args.input, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        header_map = {normalize_header(name): name for name in fieldnames}

        for row in reader:
            roll = get_cell(row, header_map, ["Mentee Roll No", "Roll Number"])
            name = get_cell(row, header_map, ["Mentee Name", "Full Name"])
            sop  = get_cell(row, header_map, ["SOP Score"])
            key  = (roll or name).strip().lower()
            if key and has_valid_sop(sop):
                mentees_with_sop.add(key)

    # ── Pass 2: copy rows belonging to mentees who have a valid SOP Score ─────
    kept_rows  = []
    dropped_keys = set()

    with open(args.input, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        header_map = {normalize_header(name): name for name in fieldnames}

        for row in reader:
            roll = get_cell(row, header_map, ["Mentee Roll No", "Roll Number"])
            name = get_cell(row, header_map, ["Mentee Name", "Full Name"])
            key  = (roll or name).strip().lower()
            if key in mentees_with_sop:
                kept_rows.append(row)
            else:
                dropped_keys.add(key)

    # ── Write output ──────────────────────────────────────────────────────────
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept_rows)

    total_mentees  = len(mentees_with_sop) + len(dropped_keys)
    print(f"Input : {args.input}")
    print(f"Output: {args.output}")
    print(f"  Total mentees found : {total_mentees}")
    print(f"  Kept  (have SOP)    : {len(mentees_with_sop)}")
    print(f"  Dropped (no SOP)    : {len(dropped_keys)}")
    if dropped_keys:
        print("\nDropped mentees:")
        for k in sorted(dropped_keys):
            print(f"  - {k}")


if __name__ == "__main__":
    main()
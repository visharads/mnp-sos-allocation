#!/usr/bin/env python3
"""
Build mentor->project-code mapping, clean mentee preferences,
and run a simple allocation algorithm producing `allocations.csv`.

Usage: python3 scripts/allocator.py

Required inputs (workspace root):
- topics.csv
- mentor.csv
- mentee_preferences_detailed.csv   <-- single mentee input

Outputs written to workspace root:
- mentor-project-code.csv
- mentee.csv                        (generated from mentee_preferences_detailed.csv)
- mentee-preferences-cleaned.csv
- allocations.csv
"""
import csv
import re
import sys
from collections import defaultdict
from difflib import get_close_matches


def normalize(s):
    if s is None:
        return ""
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s


def load_topics(path):
    code2topic = {}
    topic_names = []
    pat = re.compile(r"^\s*([A-Za-z]{1,3}\d{2,3})\s*,\s*(.+)$")
    with open(path, newline='', encoding='utf-8') as f:
        for line in f:
            line = line.strip('\n\r')
            m = pat.match(line)
            if m:
                code = m.group(1).strip()
                topic = m.group(2).strip()
                code2topic[code.upper()] = topic
                topic_names.append((normalize(topic), code.upper()))
    topic_map = {name: code for name, code in topic_names}
    return code2topic, topic_map


def parse_mentor_topics(mentor_row, topic_map):
    codes = set()
    for k, v in mentor_row.items():
        if not k:
            continue
        kl = k.lower()
        if 'topic' in kl:
            if not v:
                continue
            parts = re.split(r"[,;]\s*", v)
            for p in parts:
                p = p.strip()
                if not p:
                    continue
                if re.match(r'^[A-Za-z]{1,3}\d{2,3}$', p):
                    codes.add(p.upper())
                    continue
                norm = normalize(p)
                if norm in topic_map:
                    codes.add(topic_map[norm])
                else:
                    candidates = get_close_matches(norm, list(topic_map.keys()), n=1, cutoff=0.7)
                    if candidates:
                        codes.add(topic_map[candidates[0]])
    return sorted(codes)


def build_mentor_codes(mentor_csv, topic_map):
    mentors = []
    with open(mentor_csv, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get('Full Name') or row.get('Full name') or row.get('FullName') or ''
            codes = parse_mentor_topics(row, topic_map)
            mentors.append((name.strip(), codes))
    return mentors


def write_mentor_codes(out_path, mentors):
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Full Name', 'Project Codes'])
        for name, codes in mentors:
            writer.writerow([name, ";".join(codes)])


def generate_mentee_csv(detailed_path, out_path):
    """
    Convert mentee_preferences_detailed.csv (long format, one row per preference)
    into mentee.csv (wide format, one row per mentee).

    Input columns expected:
        Mentee Roll No, Mentee Name, Preference Number, Specific Category,
        SOP Score, Year

    Output columns written:
        Timestamp, Full Name, Year of study,
        PREFERENCE 1, PREFERENCE 2, PREFERENCE 3, PREFERENCE 4, PREFERENCE 5
    """
    grouped = {}
    order = []

    def normalize_header(v):
        return re.sub(r"[^a-z0-9]+", "", (v or '').strip().lower())

    with open(detailed_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        header_map = {normalize_header(name): name for name in (reader.fieldnames or [])}

        def get_cell(row, candidates):
            for c in candidates:
                key = header_map.get(normalize_header(c))
                if key is not None:
                    return row.get(key, '').strip()
            return ''

        for row in reader:
            roll = get_cell(row, ['Mentee Roll No', 'Roll Number'])
            name = get_cell(row, ['Mentee Name', 'Full Name'])
            pref_num_text = get_cell(row, ['Preference Number'])
            code = get_cell(row, ['Specific Category', 'Project ID'])
            year = get_cell(row, ['Year'])

            try:
                pref_num = int(pref_num_text)
            except ValueError:
                continue

            key = (roll or name).strip().lower()
            if not key:
                continue

            if key not in grouped:
                grouped[key] = {
                    'full_name': name,
                    'year': year,
                    'preferences': {},
                }
                order.append(key)

            entry = grouped[key]
            if code:
                entry['preferences'][pref_num] = code
            if year and not entry['year']:
                entry['year'] = year

    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Timestamp', 'Full Name', 'Year of study',
            'PREFERENCE 1', 'PREFERENCE 2', 'PREFERENCE 3',
            'PREFERENCE 4', 'PREFERENCE 5',
        ])
        for key in order:
            entry = grouped[key]
            prefs = [entry['preferences'].get(i, '') for i in range(1, 6)]
            writer.writerow(['', entry['full_name'], entry['year']] + prefs)

    print(f'Generated mentee.csv from {detailed_path} ({len(order)} mentees)')


def clean_mentees(mentee_csv, valid_codes):
    cleaned = []
    with open(mentee_csv, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        pref_cols = [c for c in reader.fieldnames if c and c.strip().upper().startswith('PREFERENCE')]
        for row in reader:
            name = row.get('Full Name') or row.get('Full name') or ''
            prefs = []
            for c in pref_cols[:5]:
                val = (row.get(c) or '').strip().upper()
                if val in ('', 'N/A', 'NA', 'NONE', 'NULL', '-'):
                    val = ''
                if val and val not in valid_codes:
                    val = ''
                prefs.append(val)
            cleaned.append((row.get('Timestamp', ''), name.strip(), prefs))
    return cleaned


def write_mentee_clean(out_path, cleaned):
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Timestamp', 'Full Name', 'Pref1', 'Pref2', 'Pref3', 'Pref4', 'Pref5'])
        for ts, name, prefs in cleaned:
            writer.writerow([ts, name] + prefs)


def allocate(cleaned_mentees, topic_capacity):
    allocations = []
    for ts, name, prefs in cleaned_mentees:
        assigned = ''
        pref_rank = ''
        for i, p in enumerate(prefs, start=1):
            if not p:
                continue
            cap = topic_capacity.get(p, 0)
            if cap > 0:
                assigned = p
                pref_rank = str(i)
                topic_capacity[p] = cap - 1
                break
        allocations.append((ts, name, assigned, pref_rank, prefs))
    return allocations


def write_allocations(out_path, allocations):
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Timestamp', 'Full Name', 'Assigned Code', 'Preference Rank',
                         'Pref1', 'Pref2', 'Pref3', 'Pref4', 'Pref5'])
        for ts, name, assigned, rank, prefs in allocations:
            writer.writerow([ts, name, assigned, rank] + prefs)


def main():
    import pathlib
    base = pathlib.Path(__file__).resolve().parents[1]
    topics_csv   = base / 'topics.csv'
    mentor_csv   = base / 'mentor.csv'
    detailed_csv = base / 'mentee_preferences_detailed.csv'
    mentee_csv   = base / 'mentee.csv'

    # --- Step 0: generate mentee.csv from the detailed file ---
    generate_mentee_csv(str(detailed_csv), str(mentee_csv))

    # --- Step 1: topics ---
    code2topic, topic_map = load_topics(str(topics_csv))
    print(f'Loaded {len(code2topic)} topic codes')

    # --- Step 2: mentors ---
    mentors = build_mentor_codes(str(mentor_csv), topic_map)
    write_mentor_codes(str(base / 'mentor-project-code.csv'), mentors)
    print(f'Wrote mentor-project-code.csv with {len(mentors)} mentors')

    # --- Step 3: clean mentees ---
    valid_codes = set(code2topic.keys())
    cleaned = clean_mentees(str(mentee_csv), valid_codes)
    write_mentee_clean(str(base / 'mentee-preferences-cleaned.csv'), cleaned)
    print(f'Wrote mentee-preferences-cleaned.csv with {len(cleaned)} entries')

    # --- Step 4: allocate ---
    mentor_counts = defaultdict(int)
    for _, codes in mentors:
        for c in codes:
            mentor_counts[c] += 1
    cap_per_mentor = 3
    topic_capacity = {c: mentor_counts.get(c, 0) * cap_per_mentor for c in valid_codes}
    non_zero = {k: v for k, v in topic_capacity.items() if v > 0}
    print('Non-zero capacities sample (first 20):', dict(list(non_zero.items())[:20]))

    allocations = allocate(cleaned, topic_capacity)
    write_allocations(str(base / 'allocations.csv'), allocations)
    print('Wrote allocations.csv')


if __name__ == '__main__':
    main()
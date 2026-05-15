import csv
import argparse
import os
import re
from collections import defaultdict


def normalize_text(value):
    return re.sub(r"\s+", " ", (value or '').strip().lower())


def normalize_header(value):
    return re.sub(r"[^a-z0-9]+", "", (value or '').strip().lower())


def get_row_value(row, header_map, candidates):
    for candidate in candidates:
        key = header_map.get(normalize_header(candidate))
        if key is not None:
            return row.get(key, '')
    return ''


def parse_seniority_rank(value):
    text = normalize_text(value)
    if not text:
        return 0
    if 'postdoc' in text or 'post doc' in text:
        return 7
    if 'phd' in text:
        return 6
    if 'alumnus' in text or 'alumni' in text:
        return 5
    if 'fifth' in text or '5th' in text:
        return 4
    if 'fourth' in text or '4th' in text:
        return 3
    if 'third' in text or '3rd' in text:
        return 2
    if 'second' in text or '2nd' in text:
        return 1
    if 'first' in text or '1st' in text:
        return 0
    return 0


def score_sop(sop_text):
    text = (sop_text or '').strip()
    if not text:
        return 0.0

    words = re.findall(r"\b\w+\b", text.lower())
    word_count = len(words)
    score = 3.5

    if word_count >= 60:
        score += 1.0
    if word_count >= 120:
        score += 0.8
    if word_count >= 220:
        score += 0.7

    concrete_terms = [
        'project', 'research', 'course', 'internship', 'thesis', 'paper',
        'workshop', 'lab', 'implementation', 'analysis', 'model', 'proof',
        'coding', 'experiment', 'algorithm', 'reading', 'study'
    ]
    evidence_terms = [
        'because', 'since', 'therefore', 'for example', 'previous', 'experience',
        'have worked', 'done', 'learned', 'want to', 'hope to', 'aim to'
    ]
    goal_terms = [
        'understand', 'learn', 'explore', 'deepen', 'improve', 'gain', 'build',
        'develop', 'strengthen', 'contribute', 'grow'
    ]

    lower = text.lower()
    score += min(1.0, sum(1 for term in concrete_terms if term in lower) * 0.15)
    score += min(1.0, sum(1 for term in evidence_terms if term in lower) * 0.2)
    score += min(1.0, sum(1 for term in goal_terms if term in lower) * 0.15)

    if any(ch.isdigit() for ch in text):
        score += 0.4
    if len(set(words)) >= max(20, word_count // 2):
        score += 0.4
    if 'want this one only' in lower or 'pls dedo' in lower or lower.strip() == 'please':
        score -= 0.6

    return max(0.0, min(10.0, round(score, 1)))


def load_mentee_years(file_path):
    year_map = {}
    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        header_map = {normalize_header(name): name for name in (reader.fieldnames or [])}
        for row in reader:
            roll = get_row_value(row, header_map, ['Roll Number']).strip()
            name = get_row_value(row, header_map, ['Full Name']).strip()
            year_text = get_row_value(row, header_map, ['Year of study', 'Year']).strip()
            if roll and year_text:
                year_map[normalize_text(roll)] = year_text
            if name and year_text:
                year_map[normalize_text(name)] = year_text
    return year_map

def load_mentee_preferences(file_path, fallback_year_path='mentee.csv'):
    """Load long-form mentee responses and group preferences by mentee."""
    year_map = load_mentee_years(fallback_year_path) if fallback_year_path and os.path.exists(fallback_year_path) else {}
    grouped = {}
    order = []
    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        header_map = {normalize_header(name): name for name in (reader.fieldnames or [])}
        for row in reader:
            roll = get_row_value(row, header_map, ['Mentee Roll No', 'Roll Number']).strip()
            name = get_row_value(row, header_map, ['Mentee Name', 'Full Name']).strip()
            pref_num_text = get_row_value(row, header_map, ['Preference Number']).strip()
            code = get_row_value(row, header_map, ['Specific Category', 'Project ID', 'Assigned Code']).strip()
            sop_text = get_row_value(row, header_map, ['SOP']).strip()
            year_text = get_row_value(row, header_map, ['Year']).strip()

            try:
                pref_num = int(pref_num_text)
            except ValueError:
                continue

            key = normalize_text(roll or name)
            if key not in grouped:
                grouped[key] = {
                    'roll_number': roll,
                    'full_name': name,
                    'year_text': '',
                    'preferences': {},
                    'sop_text': sop_text,
                }
                order.append(key)

            entry = grouped[key]
            if code:
                entry['preferences'][pref_num] = code
            if sop_text and not entry['sop_text']:
                entry['sop_text'] = sop_text
            if year_text and year_text.strip().lower() not in {'other', 'na', 'n/a', '-', 'none'} and not entry['year_text']:
                entry['year_text'] = year_text.strip()

    mentees = []
    for key in order:
        entry = grouped[key]
        fallback_year = year_map.get(normalize_text(entry['roll_number'])) or year_map.get(normalize_text(entry['full_name'])) or ''
        year_text = entry['year_text'] or fallback_year
        prefs = [entry['preferences'].get(i, '').strip() for i in range(1, 6)]
        prefs = [p for p in prefs if p]
        mentees.append({
            'roll_number': entry['roll_number'],
            'full_name': entry['full_name'],
            'year_text': year_text,
            'seniority_rank': parse_seniority_rank(year_text),
            'preferences': prefs,
            'sop_text': entry['sop_text'],
            'sop_score': score_sop(entry['sop_text']),
            'assigned_code': None,
            'assigned_mentor': None,
            'preference_rank': None,
            'assigned_mentor_seniority': None
        })
    return mentees


def load_mentor_years(file_path):
    mentor_years = {}
    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get('Full Name', '').strip()
            if not name:
                continue
            mentor_years[normalize_text(name)] = row.get('Current Year at IIT Bombay (as of April 2025)', '').strip()
    return mentor_years

def load_mentor_codes(file_path, mentor_meta_path='mentor.csv'):
    """Load mentor expertise areas and calculate capacity per code"""
    mentor_years = load_mentor_years(mentor_meta_path)
    mentors = {}
    code_to_mentors = defaultdict(list)
    # Support multiple mentor-code file formats. Auto-detect header names.
    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        header_map = {normalize_header(name): name for name in (reader.fieldnames or [])}
        # candidate header names for mentor name and codes
        name_candidates = ['fullname', 'full_name', 'mentor_name', 'mentor', 'name']
        code_candidates = ['projectcodes', 'project_codes', 'project codes', 'project code', 'project', 'codes', 'topic_code', 'topic codes', 'topiccodes', 'topic_code']

        def get_cell(row, candidates):
            for c in candidates:
                key = header_map.get(normalize_header(c))
                if key is not None:
                    return row.get(key, '').strip()
            return ''

        for row in reader:
            mentor_name = get_cell(row, name_candidates)
            codes_str = get_cell(row, code_candidates)
            # fallback: if file uses 'Project Codes' header
            if not mentor_name:
                mentor_name = row.get('Full Name', '') or row.get('mentor_name', '') or ''
                mentor_name = mentor_name.strip()
            if not codes_str:
                # try other common keys
                codes_str = row.get('Project Codes', '') or row.get('ProjectCodes', '') or ''
                codes_str = codes_str.strip()

            # normalize separators and split
            if codes_str:
                # replace commas with semicolons to be safe
                codes = [c.strip() for c in re.split(r'[;,]', codes_str) if c.strip()]
            else:
                codes = []

            if mentor_name:
                mentor_seniority = parse_seniority_rank(mentor_years.get(normalize_text(mentor_name), ''))
                mentors[mentor_name] = {
                    'codes': [c for c in codes if c],
                    'assigned': 0,
                    'codes_assigned': set(),
                    'seniority_rank': mentor_seniority,
                    'seniority_text': mentor_years.get(normalize_text(mentor_name), '')
                }
                for code in mentors[mentor_name]['codes']:
                    code_to_mentors[code].append(mentor_name)

    total_capacity = len(mentors) * 8
    return mentors, code_to_mentors, total_capacity

def allocate_mentees(mentees, mentors, code_to_mentors, max_codes_per_mentor=2, mentor_capacity=8):
    """
    Mentor-centric allocation:
      - Each mentor can take up to 8 mentees total (across all their codes)
      - Prefer assigning a mentee to a mentor who already mentors that code
      - Prefer mentors with fewer distinct codes assigned to avoid spreading mentors
      - Multi-pass across preference ranks; after passes, fallback-assign everyone to any mentor with capacity
    """
    ordered_mentees = sorted(
        list(enumerate(mentees)),
        key=lambda item: (-item[1]['sop_score'], -item[1]['seniority_rank'], item[0])
    )
    unassigned = [idx for idx, _ in ordered_mentees]

    # Helper to choose best mentor for a given code
    def choose_mentor_for_code(code, mentee):
        # Prefer mentors who explicitly listed the code and have capacity.
        # Do NOT allow off-topic assignment: if no mentor lists this code, return None.
        candidates = [
            m for m in code_to_mentors.get(code, [])
            if mentors[m]['assigned'] < mentor_capacity
        ]
        if not candidates:
            return None

        # Prefer candidates already mentoring this code
        # Filter out mentors where adding this code would exceed max distinct codes
        candidates = [m for m in candidates if (code in mentors[m]['codes_assigned']) or (len(mentors[m]['codes_assigned']) < max_codes_per_mentor)]
        if not candidates:
            return None

        already = [m for m in candidates if code in mentors[m]['codes_assigned']]
        if already:
            # choose the one with smallest assigned count
            return min(already, key=lambda x: (-mentors[x]['seniority_rank'], mentors[x]['assigned'], len(mentors[x]['codes_assigned'])))

        # otherwise choose the most senior eligible mentor, then the least loaded one
        return min(candidates, key=lambda x: (-mentors[x]['seniority_rank'], mentors[x]['assigned'], len(mentors[x]['codes_assigned'])))

    # Passes for preferences 1..5
    for pref_rank in range(5):
        newly_assigned = []
        for idx in list(unassigned):
            mentee = mentees[idx]
            if pref_rank < len(mentee['preferences']):
                code = mentee['preferences'][pref_rank]
                mentor_name = choose_mentor_for_code(code, mentee)
                if mentor_name:
                    # assign
                    mentee['assigned_code'] = code
                    mentee['assigned_mentor'] = mentor_name
                    mentee['preference_rank'] = pref_rank + 1
                    mentee['assigned_mentor_seniority'] = mentors[mentor_name]['seniority_rank']
                    mentors[mentor_name]['assigned'] += 1
                    mentors[mentor_name]['codes_assigned'].add(code)
                    newly_assigned.append(idx)
                    unassigned.remove(idx)

        print(f"Preference Rank {pref_rank + 1}: Assigned {len(newly_assigned)} mentees")

    # Fallback: assign remaining unassigned mentees to any mentor with capacity
    if unassigned:
        print(f"Fallback assigning {len(unassigned)} unassigned mentees to any available mentors...")
        # Prepare list of mentors with capacity
        mentors_with_capacity = [m for m in mentors.keys() if mentors[m]['assigned'] < mentor_capacity]
        # sort by seniority first, then fewest total assigned
        mentors_with_capacity.sort(key=lambda x: (-mentors[x]['seniority_rank'], mentors[x]['assigned'], len(mentors[x]['codes_assigned'])))

        for idx in list(unassigned):
            mentee = mentees[idx]
            assigned = False
            # Try to find a mentor among mentors_with_capacity who offers any of mentee's prefs
            for code in mentee['preferences']:
                for m in mentors_with_capacity:
                    if code in mentors[m]['codes'] and mentors[m]['assigned'] < mentor_capacity:
                        mentee['assigned_code'] = code
                        mentee['assigned_mentor'] = m
                        mentee['preference_rank'] = mentee.get('preference_rank') or 0
                        mentee['assigned_mentor_seniority'] = mentors[m]['seniority_rank']
                        mentors[m]['assigned'] += 1
                        mentors[m]['codes_assigned'].add(code)
                        assigned = True
                        break
                if assigned:
                    break

            # If still not assigned here, do NOT assign off-topic; leave unassigned.

            # update mentors_with_capacity ordering (in case someone's full)
            mentors_with_capacity = [m for m in mentors_with_capacity if mentors[m]['assigned'] < mentor_capacity]
            mentors_with_capacity.sort(key=lambda x: (len(mentors[x]['codes_assigned']), mentors[x]['assigned']))
            if mentee['assigned_mentor']:
                unassigned.remove(idx)

    # Final report of any remaining unassigned (should be 0 if capacity sufficient)
    print(f"\nFinal unassigned mentees: {len(unassigned)}")
    return mentees, mentors

def write_allocations(mentees, output_path):
    """Write allocation results to CSV"""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['Roll Number', 'Full Name', 'Assigned Mentor', 'Assigned Code', 'Preference Rank', 'SOP Score', 'Mentee Year', 'Assigned Mentor Seniority', 'Pref1', 'Pref2', 'Pref3', 'Pref4', 'Pref5']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for mentee in mentees:
            writer.writerow({
                'Roll Number': mentee['roll_number'],
                'Full Name': mentee['full_name'],
                'Assigned Mentor': mentee.get('assigned_mentor', '') or '',
                'Assigned Code': mentee['assigned_code'] or '',
                'Preference Rank': mentee['preference_rank'] or '',
                'SOP Score': mentee.get('sop_score', ''),
                'Mentee Year': mentee.get('year_text', ''),
                'Assigned Mentor Seniority': mentee.get('assigned_mentor_seniority', '') or '',
                'Pref1': mentee['preferences'][0] if len(mentee['preferences']) > 0 else '',
                'Pref2': mentee['preferences'][1] if len(mentee['preferences']) > 1 else '',
                'Pref3': mentee['preferences'][2] if len(mentee['preferences']) > 2 else '',
                'Pref4': mentee['preferences'][3] if len(mentee['preferences']) > 3 else '',
                'Pref5': mentee['preferences'][4] if len(mentee['preferences']) > 4 else ''
            })

def generate_report(mentees):
    """Generate allocation report"""
    assigned_count = sum(1 for m in mentees if m['assigned_code'])
    unassigned_count = len(mentees) - assigned_count
    
    # Count by preference rank
    rank_counts = defaultdict(int)
    for mentee in mentees:
        if mentee['preference_rank']:
            rank_counts[mentee['preference_rank']] += 1
    
    print(f"\n{'='*60}")
    print(f"ALLOCATION REPORT")
    print(f"{'='*60}")
    print(f"Total mentees: {len(mentees)}")
    print(f"Assigned: {assigned_count} ({100*assigned_count/len(mentees):.1f}%)")
    print(f"Unassigned: {unassigned_count} ({100*unassigned_count/len(mentees):.1f}%)")
    scored = [m for m in mentees if m.get('sop_score') is not None]
    if scored:
        average_score = sum(m['sop_score'] for m in scored) / len(scored)
        print(f"Average SOP score: {average_score:.2f}/10")
    print(f"\nBreakdown by preference rank:")
    for rank in sorted(rank_counts.keys()):
        count = rank_counts[rank]
        pct = 100 * count / assigned_count if assigned_count > 0 else 0
        print(f"  Preference {rank}: {count} mentees ({pct:.1f}% of assigned)")
    
    # Most popular assigned codes
    code_counts = defaultdict(int)
    for mentee in mentees:
        if mentee['assigned_code']:
            code_counts[mentee['assigned_code']] += 1
    
    print(f"\nTop 10 most assigned codes:")
    for code, count in sorted(code_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {code}: {count} mentees")
    
    print(f"{'='*60}\n")


def write_stats(mentees, mentors, prefix='allocations'):
    """Write allocation statistics and mentor load CSVs."""
    total = len(mentees)
    assigned_count = sum(1 for m in mentees if m['assigned_code'])
    rank_counts = defaultdict(int)
    code_counts = defaultdict(int)
    mentor_counts = defaultdict(int)
    score_buckets = defaultdict(int)

    for m in mentees:
        if m['assigned_code']:
            code_counts[m['assigned_code']] += 1
            rank = m.get('preference_rank') or 0
            rank_counts[rank] += 1
            mentor = m.get('assigned_mentor') or ''
            if mentor:
                mentor_counts[mentor] += 1
            score_buckets[int(round(m.get('sop_score') or 0))] += 1

    # write simple text summary
    summary_path = f"{prefix}_stats.txt"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write('ALLOCATION STATISTICS\n')
        f.write('='*40 + '\n')
        f.write(f'Total mentees: {total}\n')
        f.write(f'Assigned: {assigned_count} ({100*assigned_count/total:.1f}%)\n')
        f.write(f'Unassigned: {total-assigned_count} ({100*(total-assigned_count)/total:.1f}%)\n\n')
        f.write('Breakdown by preference rank:\n')
        for rank in sorted(rank_counts.keys()):
            if rank == 0:
                f.write(f'  Unspecified/Assigned by fallback: {rank_counts[rank]}\n')
            else:
                f.write(f'  Preference {rank}: {rank_counts[rank]}\n')
        f.write('\nSOP score buckets:\n')
        for score in sorted(score_buckets.keys(), reverse=True):
            f.write(f'  Score {score}: {score_buckets[score]}\n')
        f.write('\nTop 20 assigned codes:\n')
        for code, cnt in sorted(code_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
            f.write(f'  {code}: {cnt}\n')

    # write mentor loads CSV
    mentor_csv = f"{prefix}_mentor_loads.csv"
    with open(mentor_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Mentor', 'Assigned Mentees', 'Distinct Codes'])
        for name, info in sorted(mentors.items(), key=lambda x: x[1]['assigned'], reverse=True):
            writer.writerow([name, info['assigned'], len(info['codes_assigned'])])

    print(f"Wrote stats: {summary_path} and {mentor_csv}")

def main():
    parser = argparse.ArgumentParser(description='Allocate mentees to mentors using preference and SOP scoring.')
    parser.add_argument('--mentor-capacity', type=int, default=8, help='Maximum number of mentees per mentor (default: 8)')
    parser.add_argument('--max-codes-per-mentor', type=int, default=4, help='Maximum distinct codes per mentor (default: 4)')
    parser.add_argument('--output-prefix', default='allocations', help='Prefix for output files (default: allocations)')
    args = parser.parse_args()

    print("Loading mentee preferences...")
    mentees = load_mentee_preferences('mentee_preferences_detailed.csv')
    print(f"  Loaded {len(mentees)} mentees")
    print("  Scored SOPs out of 10 using a lightweight rubric model")
    
    print("\nLoading mentor expertise areas from mentor.csv (topic codes)...")
    mentors, code_to_mentors, total_capacity = load_mentor_codes('mentor.csv', mentor_meta_path='mentor.csv')
    print(f"  Loaded {len(mentors)} mentors and {len(code_to_mentors)} unique project codes")
    print(f"  Total capacity (mentors * 8): {total_capacity} slots across all mentors")
    
    print("\nAllocating mentees to preferences...")
    print("Using priority-based algorithm:")
    print("  Pass 1: Assign to 1st preference")
    print("  Pass 2: Assign to 2nd preference")
    print("  Pass 3: Assign to 3rd preference, etc.\n")
    
    mentees, mentors = allocate_mentees(
        mentees,
        mentors,
        code_to_mentors,
        max_codes_per_mentor=args.max_codes_per_mentor,
        mentor_capacity=args.mentor_capacity,
    )
    
    print("\nWriting allocation results...")
    output_csv = f"{args.output_prefix}.csv"
    write_allocations(mentees, output_csv)
    print(f"  Saved to {output_csv}")
    
    generate_report(mentees)

    # Mentor load summary
    print("Mentor load summary (top 10 busiest mentors):")
    mentor_list = sorted(mentors.items(), key=lambda x: x[1]['assigned'], reverse=True)
    for name, info in mentor_list[:10]:
        print(f"  {name}: {info['assigned']} mentees, {len(info['codes_assigned'])} distinct codes")
    # write stats files
    write_stats(mentees, mentors, prefix=args.output_prefix)
if __name__ == '__main__':
    main()

import csv
from collections import defaultdict

def load_mentee_preferences(file_path):
    """Load mentee preferences from cleaned file"""
    mentees = []
    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            prefs = [
                row.get('Pref1', '').strip(),
                row.get('Pref2', '').strip(),
                row.get('Pref3', '').strip(),
                row.get('Pref4', '').strip(),
                row.get('Pref5', '').strip()
            ]
            # Filter out empty preferences
            prefs = [p for p in prefs if p]
            mentees.append({
                'roll_number': row.get('Roll Number', '').strip(),
                'full_name': row.get('Full Name', '').strip(),
                'preferences': prefs,
                'assigned_code': None,
                'preference_rank': None
            })
    return mentees

def load_mentor_codes(file_path):
    """Load mentor expertise areas and calculate capacity per code"""
    mentors = {}
    code_to_mentors = defaultdict(list)

    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            mentor_name = row.get('Full Name', '').strip()
            codes_str = row.get('Project Codes', '').strip()
            codes = [c.strip() for c in codes_str.split(';')] if codes_str else []
            if mentor_name:
                mentors[mentor_name] = {
                    'codes': [c for c in codes if c],
                    'assigned': 0,
                    'codes_assigned': set()
                }
                for code in mentors[mentor_name]['codes']:
                    code_to_mentors[code].append(mentor_name)

    total_capacity = len(mentors) * 8
    return mentors, code_to_mentors, total_capacity

def allocate_mentees(mentees, mentors, code_to_mentors, max_codes_per_mentor=2):
    """
    Mentor-centric allocation:
      - Each mentor can take up to 8 mentees total (across all their codes)
      - Prefer assigning a mentee to a mentor who already mentors that code
      - Prefer mentors with fewer distinct codes assigned to avoid spreading mentors
      - Multi-pass across preference ranks; after passes, fallback-assign everyone to any mentor with capacity
    """
    unassigned = list(range(len(mentees)))

    # Helper to choose best mentor for a given code
    def choose_mentor_for_code(code):
        candidates = [m for m in code_to_mentors.get(code, []) if mentors[m]['assigned'] < 8]
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
            return min(already, key=lambda x: (mentors[x]['assigned'], len(mentors[x]['codes_assigned'])))

        # otherwise choose mentor with fewest distinct codes assigned, then fewest assigned mentees
        return min(candidates, key=lambda x: (len(mentors[x]['codes_assigned']), mentors[x]['assigned']))

    # Passes for preferences 1..5
    for pref_rank in range(5):
        newly_assigned = []
        for idx in list(unassigned):
            mentee = mentees[idx]
            if pref_rank < len(mentee['preferences']):
                code = mentee['preferences'][pref_rank]
                mentor_name = choose_mentor_for_code(code)
                if mentor_name:
                    # assign
                    mentee['assigned_code'] = code
                    mentee['assigned_mentor'] = mentor_name
                    mentee['preference_rank'] = pref_rank + 1
                    mentors[mentor_name]['assigned'] += 1
                    mentors[mentor_name]['codes_assigned'].add(code)
                    newly_assigned.append(idx)
                    unassigned.remove(idx)

        print(f"Preference Rank {pref_rank + 1}: Assigned {len(newly_assigned)} mentees")

    # Fallback: assign remaining unassigned mentees to any mentor with capacity
    if unassigned:
        print(f"Fallback assigning {len(unassigned)} unassigned mentees to any available mentors...")
        # Prepare list of mentors with capacity
        mentors_with_capacity = [m for m in mentors.keys() if mentors[m]['assigned'] < 8]
        # sort by fewest distinct codes assigned then fewest total assigned
        mentors_with_capacity.sort(key=lambda x: (len(mentors[x]['codes_assigned']), mentors[x]['assigned']))

        for idx in list(unassigned):
            mentee = mentees[idx]
            assigned = False
            # Try to find a mentor among mentors_with_capacity who offers any of mentee's prefs
            for code in mentee['preferences']:
                for m in mentors_with_capacity:
                    if code in mentors[m]['codes'] and mentors[m]['assigned'] < 8:
                        mentee['assigned_code'] = code
                        mentee['assigned_mentor'] = m
                        mentee['preference_rank'] = mentee.get('preference_rank') or 0
                        mentors[m]['assigned'] += 1
                        mentors[m]['codes_assigned'].add(code)
                        assigned = True
                        break
                if assigned:
                    break

            if not assigned:
                # assign to the best mentor available and pick their first offered code
                best = None
                for m in mentors_with_capacity:
                    if mentors[m]['assigned'] < 8:
                        best = m
                        break
                if best:
                    code = mentors[best]['codes'][0] if mentors[best]['codes'] else ''
                    mentee['assigned_code'] = code
                    mentee['assigned_mentor'] = best
                    mentee['preference_rank'] = mentee.get('preference_rank') or 0
                    mentors[best]['assigned'] += 1
                    if code:
                        mentors[best]['codes_assigned'].add(code)

            # update mentors_with_capacity ordering (in case someone's full)
            mentors_with_capacity = [m for m in mentors_with_capacity if mentors[m]['assigned'] < 8]
            mentors_with_capacity.sort(key=lambda x: (len(mentors[x]['codes_assigned']), mentors[x]['assigned']))
            if mentee['assigned_mentor']:
                unassigned.remove(idx)

    # Final report of any remaining unassigned (should be 0 if capacity sufficient)
    print(f"\nFinal unassigned mentees: {len(unassigned)}")
    return mentees, mentors

def write_allocations(mentees, output_path):
    """Write allocation results to CSV"""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['Roll Number', 'Full Name', 'Assigned Mentor', 'Assigned Code', 'Preference Rank', 'Pref1', 'Pref2', 'Pref3', 'Pref4', 'Pref5']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for mentee in mentees:
            writer.writerow({
                'Roll Number': mentee['roll_number'],
                'Full Name': mentee['full_name'],
                'Assigned Mentor': mentee.get('assigned_mentor', '') or '',
                'Assigned Code': mentee['assigned_code'] or '',
                'Preference Rank': mentee['preference_rank'] or '',
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

def main():
    print("Loading mentee preferences...")
    mentees = load_mentee_preferences('mentee-preferences-cleaned.csv')
    print(f"  Loaded {len(mentees)} mentees")
    
    print("\nLoading mentor expertise areas...")
    mentors, code_to_mentors, total_capacity = load_mentor_codes('mentor-project-code.csv')
    print(f"  Loaded {len(mentors)} mentors and {len(code_to_mentors)} unique project codes")
    print(f"  Total capacity (mentors * 8): {total_capacity} slots across all mentors")
    
    print("\nAllocating mentees to preferences...")
    print("Using priority-based algorithm:")
    print("  Pass 1: Assign to 1st preference")
    print("  Pass 2: Assign to 2nd preference")
    print("  Pass 3: Assign to 3rd preference, etc.\n")
    
    mentees, mentors = allocate_mentees(mentees, mentors, code_to_mentors)
    
    print("\nWriting allocation results...")
    write_allocations(mentees, 'allocations.csv')
    print("  Saved to allocations.csv")
    
    generate_report(mentees)

    # Mentor load summary
    print("Mentor load summary (top 10 busiest mentors):")
    mentor_list = sorted(mentors.items(), key=lambda x: x[1]['assigned'], reverse=True)
    for name, info in mentor_list[:10]:
        print(f"  {name}: {info['assigned']} mentees, {len(info['codes_assigned'])} distinct codes")
if __name__ == '__main__':
    main()

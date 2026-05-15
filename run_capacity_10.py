import copy
from allocation_algorithm import (
    load_mentee_preferences,
    load_mentor_codes,
    allocate_mentees,
    write_allocations,
    write_stats,
)
import csv


def write_unassigned_csv(mentees, code_to_mentors, mentors, mentor_capacity, path):
    rows = []
    for m in mentees:
        if not m.get('assigned_code'):
            prefs = m.get('preferences', [])
            reason = 'unknown'
            if not prefs:
                reason = 'no preferences listed'
            else:
                if not any(p in code_to_mentors for p in prefs):
                    reason = 'no mentor offers preferred codes'
                else:
                    all_full = True
                    for p in prefs:
                        for mm in code_to_mentors.get(p, []):
                            if mentors[mm]['assigned'] < mentor_capacity:
                                all_full = False
                                break
                        if not all_full:
                            break
                    if all_full:
                        reason = 'capacity full for preferred codes'
                    else:
                        reason = 'other (matching constraints)'

            rows.append({
                'Roll Number': m.get('roll_number', ''),
                'Full Name': m.get('full_name', ''),
                'Pref1': prefs[0] if len(prefs) > 0 else '',
                'Pref2': prefs[1] if len(prefs) > 1 else '',
                'Pref3': prefs[2] if len(prefs) > 2 else '',
                'Pref4': prefs[3] if len(prefs) > 3 else '',
                'Pref5': prefs[4] if len(prefs) > 4 else '',
                'SOP Score': m.get('sop_score', ''),
                'Reason': reason,
            })
    with open(path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['Roll Number', 'Full Name', 'Pref1', 'Pref2', 'Pref3', 'Pref4', 'Pref5', 'SOP Score', 'Reason']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    print(f'Wrote unassigned list to {path} ({len(rows)} rows)')


def run():
    mentee_file = 'mentee_preferences_detailed.csv'
    mentor_file = 'mentor.csv'

    mentees = load_mentee_preferences(mentee_file)
    mentors, code_to_mentors, _ = load_mentor_codes(mentor_file, mentor_meta_path=mentor_file)

    print('Running allocation with max_codes_per_mentor=4 and mentor_capacity=10')
    # reset mentor assigned counts
    mentors_run = {k: v.copy() for k, v in mentors.items()}
    for k in mentors_run:
        mentors_run[k]['assigned'] = 0
        mentors_run[k]['codes_assigned'] = set()

    mentees_run = copy.deepcopy(mentees)
    mentees_run, mentors_run = allocate_mentees(mentees_run, mentors_run, code_to_mentors, max_codes_per_mentor=4, mentor_capacity=10)

    write_allocations(mentees_run, 'allocations_capacity10.csv')
    write_stats(mentees_run, mentors_run, prefix='allocations_capacity10')
    write_unassigned_csv(mentees_run, code_to_mentors, mentors_run, 10, 'allocations_unassigned_capacity10.csv')

    total = len(mentees_run)
    assigned = sum(1 for m in mentees_run if m.get('assigned_code'))
    avg = sum(m.get('sop_score', 0) for m in mentees_run) / total if total else 0
    print(f'Completed: total={total}, assigned={assigned}, assigned%={100*assigned/total:.1f}%, avg_SOP={avg:.2f}')


if __name__ == '__main__':
    run()

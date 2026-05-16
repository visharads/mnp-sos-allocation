import copy
import csv
import pathlib
from allocation_algorithm import (
    load_mentee_preferences,
    load_mentor_codes,
    allocate_mentees,
    write_allocations,
    write_stats,
)

# Resolve paths relative to this script so it works regardless of where
# the command is run from. Inputs sit one level up (project root);
# outputs are written there too.
BASE = pathlib.Path(__file__).resolve().parent.parent

MENTEE_FILE  = str(BASE / 'mentee_preferences_detailed.csv')
MENTOR_FILE  = str(BASE / 'mentor.csv')

OUT_ALLOC    = str(BASE / 'allocations_capacity10.csv')
OUT_STATS    = str(BASE / 'allocations_capacity10')          # write_stats appends _stats.txt / _mentor_loads.csv
OUT_UNASSIGN = str(BASE / 'allocations_unassigned_capacity10.csv')

MENTOR_CAPACITY    = 10
MAX_CODES_PER_MENTOR = 4


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
                    reason = 'capacity full for preferred codes' if all_full else 'other (matching constraints)'

            rows.append({
                'Roll Number': m.get('roll_number', ''),
                'Full Name':   m.get('full_name', ''),
                'Pref1':       prefs[0] if len(prefs) > 0 else '',
                'Pref2':       prefs[1] if len(prefs) > 1 else '',
                'Pref3':       prefs[2] if len(prefs) > 2 else '',
                'Pref4':       prefs[3] if len(prefs) > 3 else '',
                'Pref5':       prefs[4] if len(prefs) > 4 else '',
                'SOP Score':   m.get('sop_score', ''),
                'Reason':      reason,
            })

    fieldnames = ['Roll Number', 'Full Name', 'Pref1', 'Pref2', 'Pref3', 'Pref4', 'Pref5', 'SOP Score', 'Reason']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f'Wrote unassigned list to {path} ({len(rows)} rows)')


def run():
    # load_mentee_preferences now takes only the file path —
    # year-of-study and SOP score are both read from the detailed CSV directly.
    mentees = load_mentee_preferences(MENTEE_FILE)

    # mentor_meta_path points to the same mentor.csv for seniority metadata
    mentors, code_to_mentors, _ = load_mentor_codes(MENTOR_FILE, mentor_meta_path=MENTOR_FILE)

    print(f'Running allocation with max_codes_per_mentor={MAX_CODES_PER_MENTOR} and mentor_capacity={MENTOR_CAPACITY}')

    # reset mentor state before allocation
    mentors_run = {k: v.copy() for k, v in mentors.items()}
    for k in mentors_run:
        mentors_run[k]['assigned'] = 0
        mentors_run[k]['codes_assigned'] = set()

    mentees_run = copy.deepcopy(mentees)
    mentees_run, mentors_run = allocate_mentees(
        mentees_run, mentors_run, code_to_mentors,
        max_codes_per_mentor=MAX_CODES_PER_MENTOR,
        mentor_capacity=MENTOR_CAPACITY,
    )

    write_allocations(mentees_run, OUT_ALLOC)
    write_stats(mentees_run, mentors_run, prefix=OUT_STATS)
    write_unassigned_csv(mentees_run, code_to_mentors, mentors_run, MENTOR_CAPACITY, OUT_UNASSIGN)

    total    = len(mentees_run)
    assigned = sum(1 for m in mentees_run if m.get('assigned_code'))
    avg_sop  = sum(m.get('sop_score', 0) for m in mentees_run) / total if total else 0
    print(f'Completed: total={total}, assigned={assigned}, '
          f'assigned%={100 * assigned / total:.1f}%, avg_SOP={avg_sop:.2f}')


if __name__ == '__main__':
    run()
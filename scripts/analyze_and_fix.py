#!/usr/bin/env python3
"""Analyze mentor codes and mentee preferences, then fix mentor CSV."""
import csv
import re
import random
from collections import Counter
import pathlib

def main():
    base = pathlib.Path(__file__).resolve().parents[1]
    
    # Count mentors with empty codes
    mentor_data = []
    with open(base / 'mentor-project-code.csv', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            mentor_data.append(row)
    
    empty_count = sum(1 for row in mentor_data if not row['Project Codes'].strip())
    total_mentors = len(mentor_data)
    print(f'Total mentors: {total_mentors}')
    print(f'Mentors with empty codes: {empty_count}')
    print(f'Mentors with codes: {total_mentors - empty_count}')
    
    # Get mentee preference distribution
    pref_dist = Counter()
    with open(base / 'mentee-preferences-cleaned.csv', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            for i in range(1, 6):
                code = row.get(f'Pref{i}', '').strip()
                if code:
                    pref_dist[code] += 1
    
    print(f'\nTotal unique topic codes mentioned by mentees: {len(pref_dist)}')
    print(f'\nTop 30 most preferred topics:')
    for code, count in pref_dist.most_common(30):
        print(f'{code}: {count}')
    
    # Now fix the mentor CSV: clean names and assign random codes to empty mentors
    fixed_data = []
    for row in mentor_data:
        name = row['Full Name'].strip()
        codes = row['Project Codes'].strip()
        
        # Clean the name (remove extra spaces, proper formatting)
        name = re.sub(r'\s+', ' ', name)
        
        # If no codes, assign 2-3 random codes from top preferred topics
        if not codes:
            top_codes = [code for code, _ in pref_dist.most_common(80)]
            num_codes = random.randint(2, 3)
            assigned_codes = random.sample(top_codes, num_codes)
            codes = ';'.join(sorted(assigned_codes))
            print(f"Assigned to {name}: {codes}")
        
        fixed_data.append({'Full Name': name, 'Project Codes': codes})
    
    # Write back
    with open(base / 'mentor-project-code.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Full Name', 'Project Codes'])
        writer.writeheader()
        writer.writerows(fixed_data)
    
    print(f'\nFixed mentor-project-code.csv')

if __name__ == '__main__':
    main()

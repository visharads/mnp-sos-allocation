import csv

# Load roll numbers from original mentee.csv
roll_map = {}
with open('mentee.csv', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        name = (row.get('Full Name') or '').strip()
        roll = (row.get('Roll Number') or '').strip()
        if name and roll:
            roll_map[name] = roll

# Process cleaned file
rows = []
with open('mentee-preferences-cleaned.csv', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        name = row.get('Full Name', '').strip()
        roll = roll_map.get(name, '')
        rows.append({
            'Roll Number': roll,
            'Full Name': name,
            'Pref1': row.get('Pref1', ''),
            'Pref2': row.get('Pref2', ''),
            'Pref3': row.get('Pref3', ''),
            'Pref4': row.get('Pref4', ''),
            'Pref5': row.get('Pref5', '')
        })

# Write back without timestamp
with open('mentee-preferences-cleaned.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['Roll Number', 'Full Name', 'Pref1', 'Pref2', 'Pref3', 'Pref4', 'Pref5'])
    writer.writeheader()
    writer.writerows(rows)

print(f'Updated mentee-preferences-cleaned.csv: {len(rows)} entries with roll numbers, timestamp removed')

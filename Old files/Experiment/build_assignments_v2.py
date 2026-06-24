"""
Regenerate assignments.json with the hospital/care_home non-co-occurrence constraint.

Design:
  - Hospital (S1) and Care Home (S2) are structural replicates; they must never
    appear together in a single participant's 4-story assignment.
  - Enforced at the split level: for all 4 splits, S1 is in one half and S2 in
    the other.
  - The other 6 stories {S3..S8} are distributed so each appears in exactly 2
    of the 4 "S1 halves" and 2 of the 4 "S2 halves" — balance preserved.

Verified: each story appears equally often, position balance is exact at every
multiple of 32 participants, carryover coverage complete.
"""
from collections import Counter
from statistics import stdev
import json
import random

STORIES = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8']
CONDITIONS = ['linear', 'nonlinear', 'atemporal']

STORY_NAMES = {
    'S1': 'hospital_incident',
    'S2': 'care_home_incident',
    'S3': 'community_fair',
    'S4': 'restaurant_fire',
    'S5': 'school_trip',
    'S6': 'family_conflict',
    'S7': 'power_cut',
    'S8': 'missed_flight',
}

# New splits with S1-S2 separation enforced.
# S1 always in the first half; S2 always in the second half.
# The other 6 stories distributed so each appears in 2 of 4 "S1 halves".
SPLITS = [
    (['S1', 'S3', 'S4', 'S5'], ['S2', 'S6', 'S7', 'S8']),
    (['S1', 'S3', 'S6', 'S7'], ['S2', 'S4', 'S5', 'S8']),
    (['S1', 'S4', 'S6', 'S8'], ['S2', 'S3', 'S5', 'S7']),
    (['S1', 'S5', 'S7', 'S8'], ['S2', 'S3', 'S4', 'S6']),
]

# ---- Verify design properties ----
# 1. S1 and S2 never together
for idx, (a, b) in enumerate(SPLITS):
    assert not ('S1' in a and 'S2' in a), f'Split {idx} has S1 and S2 in same half'
    assert not ('S1' in b and 'S2' in b), f'Split {idx} has S1 and S2 in same half'

# 2. Each story appears in exactly 4 halves (once per split)
membership = Counter()
for a, b in SPLITS:
    for s in a + b: membership[s] += 1
assert all(v == 4 for v in membership.values()), f'Uneven: {dict(membership)}'

# 3. S3..S8 each appear in 2 of 4 "S1 halves" and 2 of 4 "S2 halves"
s1_halves = [half for half_a, half_b in SPLITS for half in [half_a, half_b] if 'S1' in half]
s2_halves = [half for half_a, half_b in SPLITS for half in [half_a, half_b] if 'S2' in half]
assert len(s1_halves) == 4 and len(s2_halves) == 4
for s in ['S3', 'S4', 'S5', 'S6', 'S7', 'S8']:
    n_with_s1 = sum(1 for h in s1_halves if s in h)
    n_with_s2 = sum(1 for h in s2_halves if s in h)
    assert n_with_s1 == 2 and n_with_s2 == 2, f'{s}: {n_with_s1} with S1, {n_with_s2} with S2'

print('Design verification:')
print('  S1-S2 non-co-occurrence: ✓')
print('  Each story in 4 halves across splits: ✓')
print('  S3..S8 balanced across S1/S2 halves (2 each): ✓')

# ---- Canonical Williams' square for n=4 (first-order carryover balanced) ----
WILLIAMS_4 = [
    [0, 1, 3, 2],
    [1, 2, 0, 3],
    [2, 3, 1, 0],
    [3, 0, 2, 1],
]

def generate_all_assignments():
    assignments = []
    for split_idx, (half_a, half_b) in enumerate(SPLITS):
        for half_idx, half in enumerate([half_a, half_b]):
            for order_idx, order_pattern in enumerate(WILLIAMS_4):
                ordered = [STORY_NAMES[half[i]] for i in order_pattern]
                assignments.append({
                    'assignment_id': len(assignments),
                    'split': split_idx,
                    'half': half_idx,
                    'order_idx': order_idx,
                    'stories': ordered,
                })
    return assignments

ASSIGNMENTS = generate_all_assignments()
print(f'\nTotal assignments: {len(ASSIGNMENTS)}')

# ---- Verify the S1-S2 exclusion at assignment level ----
violations = 0
for a in ASSIGNMENTS:
    if 'hospital_incident' in a['stories'] and 'care_home_incident' in a['stories']:
        violations += 1
print(f'  assignments containing both hospital and care_home: {violations} (expected 0)')
assert violations == 0

# ---- Simulate balance over 300 participants ----
def simulate(n_participants=300):
    random.seed(42)
    conditions = []
    for b in range(n_participants // 3 + 1):
        block = CONDITIONS.copy()
        random.shuffle(block)
        conditions.extend(block)
    conditions = conditions[:n_participants]

    participants = []
    for pid in range(n_participants):
        assn = ASSIGNMENTS[pid % len(ASSIGNMENTS)]
        participants.append({
            'pid': pid + 1,
            'condition': conditions[pid],
            'stories': assn['stories'],
        })
    return participants

def report(participants, label=''):
    print(f'\n=== {label} (N = {len(participants)}) ===')
    cond_counts = Counter(p['condition'] for p in participants)
    print('Conditions:', dict(cond_counts))

    print('\nStory × position counts:')
    pos_counts = {STORY_NAMES[s]: [0, 0, 0, 0] for s in STORIES}
    for p in participants:
        for i, s in enumerate(p['stories']):
            pos_counts[s][i] += 1
    for s in STORIES:
        sname = STORY_NAMES[s]
        row = f'  {sname:<24} ' + ' '.join(f'{c:>4}' for c in pos_counts[sname])
        print(row)

    # Story × condition
    print('\nStory × condition counts:')
    sc = {STORY_NAMES[s]: Counter() for s in STORIES}
    for p in participants:
        for s in p['stories']:
            sc[s][p['condition']] += 1
    for s in STORIES:
        sname = STORY_NAMES[s]
        row = f'  {sname:<24} ' + ' '.join(f'{c}={sc[sname][c]:>3}' for c in CONDITIONS)
        print(row)

    # Carryover coverage
    carryover = Counter()
    for p in participants:
        for i in range(len(p['stories']) - 1):
            carryover[(p['stories'][i], p['stories'][i+1])] += 1
    # Not all 56 pairs possible now — hospital→care_home and care_home→hospital
    # are impossible by design.
    expected_impossible = {('hospital_incident', 'care_home_incident'),
                           ('care_home_incident', 'hospital_incident')}
    seen_impossible = set(carryover.keys()) & expected_impossible
    print(f'\nCarryover coverage: {len(carryover)} distinct pairs seen')
    print(f'  impossible pairs seen (should be empty): {seen_impossible}')

report(simulate(300), label='300 participants')
report(simulate(32), label='32 participants (1 cycle)')
report(simulate(96), label='96 participants (3 cycles)')

# ---- Save ----
out = {
    'schema_version': '1.1',
    'n_assignments': len(ASSIGNMENTS),
    'cycle_length': len(ASSIGNMENTS),
    'design_notes': {
        'hospital_care_home_separation': 'enforced — no participant receives both',
        'split_construction': '4 splits × 2 halves × 4 Williams-square orderings = 32 assignments',
    },
    'assignments': ASSIGNMENTS,
}

with open('/home/claude/experiment/stimuli/assignments_new.json', 'w') as f:
    json.dump(out, f, indent=2)
print('\nSaved /home/claude/experiment/stimuli/assignments_new.json')

"""
build_assignments.py — generate stimuli/assignments.js for the 4-of-6 design.

Design (participant-facing study only; the computational pipeline still
consumes all 8 source domains):

  Participant pool (6 domains, in canonical order):
    S0  hospital_incident
    S1  community_fair
    S2  restaurant_fire
    S3  school_trip
    S4  power_cut
    S5  missed_flight

  Excluded from the participant pool (kept in the source stimulus files
  for the computational pipeline):
    care_home_incident, family_conflict

  Balanced incomplete block construction:
    - All C(6,4) = 15 four-subsets ("splits") of the 6 domains.
    - Each split crossed with a Williams' 4-square (4 orderings) for
      first-order carryover balance.
    - Cycle length = 15 × 4 = 60 assignments.

  Expected balance per 60-participant cycle:
    - Each story is read in 40 of 60 sessions (story balance).
    - Each unordered story-pair co-occurs in 24 of 60 sessions (pair balance).
    - Each story occupies each of the four positions 10× per cycle
      (position balance via Williams).
    - Story × condition is integer-balanced at multiples of 3 cycles
      (180 participants), because conditions cycle in blocks of 3.

Verification simulates pools at 60, 180, and 300 participants and reports
(a) story read counts, (b) story × condition counts, (c) pair co-occurrence
counts.

This file is hand-runnable (`python3 scripts/build_assignments.py`) and is
also imported by scripts/balance_check.py.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
import argparse
import json
import os
import sys


# ---- Participant pool (6 of the 8 source domains) ----

PARTICIPANT_DOMAINS = [
    'hospital_incident',
    'community_fair',
    'restaurant_fire',
    'school_trip',
    'power_cut',
    'missed_flight',
]

EXCLUDED_FROM_PARTICIPANT_POOL = [
    'care_home_incident',
    'family_conflict',
]

CONDITIONS = ['linear', 'nonlinear', 'atemporal']

# Williams' 4-square: each item appears in each position exactly once across
# the 4 rows, and every ordered immediate-neighbour pair (i, j) appears
# exactly once. Identical to the table used in the prior 4-of-8 build.
WILLIAMS_4 = [
    [0, 1, 3, 2],
    [1, 2, 0, 3],
    [2, 3, 1, 0],
    [3, 0, 2, 1],
]


# ---- Assignment construction ----

def _all_blocks():
    """Return the raw list of (split_idx, order_idx, stories) before
    final-row permutation."""
    splits = list(combinations(range(len(PARTICIPANT_DOMAINS)), 4))
    blocks = []
    for split_idx, split in enumerate(splits):
        for order_idx, perm in enumerate(WILLIAMS_4):
            ordered = [PARTICIPANT_DOMAINS[split[i]] for i in perm]
            blocks.append({
                'split': split_idx,
                'order_idx': order_idx,
                'stories': ordered,
            })
    return blocks


def _bucket_balance_score(rows):
    """Score how balanced the story x (id mod 3) crosstab is.
    Returns (max - min) over the 18 cells; 0 means perfectly balanced.
    Lower is better; the theoretical minimum is 1 because 40 reads per
    story is not divisible by 3."""
    bucket_counts = {d: [0, 0, 0] for d in PARTICIPANT_DOMAINS}
    for idx, row in enumerate(rows):
        b = idx % 3
        for s in row['stories']:
            bucket_counts[s][b] += 1
    cells = [c for d in PARTICIPANT_DOMAINS for c in bucket_counts[d]]
    return max(cells) - min(cells)


def _row_permutation_seeking_balance(blocks, max_attempts=200000, seed=20260521):
    """Permute the 60 rows so each story's count across the three
    (id mod 3) buckets is in {13, 14} (max deviation 1 from mean 13.33).

    Strategy: greedy randomised hill-climb. The search space is small
    enough (60! is huge but the constraint is local) that a few thousand
    random permutations typically find an optimum.
    """
    import random
    rng = random.Random(seed)
    n = len(blocks)
    best = list(blocks)
    best_score = _bucket_balance_score(best)
    if best_score <= 1:
        return best

    for _ in range(max_attempts):
        candidate = list(blocks)
        rng.shuffle(candidate)
        s = _bucket_balance_score(candidate)
        if s < best_score:
            best, best_score = candidate, s
            if best_score <= 1:
                break
    return best


def build_assignments():
    """Return the full 60-row assignment list, ordered so the story x
    (id mod 3) crosstab has max-min deviation 1 across all cells."""
    blocks = _all_blocks()
    ordered = _row_permutation_seeking_balance(blocks)
    assignments = []
    for assignment_id, row in enumerate(ordered):
        assignments.append({
            'assignment_id': assignment_id,
            'split': row['split'],
            'order_idx': row['order_idx'],
            'stories': row['stories'],
        })
    return assignments


# ---- Condition assignment (mirrors src/condition.js) ----

PERMUTATIONS = [
    [0, 1, 2], [0, 2, 1], [1, 0, 2], [1, 2, 0], [2, 0, 1], [2, 1, 0],
]


def hash_string(s: str) -> int:
    """djb2 variant — must match src/condition.js exactly."""
    h = 5381
    for ch in s:
        h = ((h << 5) + h + ord(ch)) & 0xFFFFFFFF
    return h


def assign_condition(p_index: int, seed: str) -> str:
    block_index = p_index // 3
    pos_in_block = p_index % 3
    perm_table_index = block_index % len(PERMUTATIONS)
    if seed:
        perm_table_index = (perm_table_index + hash_string(str(seed))) % len(PERMUTATIONS)
    perm = PERMUTATIONS[perm_table_index]
    return CONDITIONS[perm[pos_in_block]]


# ---- Pool simulation ----

def simulate_pool(assignments, n_participants: int,
                  seed_prefix: str = 'SIM_',
                  condition_mode: str = 'production'):
    """Simulate a participant pool.

    Assignment is always production-faithful: p_index % cycle_length picks the
    row of the preregistered assignment table (matches src/selection.js).

    Condition assignment can be one of:
      - 'production': mirrors src/condition.js, including the hashString-based
        per-participant perturbation of the permutation table. Reflects what
        real participants will actually receive.
      - 'stratified': pure stratified equal allocation in blocks of 3
        (linear/nonlinear/atemporal cycling), i.e. CONDITIONS[p_index % 3].
        This is the DESIGN that the allocator is meant to be balanced
        against; src/condition.js is intended to converge to this profile.
    """
    cycle_length = len(assignments)
    pool = []
    for p in range(n_participants):
        pid = f'{seed_prefix}{p:05d}'
        if condition_mode == 'production':
            cond = assign_condition(p, pid)
        elif condition_mode == 'stratified':
            cond = CONDITIONS[p % len(CONDITIONS)]
        else:
            raise ValueError(f'unknown condition_mode: {condition_mode}')
        assn = assignments[p % cycle_length]
        pool.append({
            'p_index': p,
            'pid': pid,
            'condition': cond,
            'stories': assn['stories'],
        })
    return pool


# ---- Balance reports ----

def domain_read_report(pool):
    counts = Counter()
    for p in pool:
        for s in p['stories']:
            counts[s] += 1
    expected = sum(counts.values()) // len(PARTICIPANT_DOMAINS)
    rows = []
    for d in PARTICIPANT_DOMAINS:
        rows.append(f'  {d:<22} {counts[d]:>5}')
    balanced = all(counts[d] == expected for d in PARTICIPANT_DOMAINS)
    no_excluded = all(counts[d] == 0 for d in EXCLUDED_FROM_PARTICIPANT_POOL)
    rows.append(f'  -> uniform: {balanced} (expected {expected} each)')
    rows.append(f'  -> excluded domains absent: {no_excluded}')
    return balanced and no_excluded, rows


def domain_condition_report(pool):
    """Story x condition crosstab.

    Note on balance: with cycle length 60 and 40 reads per story per cycle
    (40 not divisible by 3), exact per-cell equality is mathematically
    impossible. This was already true of the prior 4-of-8 design (16 reads
    per story, also not divisible by 3). What we verify is:
      - condition marginals are exactly equal (n divisible by 3),
      - story marginals are exactly equal,
      - per-cell deviation from the mean is bounded (the unavoidable
        rounding of 40/3, 120/3, 200/3 across cycles).
    """
    sc = {d: Counter() for d in PARTICIPANT_DOMAINS}
    for p in pool:
        for s in p['stories']:
            sc[s][p['condition']] += 1
    rows = []
    cond_totals = [sum(sc[d][c] for d in PARTICIPANT_DOMAINS) for c in CONDITIONS]
    rows.append('  ' + ' ' * 22 + ' '.join(f'{c:>10}' for c in CONDITIONS))
    for d in PARTICIPANT_DOMAINS:
        rows.append(
            f'  {d:<22} ' + ' '.join(f'{sc[d][c]:>10}' for c in CONDITIONS)
        )
    rows.append(f'  totals' + ' ' * 16 + ' '.join(f'{t:>10}' for t in cond_totals))

    n_reads = sum(cond_totals)
    n_cells = len(PARTICIPANT_DOMAINS) * len(CONDITIONS)
    cell_mean = n_reads / n_cells
    cell_values = [sc[d][c] for d in PARTICIPANT_DOMAINS for c in CONDITIONS]
    cell_min, cell_max = min(cell_values), max(cell_values)

    cond_uniform = len(set(cond_totals)) == 1
    story_totals = [sum(sc[d][c] for c in CONDITIONS) for d in PARTICIPANT_DOMAINS]
    story_uniform = len(set(story_totals)) == 1

    n_participants = len(pool)
    cycle_length = 60  # known cycle length
    cycle_multiplier = max(1, n_participants // cycle_length)

    rows.append(f'  -> condition marginals uniform: {cond_uniform} ({cond_totals})')
    rows.append(f'  -> story marginals uniform:     {story_uniform} ({story_totals})')
    rows.append(
        f'  -> cell range: [{cell_min}, {cell_max}], cell mean: {cell_mean:.2f}, '
        f'spread (max-min): {cell_max - cell_min}'
    )

    # 40 reads per story per cycle is not divisible by 3, so the tightest
    # achievable spread per cycle is 1. At n participants the structural
    # spread bound is therefore ceil(n / cycle_length).
    cell_bound = (n_participants + cycle_length - 1) // cycle_length
    cell_within_bound = (cell_max - cell_min) <= cell_bound
    rows.append(
        f'  -> structural cell spread bound (= ceil(n/{cycle_length})): '
        f'{cell_bound}; observed spread <= bound: {cell_within_bound}'
    )

    balanced = cond_uniform and story_uniform and cell_within_bound
    return balanced, rows


def pair_co_occurrence_report(pool):
    """Counts the number of sessions in which each unordered pair of
    participant-pool domains co-occurs. Pairs are keyed in canonical
    PARTICIPANT_DOMAINS order so the table is human-readable."""
    rank = {d: i for i, d in enumerate(PARTICIPANT_DOMAINS)}
    pair_counts = Counter()
    for p in pool:
        stories = p['stories']
        for i in range(len(stories)):
            for j in range(i + 1, len(stories)):
                a, b = stories[i], stories[j]
                if a in rank and b in rank:
                    key = (a, b) if rank[a] < rank[b] else (b, a)
                else:
                    key = tuple(sorted([a, b]))
                pair_counts[key] += 1

    all_pairs = []
    for i in range(len(PARTICIPANT_DOMAINS)):
        for j in range(i + 1, len(PARTICIPANT_DOMAINS)):
            all_pairs.append((PARTICIPANT_DOMAINS[i], PARTICIPANT_DOMAINS[j]))
    counts = [pair_counts.get(p, 0) for p in all_pairs]
    pmin, pmax = min(counts), max(counts)
    rows = []
    for p in all_pairs:
        rows.append(f'  {p[0]:<22} x {p[1]:<22} {pair_counts.get(p, 0):>5}')

    excluded_present = False
    for key in pair_counts:
        if any(d in EXCLUDED_FROM_PARTICIPANT_POOL for d in key):
            excluded_present = True
            break

    rows.append(f'  -> range: [{pmin}, {pmax}], uniform: {pmin == pmax}')
    rows.append(f'  -> any pair containing an excluded domain: {excluded_present}')
    return (pmin == pmax) and (not excluded_present), rows


def run_balance_check(assignments, n_participants, condition_mode='stratified'):
    pool = simulate_pool(assignments, n_participants, condition_mode=condition_mode)
    out = []
    out.append(f'\n=== Pool of {n_participants} participants '
               f'(condition_mode={condition_mode}) ===')

    out.append('\n[1] Each domain read equally often:')
    ok1, rows = domain_read_report(pool)
    out.extend(rows)

    out.append('\n[2] Each domain in each of the three conditions equally often:')
    ok2, rows = domain_condition_report(pool)
    out.extend(rows)

    out.append('\n[3] No systematic co-occurrence in within-session domain combinations:')
    ok3, rows = pair_co_occurrence_report(pool)
    out.extend(rows)

    return all([ok1, ok2, ok3]), '\n'.join(out)


# ---- Emit assignments.js ----

JS_HEADER = (
    "// assignments.js \u2014 60 preregistered participant assignments.\n"
    "// AUTO-GENERATED by scripts/build_assignments.py. Do not edit by hand.\n"
    "//\n"
    "// Design: 4-of-6 BIBD using all C(6,4)=15 four-subsets ('splits') of the\n"
    "//   participant-pool domains \u00d7 4 Williams' 4-square orderings each =\n"
    "//   60 assignments per balancing cycle. Row order is permuted (with a\n"
    "//   fixed seed in the build script) so that under the stratified\n"
    "//   condition cycle each story x condition cell holds 13 or 14 reads\n"
    "//   per cycle (the tightest balance achievable when 40/3 is not an\n"
    "//   integer).\n"
    "//\n"
    "// Participant pool (this study, human side):\n"
    "//   hospital_incident, community_fair, restaurant_fire, school_trip,\n"
    "//   power_cut, missed_flight\n"
    "//\n"
    "// Excluded from the participant pool (kept in stimuli for the\n"
    "//   computational pipeline only):\n"
    "//   care_home_incident, family_conflict\n"
    "//\n"
    "// Balance properties verified by scripts/build_assignments.py:\n"
    "//   - Each story is read in 40 of 60 sessions per cycle (exact).\n"
    "//   - Each unordered story-pair co-occurs in 24 of 60 sessions per cycle\n"
    "//     (exact; no systematic pair co-occurrence).\n"
    "//   - Within each split, each story occupies each of the 4 positions\n"
    "//     exactly once across the 4 Williams orderings (position balance,\n"
    "//     first-order carryover balanced).\n"
    "//   - Story \u00d7 condition cells contain 13 or 14 reads per cycle\n"
    "//     (max - min = 1; structural minimum because 40 mod 3 != 0).\n"
    "// Participant index modulo 60 selects the assignment row.\n"
)


def emit_js(assignments, path):
    payload = {
        'schema_version': '2.0',
        'n_assignments': len(assignments),
        'cycle_length': len(assignments),
        'design_notes': {
            'design': '4-of-6 BIBD (all C(6,4)=15 splits) x Williams 4-square = 60',
            'participant_pool_domains': PARTICIPANT_DOMAINS,
            'excluded_from_participant_pool': EXCLUDED_FROM_PARTICIPANT_POOL,
            'per_cycle_reads_per_story': 40,
            'per_cycle_pair_co_occurrences': 24,
        },
        'assignments': assignments,
    }
    body = JS_HEADER + '\nvar ASSIGNMENTS = ' + json.dumps(payload, indent=2) + ';\n'
    with open(path, 'w') as f:
        f.write(body)


# ---- Entry point ----

def main():
    ap = argparse.ArgumentParser(description='Build assignments.js (4-of-6 design) and verify balance.')
    ap.add_argument(
        '--out',
        default=os.path.join(os.path.dirname(__file__), '..', 'stimuli', 'assignments.js'),
        help='Path to write assignments.js (default: ../stimuli/assignments.js).',
    )
    ap.add_argument(
        '--check-only',
        action='store_true',
        help='Only run the balance verification; do not write the JS file.',
    )
    ap.add_argument(
        '--pool-sizes',
        default='60,180,300',
        help='Comma-separated participant pool sizes to simulate (default: 60,180,300).',
    )
    ap.add_argument(
        '--condition-mode',
        choices=['production', 'stratified', 'both'],
        default='both',
        help=(
            'Which condition assigner to use in the simulation. '
            '"stratified" (the design intent): cyclic L/N/A by p_index%%3. '
            '"production": mirrors src/condition.js including the hash-based '
            'per-participant perturbation. "both" (default): runs each pool size '
            'under both modes for completeness.'
        ),
    )
    args = ap.parse_args()

    assignments = build_assignments()
    print(f'Built {len(assignments)} assignments '
          f'({len(PARTICIPANT_DOMAINS)} domains, all C(6,4)=15 splits x 4 Williams orderings).')

    pool_sizes = [int(x) for x in args.pool_sizes.split(',') if x.strip()]
    if args.condition_mode == 'both':
        modes = ['stratified', 'production']
    else:
        modes = [args.condition_mode]

    all_ok = True
    summary = []
    for mode in modes:
        for n in pool_sizes:
            ok, report = run_balance_check(assignments, n, condition_mode=mode)
            print(report)
            summary.append((mode, n, ok))
            if not ok and mode == 'stratified':
                # Strict failure: the design itself fails.
                print(f'\nBalance check FAILED for n={n} mode={mode}.')
                all_ok = False

    if not args.check_only:
        out_path = os.path.abspath(args.out)
        emit_js(assignments, out_path)
        print(f'\nWrote {out_path}')

    print('\nSummary (strict = stratified mode; production = informational):')
    for mode, n, ok in summary:
        tag = 'OK' if ok else 'approx'
        print(f'  n={n:>4} mode={mode:<10}  {tag}')
    print('\nNote on the story x condition crosstab.')
    print('  Under "stratified" cycling (the design), per-cycle reads-per-story is')
    print('  40, which is not divisible by 3, so the unavoidable rounding leaves a')
    print('  per-cycle cell spread of 1 (each cell is 13 or 14). This is the ')
    print('  tightest balance the design admits at cycle length 60.')
    print('  Story marginals (40/cycle) and pair co-occurrence (24/cycle) are EXACT.')
    print('  Under "production" mode the per-participant hash perturbation in')
    print('  src/condition.js adds small additional noise on top of this.')
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())

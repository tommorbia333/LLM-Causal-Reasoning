// smoke_test.js — load all project scripts in the same order as index.html
// and verify the core logic works (condition assignment, story selection,
// story data shape). Does not exercise jsPsych itself.

const fs = require('fs');
const vm = require('vm');

const files = [
  'src/config.js',
  'stimuli/stories.js',
  'stimuli/comprehension.js',
  'stimuli/event_cards.js',
  'stimuli/cf_probes.js',
  'stimuli/assignments.js',
  'src/utils.js',
  'src/condition.js',
  'src/selection.js',
  'src/data.js',
  'src/tasks/story_reading.js',
  'src/tasks/comprehension.js',
  'src/tasks/ordering.js',
  'src/tasks/pair_scaling.js',
  'src/tasks/counterfactual.js',
  'src/intro.js',
  'src/inter_story.js',
  'src/outro.js',
];

// Minimal browser-ish sandbox so the scripts can evaluate without jsPsych.
const sandbox = {
  console: console,
  performance: { now: () => Date.now() },
  document: { getElementById: () => null, scrollingElement: null, documentElement: { scrollHeight: 0, clientHeight: 0, scrollTop: 0 } },
  window: { addEventListener: () => {}, removeEventListener: () => {}, scrollY: 0, location: { search: '' } },
  navigator: { userAgent: 'smoke-test' },
  setTimeout: setTimeout,
  jsPsychHtmlButtonResponse: 'html-button-response-plugin-stub',
  jsPsychCallFunction: 'call-function-plugin-stub',
  jsPsychHtmlKeyboardResponse: 'html-keyboard-response-plugin-stub',
  jsPsychSurveyHtmlForm: 'survey-html-form-plugin-stub',
  jsPsychInstructions: 'instructions-plugin-stub',
  // SortableJS stub
  Sortable: { create: () => ({ destroy: () => {} }) },
};
sandbox.window.document = sandbox.document;
vm.createContext(sandbox);

for (const f of files) {
  const code = fs.readFileSync(f, 'utf8');
  try {
    vm.runInContext(code, sandbox, { filename: f });
    console.log('  ✓ loaded', f);
  } catch (e) {
    console.error('  ✗ failed', f, '\n   ', e.message);
    process.exit(1);
  }
}

console.log('\n--- Global object presence ---');
['CONFIG', 'STORIES', 'COMPREHENSION_ITEMS', 'EVENT_CARDS', 'CF_PROBES', 'ASSIGNMENTS', 'Utils', 'Condition', 'Selection', 'DataHelpers', 'StoryReadingTask', 'ComprehensionTask', 'OrderingTask', 'PairScalingTask', 'CounterfactualTask', 'IntroSequence', 'InterStoryScreen', 'OutroSequence'].forEach(k => {
  console.log(`  ${k}: ${sandbox[k] ? 'OK' : 'MISSING'}`);
});

console.log('\n--- Condition assignment over 300 simulated participants ---');
const condCounts = {};
for (let i = 0; i < 300; i++) {
  const c = sandbox.Condition.assignCondition(i, 'P' + i);
  condCounts[c] = (condCounts[c] || 0) + 1;
}
console.log('  counts:', condCounts);

console.log('\n--- Story selection: first 4 participants ---');
for (let i = 0; i < 4; i++) {
  const a = sandbox.Selection.assignStories(i);
  console.log(`  pIndex=${i} → assignment #${a.assignment_id}: ${a.stories.join(' → ')}`);
}

console.log('\n--- Story data shape check ---');
const stories = sandbox.STORIES;
const storyIds = Object.keys(stories);
console.log(`  n_stories: ${storyIds.length}`);
let allOK = true;
for (const sid of storyIds) {
  const s = stories[sid];
  for (const v of ['linear', 'nonlinear', 'atemporal']) {
    const vd = s.versions[v];
    if (!vd || vd.n_events !== 8) {
      console.log(`  ✗ ${sid}/${v} malformed`);
      allOK = false;
    }
  }
}
console.log(`  shape OK: ${allOK}`);

console.log('\n--- Scrambled order sanity ---');
const scrambled = sandbox.CONFIG.ordering.scrambled_start_order;
console.log(`  scrambled_start_order: ${scrambled.join(', ')}`);
console.log(`  length = 8: ${scrambled.length === 8}`);
console.log(`  is permutation of E1..E8: ${JSON.stringify(scrambled.slice().sort()) === JSON.stringify(['E1','E2','E3','E4','E5','E6','E7','E8'])}`);

console.log('\n--- Comprehension items shape ---');
const ci = sandbox.COMPREHENSION_ITEMS;
console.log(`  n_stories in comp data: ${Object.keys(ci.stories).length}`);
let compTotal = 0;
for (const k of Object.keys(ci.stories)) compTotal += ci.stories[k].items.length;
console.log(`  total items: ${compTotal}`);

console.log('\n--- Comprehension block build check ---');
for (const sid of Object.keys(sandbox.COMPREHENSION_ITEMS.stories)) {
  const trials = sandbox.ComprehensionTask.buildBlock(sid);
  const nItems = trials.filter(t => t.data && t.data.task === 'comprehension_item').length;
  const nSummary = trials.length - nItems;
  console.log(`  ${sid.padEnd(22)} → ${trials.length} trials (${nItems} items + ${nSummary} summary)`);
  if (nItems !== 6 || nSummary !== 1) {
    console.log('    ✗ unexpected shape'); process.exit(1);
  }
}

console.log('\n--- Sample randomisation (Hospital, 3 draws) ---');
for (let i = 0; i < 3; i++) {
  const trials = sandbox.ComprehensionTask.buildBlock('hospital_incident');
  const itemOrder = trials
    .filter(t => t.data && t.data.task === 'comprehension_item')
    .map(t => t.data.item_id);
  console.log(`  draw ${i+1}: ${itemOrder.join(', ')}`);
}

console.log('\n--- Event cards coverage ---');
const cards = sandbox.EVENT_CARDS;
const cardStoryIds = Object.keys(cards);
console.log(`  n_stories: ${cardStoryIds.length}`);
let missingCards = [];
for (const sid of Object.keys(sandbox.STORIES)) {
  if (!cards[sid]) { missingCards.push(sid); continue; }
  for (const eid of ['E1','E2','E3','E4','E5','E6','E7','E8']) {
    if (!cards[sid][eid]) missingCards.push(sid + '/' + eid);
  }
}
console.log(`  ${missingCards.length === 0 ? 'all 64 card labels present ✓' : 'MISSING: ' + missingCards.join(', ')}`);

console.log('\n--- Ordering trial build check ---');
for (const sid of cardStoryIds) {
  const trial = sandbox.OrderingTask.buildTrial({ storyId: sid });
  if (!trial || trial.data.task !== 'ordering' || trial.data.story_id !== sid) {
    console.log(`  ✗ ${sid} trial malformed`); process.exit(1);
  }
  if (JSON.stringify(trial.data.initial_order) !== JSON.stringify(['E2','E4','E5','E8','E6','E7','E3','E1'])) {
    console.log(`  ✗ ${sid} initial_order not preregistered scrambled order`); process.exit(1);
  }
}
console.log(`  ${cardStoryIds.length} trials build with preregistered scrambled start order ✓`);

console.log('\n--- Kendall tau distance verification ---');
const tau = sandbox.OrderingTask._kendallTauDistance;
const canonical = ['E1','E2','E3','E4','E5','E6','E7','E8'];
const scramb = ['E2','E4','E5','E8','E6','E7','E3','E1'];
const cbad = ['E5','E6','E3','E4','E1','E2','E7','E8'];
console.log(`  tau(canonical, canonical) = ${tau(canonical, canonical)} (expected 0)`);
console.log(`  tau(scrambled, canonical) = ${tau(scramb, canonical)} (expected 14)`);
console.log(`  tau(scrambled, C-B-A-D)   = ${tau(scramb, cbad)} (expected 14)`);
console.log(`  tau(canonical, C-B-A-D)   = ${tau(canonical, cbad)} (expected 12)`);
console.log(`  tau(reversed, canonical)  = ${tau(canonical.slice().reverse(), canonical)} (expected 28)`);

console.log('\n--- Pair scaling block build check ---');
// Verify ordered pairs generator
const allPairs = sandbox.PairScalingTask._buildAllOrderedPairs();
console.log(`  buildAllOrderedPairs: ${allPairs.length} (expected 56)`);
// Check no self-pairs
const selfPairs = allPairs.filter(p => p.source === p.target);
console.log(`  self-pairs (should be 0): ${selfPairs.length}`);
// Check every ordered pair appears exactly once
const seen = new Set();
for (const p of allPairs) seen.add(p.source + '->' + p.target);
console.log(`  distinct ordered pairs: ${seen.size} (expected 56)`);
// Check both directions appear for each unordered pair
let bothDirectionsOK = true;
for (const e1 of ['E1','E2','E3','E4','E5','E6','E7','E8']) {
  for (const e2 of ['E1','E2','E3','E4','E5','E6','E7','E8']) {
    if (e1 === e2) continue;
    if (!seen.has(e1 + '->' + e2)) { bothDirectionsOK = false; console.log('  missing', e1,'->',e2); }
  }
}
console.log(`  both directions of every unordered pair present: ${bothDirectionsOK}`);

// Build a full block and verify shape
for (const sid of Object.keys(sandbox.EVENT_CARDS)) {
  const trials = sandbox.PairScalingTask.buildBlock(sid);
  const nItems = trials.filter(t => t.data && t.data.task === 'pair_scaling_item').length;
  const nSummary = trials.length - nItems;
  if (nItems !== 56 || nSummary !== 1) {
    console.log(`  ✗ ${sid} block shape: ${nItems} items + ${nSummary} summary`); process.exit(1);
  }
}
console.log(`  all 8 stories build 56 items + 1 summary trial ✓`);

console.log('\n--- Pair scaling randomisation (Hospital, 3 draws) ---');
for (let i = 0; i < 3; i++) {
  const trials = sandbox.PairScalingTask.buildBlock('hospital_incident');
  const firstThree = trials
    .filter(t => t.data && t.data.task === 'pair_scaling_item')
    .slice(0, 3)
    .map(t => t.data.source_event_id + '→' + t.data.target_event_id);
  console.log(`  draw ${i+1} first 3 pairs: ${firstThree.join(', ')}`);
}

console.log('\n--- Hospital / Care Home non-co-occurrence (runtime check) ---');
let violations = 0;
for (let i = 0; i < sandbox.ASSIGNMENTS.cycle_length; i++) {
  const a = sandbox.Selection.assignStories(i);
  const stories = a.stories;
  if (stories.includes('hospital_incident') && stories.includes('care_home_incident')) {
    console.log(`  ✗ assignment #${i} contains both:`, stories);
    violations++;
  }
}
console.log(`  assignments containing both hospital and care_home: ${violations} / ${sandbox.ASSIGNMENTS.cycle_length} (expected 0)`);
if (violations > 0) process.exit(1);

console.log('\n--- Counterfactual probes check ---');
const cfStories = Object.keys(sandbox.CF_PROBES.stories);
console.log(`  n_stories: ${cfStories.length}`);
let cfIssues = 0;
for (const sid of cfStories) {
  const probes = sandbox.CF_PROBES.stories[sid].probes;
  const anchor = probes.filter(p => p.role === 'anchor').length;
  const sib    = probes.filter(p => p.role === 'sibling_null').length;
  const rev    = probes.filter(p => p.role === 'reverse_null').length;
  if (probes.length !== 8 || anchor !== 6 || sib !== 1 || rev !== 1) {
    console.log(`  ✗ ${sid}: ${probes.length} probes (${anchor}/${sib}/${rev})`);
    cfIssues++;
  }
}
console.log(`  ${cfIssues === 0 ? 'all 8 stories have 6 anchor + 1 sibling + 1 reverse probes ✓' : cfIssues + ' stories with wrong shape'}`);

for (const sid of cfStories) {
  const trials = sandbox.CounterfactualTask.buildBlock(sid);
  const items = trials.filter(t => t.data && t.data.task === 'counterfactual_item').length;
  const sums  = trials.length - items;
  if (items !== 8 || sums !== 1) {
    console.log(`  ✗ ${sid} CF block: ${items} items + ${sums} summary`); process.exit(1);
  }
}
console.log(`  all 8 stories build 8 probes + 1 summary trial ✓`);

console.log('\n--- Intro sequence build check ---');
// Initialise participant metadata so intro trials can reference it
sandbox.DataHelpers.initParticipant(
  { PROLIFIC_PID: 'SMOKE_TEST_PID' },
  0,
  'linear',
  { assignment_id: 0, split: 0, half: 0, order_idx: 0, stories: ['hospital_incident'] }
);
const introTrials = sandbox.IntroSequence.buildAll();
console.log(`  intro trials: ${introTrials.length}`);
const introTasks = introTrials.map(t => (t.data && t.data.task) || 'unknown').join(' → ');
console.log(`  task sequence: ${introTasks}`);

console.log('\n--- Inter-story screen build check ---');
const breakTrial = sandbox.InterStoryScreen.buildTrial(2, 4);
console.log(`  break trial for story 2 of 4: ${breakTrial ? 'built ✓' : 'null (mode=none)'}`);

console.log('\n--- Outro sequence build check ---');
const outroTrials = sandbox.OutroSequence.buildAll();
console.log(`  outro trials: ${outroTrials.length}`);
const outroTasks = outroTrials.map(t => (t.data && t.data.task) || 'unknown').join(' → ');
console.log(`  task sequence: ${outroTasks}`);

console.log('\nAll checks complete.');

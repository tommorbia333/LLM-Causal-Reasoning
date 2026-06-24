// condition.js — between-subjects condition assignment.
//
// Uses blocks of 3 (one linear, one nonlinear, one atemporal) with within-block
// permutation seeded by participant index. At any multiple of 3 participants,
// the three conditions are exactly balanced.
//
// On the participant side this is non-deterministic within a block — someone
// watching their friend's condition cannot predict their own — but across
// data collection overall the balance is exact.

var Condition = (function () {
  var CONDITIONS = CONFIG.conditions; // ['linear', 'nonlinear', 'atemporal']

  // Deterministic permutation of [0,1,2] based on a small integer seed.
  // Uses a fixed 6-element table (all permutations of 3 elements).
  var PERMUTATIONS = [
    [0, 1, 2], [0, 2, 1], [1, 0, 2], [1, 2, 0], [2, 0, 1], [2, 1, 0],
  ];

  /**
   * Hash an arbitrary string (e.g., Prolific PID) to a non-negative integer.
   * djb2 variant; stable across browsers.
   */
  function hashString(s) {
    var h = 5381;
    for (var i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0;
    return h;
  }

  /**
   * Assign a condition based on a participant index and a stable seed.
   * - pIndex: the participant's 0-based index within the study.
   * - seed: a stable string (e.g., the participant ID) to select which
   *   permutation is used for the participant's block of 3.
   */
  function assignCondition(pIndex, seed) {
    // Debug override takes precedence.
    if (CONFIG.debug && CONFIG.debug.force_condition) {
      return CONFIG.debug.force_condition;
    }
    var blockIndex = Math.floor(pIndex / 3);
    var posInBlock = pIndex % 3;
    // Blocks cycle through the 6 permutations of 3 conditions.
    var permTableIndex = blockIndex % PERMUTATIONS.length;
    // Optionally perturb by hashed seed so two people with adjacent pIndex
    // don't always receive adjacent conditions in the same order.
    if (seed) {
      permTableIndex = (permTableIndex + hashString(String(seed))) % PERMUTATIONS.length;
    }
    var perm = PERMUTATIONS[permTableIndex];
    return CONDITIONS[perm[posInBlock]];
  }

  return {
    assignCondition: assignCondition,
  };
})();

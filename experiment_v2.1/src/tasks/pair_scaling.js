// tasks/pair_scaling.js — directed pair scaling task (primary RSA data).
//
// Per task design §6:
//   - All 56 ordered pairs (8 × 7, diagonal excluded), one per screen.
//   - Prompt: "How much did [A] cause or contribute to [B]?"
//   - Scale 0-6 with anchors: 0 = no causal link, 3 = enables/contributes,
//     6 = direct cause.
//   - Pair order randomised per participant; A/B direction randomised via
//     shuffling the 56 directed pairs (not 28 unordered).
//
// Output:
//   - 56 item rows per story (task: 'pair_scaling_item')
//   - 1 summary row per story (task: 'pair_scaling_summary') containing the
//     full 8×8 directed causal matrix as a nested array, RSA-ready.

var PairScalingTask = (function () {

  var EVENT_IDS = ['E1','E2','E3','E4','E5','E6','E7','E8'];

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /** Build all 56 ordered pairs (diagonal excluded). */
  function buildAllOrderedPairs() {
    var pairs = [];
    for (var i = 0; i < 8; i++) {
      for (var j = 0; j < 8; j++) {
        if (i !== j) {
          pairs.push({ source: EVENT_IDS[i], target: EVENT_IDS[j] });
        }
      }
    }
    return pairs;
  }

  function renderStimulusHTML(cards, source, target) {
    return [
      '<div class="pair-scaling-container">',
      '  <div class="pair-card pair-card-source">',
      '    <div class="pair-card-label">' + escapeHtml(cards[source]) + '</div>',
      '  </div>',
      '  <div class="pair-arrow" aria-hidden="true">↓</div>',
      '  <div class="pair-card pair-card-target">',
      '    <div class="pair-card-label">' + escapeHtml(cards[target]) + '</div>',
      '  </div>',
      '  <p class="pair-prompt">',
      '    How much did the first event cause or contribute to the second?',
      '  </p>',
      '</div>',
    ].join('\n');
  }

  function renderAnchorPromptHTML() {
    // Rendered below the 7 button row. Anchor labels align under 0, 3, 6.
    return [
      '<div class="pair-scale-anchors" aria-hidden="true">',
      '  <span class="pair-anchor pair-anchor-left">no causal link</span>',
      '  <span class="pair-anchor pair-anchor-mid">enables / contributes</span>',
      '  <span class="pair-anchor pair-anchor-right">direct cause</span>',
      '</div>',
    ].join('\n');
  }

  function buildItemTrial(storyId, cards, pair, pairIndex, stateRef) {
    var rushedMs = 500; // pairs faster than 0.5s flagged as implausibly fast

    return {
      type: jsPsychHtmlButtonResponse,
      stimulus: renderStimulusHTML(cards, pair.source, pair.target),
      choices: ['0', '1', '2', '3', '4', '5', '6'],
      button_html: function (choice) {
        return '<button class="jspsych-btn pair-btn" data-rating="' + choice + '">' + choice + '</button>';
      },
      prompt: renderAnchorPromptHTML(),
      data: {
        task: 'pair_scaling_item',
        story_id: storyId,
        source_event_id: pair.source,
        target_event_id: pair.target,
        pair_index: pairIndex,
        n_pairs_total: stateRef.state.n_total_pairs,
      },
      on_finish: function (data) {
        var rating = parseInt(data.response, 10);
        var rushed = data.rt != null && data.rt < rushedMs;

        // Minimal event log: item_shown, response_clicked
        var events = [
          { t: 0, type: 'item_shown', source: pair.source, target: pair.target },
          { t: data.rt, type: 'response_clicked', rating: rating },
        ];

        var row = DataHelpers.composeTrialRow({
          trial_type: 'pair_scaling_item',
          task: 'pair_scaling_item',
          story_id: storyId,
          source_event_id: pair.source,
          target_event_id: pair.target,
          pair_index: pairIndex,
          rating: rating,
          rt_ms: data.rt,
          rushed_flag: rushed,
          events: events,
        });
        Object.keys(row).forEach(function (k) { data[k] = row[k]; });

        // Accumulate into the shared state for the summary trial.
        var s = stateRef.state;
        if (s.first_item_t === null) s.first_item_t = data.time_elapsed - (data.rt || 0);
        s.last_item_t = data.time_elapsed;
        s.n_completed += 1;
        if (rushed) s.n_rushed += 1;
        // Matrix[source_idx][target_idx] = rating.
        var i = EVENT_IDS.indexOf(pair.source);
        var j = EVENT_IDS.indexOf(pair.target);
        if (i >= 0 && j >= 0) s.matrix[i][j] = rating;
      },
    };
  }

  function buildSummaryTrial(storyId, stateRef) {
    return {
      type: jsPsychCallFunction,
      func: function () {
        // No-op during runtime; the work happens in on_finish.
        return null;
      },
      on_finish: function (data) {
        var s = stateRef.state;
        data.trial_type = 'pair_scaling_summary';
        data.task = 'pair_scaling_summary';
        data.story_id = storyId;
        data.n_pairs = s.n_completed;
        data.n_pairs_expected = s.n_total_pairs;
        data.n_rushed = s.n_rushed;
        data.block_rt_ms = s.last_item_t > s.first_item_t
          ? Math.round(s.last_item_t - s.first_item_t)
          : null;
        // The 8×8 directed causal matrix — the primary RSA object for this story.
        data.directed_matrix = s.matrix.map(function (row) { return row.slice(); });
        data.matrix_event_ids = EVENT_IDS.slice();
        data.presentation_order = s.presentation_order.slice();
      },
    };
  }

  /**
   * Build a full pair-scaling block for one story: 56 randomised item trials
   * followed by a block-summary trial that emits the 8×8 directed matrix.
   */
  function buildBlock(storyId) {
    var cards = EVENT_CARDS[storyId];
    if (!cards) throw new Error('No event cards for story_id=' + storyId);

    var pairs = buildAllOrderedPairs();
    if (CONFIG.pair_scaling.randomize_pair_order) {
      pairs = Utils.shuffle(pairs);
    }

    // Initialise 8×8 matrix with nulls (diagonal stays null; off-diagonal fills in).
    var matrix = [];
    for (var i = 0; i < 8; i++) {
      matrix.push(new Array(8).fill(null));
    }

    var stateRef = { state: {
      n_total_pairs: pairs.length,
      n_completed: 0,
      n_rushed: 0,
      first_item_t: null,
      last_item_t: null,
      matrix: matrix,
      presentation_order: pairs.map(function (p) { return [p.source, p.target]; }),
    }};

    var trials = pairs.map(function (p, idx) {
      return buildItemTrial(storyId, cards, p, idx, stateRef);
    });
    trials.push(buildSummaryTrial(storyId, stateRef));
    return trials;
  }

  return {
    buildBlock: buildBlock,
    _buildAllOrderedPairs: buildAllOrderedPairs,
  };
})();

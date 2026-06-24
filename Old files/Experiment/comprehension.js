// tasks/comprehension.js — comprehension check component.
//
// Per task design §5.2:
//   - 6 yes/no/unsure items per story
//   - Randomised item order
//   - Logged per-item response times
//
// Implementation choices:
//   - One item per screen (clean per-item RT).
//   - Fixed answer order: [Yes, No, Unsure] left-to-right.
//   - Emits 6 item-level rows + 1 block-level summary row per story.
//   - Rushed (< 1.5 s) and Slow (> 30 s) responses are FLAGGED, not excluded.
//   - Per Research Notes §5, items are pre-audited for subtle-cue neutrality.

var ComprehensionTask = (function () {

  /** Build a single item trial (one item per screen). */
  function buildItemTrial(storyId, itemData, onFinishHook) {
    var options = CONFIG.comprehension.response_options; // ['Yes','No','Unsure']
    var rushedMs = CONFIG.comprehension.response_time_flag_ms;
    var slowMs   = CONFIG.comprehension.response_time_slow_flag_ms;

    return {
      type: jsPsychHtmlButtonResponse,
      stimulus: [
        '<div class="comp-container">',
        '  <p class="comp-prompt">' + escapeHtml(itemData.text) + '</p>',
        '</div>',
      ].join('\n'),
      choices: options,
      button_html: function (choice) {
        return '<button class="jspsych-btn comp-btn">' + choice + '</button>';
      },
      data: {
        task: 'comprehension_item',
        story_id: storyId,
        item_id: itemData.id,
        item_role: itemData.role,
        item_events: itemData.events,   // array of event IDs this item covers
        correct_response: itemData.correct,
      },
      on_finish: function (data) {
        // jsPsych 8: data.response is the 0-indexed button chosen.
        var chosen = options[data.response];
        var isCorrect = (chosen === itemData.correct);
        var rushed = data.rt != null && data.rt < rushedMs;
        var slow   = data.rt != null && data.rt > slowMs;

        // Item-level event log (minimal — item_shown and response_clicked).
        var events = [
          { t: 0, type: 'item_shown' },
          { t: data.rt, type: 'response_clicked', choice: chosen },
        ];

        var row = DataHelpers.composeTrialRow({
          trial_type: 'comprehension_item',
          task: 'comprehension_item',
          story_id: storyId,
          item_id: itemData.id,
          item_text: itemData.text,
          item_role: itemData.role,
          item_events: itemData.events,
          response: chosen,
          response_index: data.response,
          correct_response: itemData.correct,
          is_correct: isCorrect,
          rt_ms: data.rt,
          rushed_flag: rushed,
          slow_flag: slow,
          events: events,
        });

        Object.keys(row).forEach(function (k) { data[k] = row[k]; });

        // Hook: allow caller to accumulate per-item stats for block summary.
        if (onFinishHook) onFinishHook(data);
      },
    };
  }

  /** Build a block-summary trial that doesn't display anything but emits a summary row. */
  function buildSummaryTrial(storyId, stateRef) {
    return {
      type: jsPsychCallFunction,
      func: function () {
        var s = stateRef.state;
        var blockRT = s.last_item_t - s.first_item_t;
        var row = DataHelpers.composeTrialRow({
          trial_type: 'comprehension_summary',
          task: 'comprehension_summary',
          story_id: storyId,
          n_items: s.n_total,
          n_correct: s.n_correct,
          n_rushed: s.n_rushed,
          n_slow: s.n_slow,
          accuracy: s.n_total > 0 ? (s.n_correct / s.n_total) : null,
          block_rt_ms: Math.round(blockRT),
          presentation_order: s.presentation_order,
        });
        // jsPsych callFunction data is sparse; attach via on_finish alternative.
        // Here we use a post hoc data update below.
        return row;
      },
      on_finish: function (data) {
        // Copy summary fields into the data record.
        var s = stateRef.state;
        data.trial_type = 'comprehension_summary';
        data.task = 'comprehension_summary';
        data.story_id = storyId;
        data.n_items = s.n_total;
        data.n_correct = s.n_correct;
        data.n_rushed = s.n_rushed;
        data.n_slow = s.n_slow;
        data.accuracy = s.n_total > 0 ? (s.n_correct / s.n_total) : null;
        data.block_rt_ms = s.last_item_t > s.first_item_t
          ? Math.round(s.last_item_t - s.first_item_t)
          : null;
        data.presentation_order = s.presentation_order.slice();
      },
    };
  }

  /**
   * Build a full comprehension block for one story: 6 randomised item trials
   * followed by a block-summary trial. Returns an array of trials (push onto timeline).
   */
  function buildBlock(storyId) {
    var storyItems = COMPREHENSION_ITEMS.stories[storyId];
    if (!storyItems) {
      throw new Error('No comprehension items found for story_id=' + storyId);
    }
    var items = storyItems.items.slice();
    if (CONFIG.comprehension.randomize_item_order) {
      items = Utils.shuffle(items);
    }

    // Shared mutable state object so summary trial can see item-level accumulation.
    var stateRef = { state: {
      n_total: 0,
      n_correct: 0,
      n_rushed: 0,
      n_slow: 0,
      first_item_t: null,
      last_item_t: null,
      presentation_order: items.map(function (it) { return it.id; }),
    }};

    function recordItem(data) {
      var s = stateRef.state;
      s.n_total += 1;
      if (data.is_correct) s.n_correct += 1;
      if (data.rushed_flag) s.n_rushed += 1;
      if (data.slow_flag) s.n_slow += 1;
      if (s.first_item_t === null) s.first_item_t = data.time_elapsed - (data.rt || 0);
      s.last_item_t = data.time_elapsed;
    }

    var trials = items.map(function (it) {
      return buildItemTrial(storyId, it, recordItem);
    });
    trials.push(buildSummaryTrial(storyId, stateRef));
    return trials;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  return {
    buildBlock: buildBlock,
  };
})();

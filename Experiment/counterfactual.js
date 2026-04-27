// tasks/counterfactual.js — counterfactual probes task.
//
// Per task design §7:
//   - 8 probes per story: 6 anchor (E1..E6 → E7) + 1 sibling null + 1 reverse null (E8 → E7).
//   - One probe per screen.
//   - Randomised probe order per participant.
//   - 5-point signed scale: 1 = Much less likely, 3 = No change, 5 = Much more likely.
//   - Probe prompt: "If [antecedent], would [consequent] still have occurred?"
//
// Output:
//   - 8 item rows per story (task: 'counterfactual_item') with role, antecedent,
//     consequent, rating, rt, flags
//   - 1 summary row (task: 'counterfactual_summary') with the length-6 anchor
//     vector + 2 null-control ratings + discrimination index (per §7.5)

var CounterfactualTask = (function () {

  var SCALE_LABELS = CONFIG.counterfactual.scale_labels; // length-5 array
  // Numeric values mapped to scale positions: 1..5
  var SCALE_VALUES = SCALE_LABELS.map(function (_, i) { return i + 1; });

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function renderStimulusHTML(probe) {
    return [
      '<div class="cf-container">',
      '  <p class="cf-prompt">' + escapeHtml(probe.prompt) + '</p>',
      '</div>',
    ].join('\n');
  }

  function buildItemTrial(storyId, probe, probeIndex, stateRef) {
    return {
      type: jsPsychHtmlButtonResponse,
      stimulus: renderStimulusHTML(probe),
      choices: SCALE_LABELS,
      button_html: function (choice, choice_index) {
        return '<button class="jspsych-btn cf-btn" data-rating="' + (choice_index + 1) + '">' + choice + '</button>';
      },
      data: {
        task: 'counterfactual_item',
        story_id: storyId,
        probe_id: probe.probe_id,
        probe_role: probe.role,
        antecedent_event_id: probe.antecedent_event_id,
        consequent_event_id: probe.consequent_event_id,
        probe_index: probeIndex,
      },
      on_finish: function (data) {
        var rating = data.response + 1; // 1..5 on the signed scale
        var label = SCALE_LABELS[data.response];
        var events = [
          { t: 0, type: 'probe_shown', probe_id: probe.probe_id },
          { t: data.rt, type: 'response_clicked', rating: rating, label: label },
        ];

        var row = DataHelpers.composeTrialRow({
          trial_type: 'counterfactual_item',
          task: 'counterfactual_item',
          story_id: storyId,
          probe_id: probe.probe_id,
          probe_role: probe.role,
          antecedent_event_id: probe.antecedent_event_id,
          consequent_event_id: probe.consequent_event_id,
          probe_index: probeIndex,
          prompt_text: probe.prompt,
          rating: rating,
          rating_label: label,
          rt_ms: data.rt,
          events: events,
        });
        Object.keys(row).forEach(function (k) { data[k] = row[k]; });

        // Accumulate into summary state.
        var s = stateRef.state;
        if (s.first_item_t === null) s.first_item_t = data.time_elapsed - (data.rt || 0);
        s.last_item_t = data.time_elapsed;
        if (probe.role === 'anchor') {
          s.anchor_vector[probe.antecedent_event_id] = rating;
        } else if (probe.role === 'sibling_null') {
          s.sibling_null_rating = rating;
        } else if (probe.role === 'reverse_null') {
          s.reverse_null_rating = rating;
        }
      },
    };
  }

  function buildSummaryTrial(storyId, stateRef) {
    return {
      type: jsPsychCallFunction,
      func: function () { return null; },
      on_finish: function (data) {
        var s = stateRef.state;
        // Build length-6 anchor vector in canonical E1..E6 order for easy matrix storage.
        var anchor = ['E1','E2','E3','E4','E5','E6'].map(function (eid) {
          return s.anchor_vector[eid] != null ? s.anchor_vector[eid] : null;
        });
        // Discrimination index (per §7.5): mean anchor magnitude vs mean null magnitude.
        // Magnitude is |rating - 3| (distance from "no change" baseline).
        var anchorMagnitudes = anchor.filter(function (v) { return v != null; })
          .map(function (v) { return Math.abs(v - 3); });
        var nullMagnitudes = [s.sibling_null_rating, s.reverse_null_rating]
          .filter(function (v) { return v != null; })
          .map(function (v) { return Math.abs(v - 3); });
        var meanAnchor = anchorMagnitudes.length
          ? anchorMagnitudes.reduce(function (a, b) { return a + b; }, 0) / anchorMagnitudes.length : null;
        var meanNull = nullMagnitudes.length
          ? nullMagnitudes.reduce(function (a, b) { return a + b; }, 0) / nullMagnitudes.length : null;
        var discrimination = (meanAnchor != null && meanNull != null)
          ? meanAnchor - meanNull : null;

        data.trial_type = 'counterfactual_summary';
        data.task = 'counterfactual_summary';
        data.story_id = storyId;
        data.anchor_vector = anchor;  // [E1, E2, E3, E4, E5, E6] ratings
        data.sibling_null_rating = s.sibling_null_rating;
        data.reverse_null_rating = s.reverse_null_rating;
        data.discrimination_index = discrimination;
        data.block_rt_ms = s.last_item_t > s.first_item_t
          ? Math.round(s.last_item_t - s.first_item_t) : null;
        data.presentation_order = s.presentation_order.slice();
      },
    };
  }

  /**
   * Build a full CF block for one story: 8 randomised probe trials + 1 summary.
   */
  function buildBlock(storyId) {
    var storyData = CF_PROBES.stories[storyId];
    if (!storyData) throw new Error('No CF probes for story_id=' + storyId);
    var probes = storyData.probes.slice();
    // Randomise order per participant.
    probes = Utils.shuffle(probes);

    var stateRef = { state: {
      first_item_t: null,
      last_item_t: null,
      anchor_vector: {},
      sibling_null_rating: null,
      reverse_null_rating: null,
      presentation_order: probes.map(function (p) { return p.probe_id; }),
    }};

    var trials = probes.map(function (p, idx) {
      return buildItemTrial(storyId, p, idx, stateRef);
    });
    trials.push(buildSummaryTrial(storyId, stateRef));
    return trials;
  }

  return {
    buildBlock: buildBlock,
  };
})();

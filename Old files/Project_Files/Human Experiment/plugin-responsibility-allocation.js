(function (jspsych) {
  "use strict";

  if (!jspsych || !jspsych.ParameterType) {
    console.warn("responsibility-allocation plugin: jsPsychModule not available at load time");
    return;
  }

  var info = {
    name: "responsibility-allocation",
    parameters: {
      title: {
        type: jspsych.ParameterType.STRING,
        default: "Responsibility Allocation"
      },
      instructions: {
        type: jspsych.ParameterType.HTML_STRING,
        default: "Distribute exactly 100 points across the events below to indicate how responsible each was for the incident that occurred."
      },
      events: {
        type: jspsych.ParameterType.STRING,
        array: true,
        default: []
      },
      exclude_indices: {
        type: jspsych.ParameterType.INT,
        array: true,
        default: [7]
      },
      total_points: {
        type: jspsych.ParameterType.INT,
        default: 100
      },
      button_label: {
        type: jspsych.ParameterType.STRING,
        default: "Continue"
      }
    }
  };

  class ResponsibilityAllocationPlugin {
    constructor(jsPsych) {
      this.jsPsych = jsPsych;
    }

    trial(display_element, trial) {
      var t0 = performance.now();
      var target = trial.total_points;
      var excludeSet = new Set(trial.exclude_indices || []);

      var events = (trial.events || []).map(function (txt, idx) {
        return {
          id: "e" + (idx + 1),
          canonicalIndex: idx,
          text: String(txt).replace(/^E\d+:\s*/, "")
        };
      }).filter(function (ev) {
        return !excludeSet.has(ev.canonicalIndex);
      });

      var rows = events.map(function (ev) {
        return '<div class="ra-row">' +
          '<span class="ra-label">' + ev.text + '</span>' +
          '<input class="ra-input" type="number" min="0" max="' + target + '" value="0" ' +
          'name="' + ev.id + '" data-event-id="' + ev.id + '" data-canonical-index="' + ev.canonicalIndex + '">' +
          '</div>';
      }).join("");

      display_element.innerHTML =
        '<div class="ra-wrap"><div class="ra-panel">' +
        '<h2>' + trial.title + '</h2>' +
        '<p class="ra-instructions">' + trial.instructions + '</p>' +
        '<div class="ra-list">' + rows + '</div>' +
        '<div class="ra-total" id="ra-total">Total: <span id="ra-sum">0</span> / ' + target + '</div>' +
        '<p id="ra-error" class="ra-error" style="display:none;">Points must add up to exactly ' + target + '.</p>' +
        '<button id="ra-next" class="jspsych-btn">' + trial.button_label + '</button>' +
        '</div></div>';

      var inputs = display_element.querySelectorAll(".ra-input");
      var sumEl = display_element.querySelector("#ra-sum");
      var totalEl = display_element.querySelector("#ra-total");
      var errorEl = display_element.querySelector("#ra-error");
      var nextBtn = display_element.querySelector("#ra-next");

      function getSum() {
        var s = 0;
        for (var i = 0; i < inputs.length; i++) {
          var v = parseInt(inputs[i].value, 10);
          if (!isNaN(v) && v >= 0) s += v;
        }
        return s;
      }

      function updateTotal() {
        var s = getSum();
        sumEl.textContent = s;
        if (s === target) {
          totalEl.classList.remove("ra-total-over");
          totalEl.classList.add("ra-total-ok");
        } else {
          totalEl.classList.remove("ra-total-ok");
          totalEl.classList.toggle("ra-total-over", s > target);
        }
        errorEl.style.display = "none";
      }

      for (var i = 0; i < inputs.length; i++) {
        inputs[i].addEventListener("input", updateTotal);
        inputs[i].addEventListener("focus", function () { this.select(); });
      }

      var plugin = this;

      nextBtn.addEventListener("click", function () {
        var s = getSum();
        if (s !== target) {
          errorEl.style.display = "block";
          return;
        }

        var rt = Math.round(performance.now() - t0);
        var allocation = [];
        var trialData = { rt: rt };

        for (var i = 0; i < inputs.length; i++) {
          var inp = inputs[i];
          var pts = parseInt(inp.value, 10) || 0;
          var eid = inp.dataset.eventId;
          trialData[eid + "_points"] = pts;
          allocation.push({
            id: eid,
            text: events[i].text,
            points: pts
          });
        }
        trialData.allocation = allocation;

        display_element.innerHTML = "";
        plugin.jsPsych.finishTrial(trialData);
      });
    }
  }

  ResponsibilityAllocationPlugin.info = info;
  window.jsPsychResponsibilityAllocation = ResponsibilityAllocationPlugin;
})(typeof jsPsychModule !== "undefined" ? jsPsychModule : null);

// Guard against double execution (index.js bootstrap + index.html script tag)
if (typeof window._experimentJsRan !== "undefined") {
  // already executed — skip
} else {
window._experimentJsRan = true;

function getParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

function getNumericParam(name, fallbackValue) {
  const rawValue = getParam(name);
  if (rawValue === null || rawValue.trim() === "") {
    return fallbackValue;
  }
  const value = Number(rawValue);
  return Number.isFinite(value) ? value : fallbackValue;
}

const runtimeConfig = {
  debug: getParam("debug") === "1" || window.location.hostname === "localhost" || window.location.protocol === "file:",
  completionUrl: getParam("completion_url") || "",
  disqualificationUrl: getParam("disqualify_url") || "disqualified.html",
  comprehensionMinCorrect: getNumericParam("comprehension_min_correct", 1),
  comprehensionMaxWrong: getNumericParam("comprehension_max_wrong", 3)
};

const participantMeta = {
  participant_id: getParam("participant_id") || getParam("PROLIFIC_PID") || "",
  study_id: getParam("study_id") || getParam("STUDY_ID") || "",
  session_id: getParam("session_id") || getParam("SESSION_ID") || ""
};

const counterfactual_scale = ["1 Much less likely", "2 Less likely", "3 No change/Unsure", "4 More likely", "5 Much more likely"];
const y_n_u = ["Yes", "No", "Unsure"];

// Fallback registration for Cognition deployments where external custom plugins can fail to load.
if (typeof window.jsPsychCausalPairScale === "undefined" && typeof window.jsPsychModule !== "undefined") {
  (function registerCausalPairScaleFallback(jspsych) {
    const info = {
      name: "causal-pair-scale",
      parameters: {
        heading: {
          type: jspsych.ParameterType.HTML_STRING,
          default: ""
        },
        instruction: {
          type: jspsych.ParameterType.HTML_STRING,
          default: "Indicate the likelihood that the event on the left causally contributed to the event on the right."
        },
        left_event: {
          type: jspsych.ParameterType.HTML_STRING,
          default: undefined
        },
        right_event: {
          type: jspsych.ParameterType.HTML_STRING,
          default: undefined
        },
        labels: {
          type: jspsych.ParameterType.STRING,
          array: true,
          default: []
        },
        required: {
          type: jspsych.ParameterType.BOOL,
          default: true
        },
        button_label: {
          type: jspsych.ParameterType.STRING,
          default: "Continue"
        }
      }
    };

    class CausalPairScalePlugin {
      constructor(jsPsych) {
        this.jsPsych = jsPsych;
      }

      trial(display_element, trial) {
        const trialStart = performance.now();
        const optionsHtml = trial.labels
          .map((label, i) => {
            return `
            <label class="causal-option">
              <input type="radio" name="causal_scale" value="${i}">
              <span>${label}</span>
            </label>
          `;
          })
          .join("");

        const headingHtml = trial.heading ? "<h2>" + trial.heading + "</h2>" : "";

        display_element.innerHTML = `
        <div class="causal-card">
          ${headingHtml}
          <p class="causal-instruction">${trial.instruction}</p>
          <div class="causal-events">
            <div class="causal-event-box causal-left-event">${trial.left_event}</div>
            <div class="causal-arrow" aria-hidden="true">&rarr;</div>
            <div class="causal-event-box causal-right-event">${trial.right_event}</div>
          </div>
          <div class="causal-scale" role="group" aria-label="Causal contribution scale">
            ${optionsHtml}
          </div>
          <p id="causal-error" class="causal-error" style="display:none;">Please choose one response before continuing.</p>
          <button id="causal-next" class="jspsych-btn">${trial.button_label}</button>
        </div>
      `;

        display_element.querySelector("#causal-next").addEventListener("click", () => {
          const selected = display_element.querySelector('input[name="causal_scale"]:checked');
          if (!selected && trial.required) {
            display_element.querySelector("#causal-error").style.display = "block";
            return;
          }

          const rt = Math.round(performance.now() - trialStart);
          const responseIndex = selected ? Number(selected.value) : null;
          const trialData = {
            left_event: trial.left_event,
            right_event: trial.right_event,
            response_index: responseIndex,
            response_label: responseIndex !== null ? trial.labels[responseIndex] : null,
            rt: rt
          };

          display_element.innerHTML = "";
          this.jsPsych.finishTrial(trialData);
        });
      }
    }

    CausalPairScalePlugin.info = info;
    window.jsPsychCausalPairScale = CausalPairScalePlugin;
  })(window.jsPsychModule);
}

// Fallback: ResponsibilityAllocation plugin
if (typeof window.jsPsychResponsibilityAllocation === "undefined" && typeof window.jsPsychModule !== "undefined") {
  (function (jspsych) {
    var info = {
      name: "responsibility-allocation",
      parameters: {
        title: { type: jspsych.ParameterType.STRING, default: "Responsibility Allocation" },
        instructions: { type: jspsych.ParameterType.HTML_STRING, default: "" },
        events: { type: jspsych.ParameterType.STRING, array: true, default: [] },
        exclude_indices: { type: jspsych.ParameterType.INT, array: true, default: [7] },
        total_points: { type: jspsych.ParameterType.INT, default: 100 },
        button_label: { type: jspsych.ParameterType.STRING, default: "Continue" }
      }
    };
    class P {
      constructor(j) { this.jsPsych = j; }
      trial(el, trial) {
        var t0 = performance.now(), target = trial.total_points, excludeSet = new Set(trial.exclude_indices || []);
        var events = (trial.events || []).map(function (t, i) {
          return { id: "e" + (i + 1), canonicalIndex: i, text: String(t).replace(/^E\d+:\s*/, "") };
        }).filter(function (e) { return !excludeSet.has(e.canonicalIndex); });
        var rows = events.map(function (e) {
          return '<div class="ra-row"><span class="ra-label">' + e.text + '</span>' +
            '<input class="ra-input" type="number" min="0" max="' + target + '" value="0" name="' + e.id + '" data-event-id="' + e.id + '" data-canonical-index="' + e.canonicalIndex + '"></div>';
        }).join("");
        el.innerHTML = '<div class="ra-wrap"><div class="ra-panel"><h2>' + trial.title + '</h2>' +
          '<p class="ra-instructions">' + trial.instructions + '</p><div class="ra-list">' + rows + '</div>' +
          '<div class="ra-total" id="ra-total">Total: <span id="ra-sum">0</span> / ' + target + '</div>' +
          '<p id="ra-error" class="ra-error" style="display:none;">Points must add up to exactly ' + target + '.</p>' +
          '<button id="ra-next" class="jspsych-btn">' + trial.button_label + '</button></div></div>';
        var inputs = el.querySelectorAll(".ra-input"), sumEl = el.querySelector("#ra-sum"),
            totalEl = el.querySelector("#ra-total"), errorEl = el.querySelector("#ra-error");
        function getSum() { var s = 0; for (var i = 0; i < inputs.length; i++) { var v = parseInt(inputs[i].value, 10); if (!isNaN(v) && v >= 0) s += v; } return s; }
        function updateTotal() {
          var s = getSum(); sumEl.textContent = s; errorEl.style.display = "none";
          totalEl.classList.toggle("ra-total-ok", s === target);
          totalEl.classList.toggle("ra-total-over", s > target);
        }
        for (var i = 0; i < inputs.length; i++) { inputs[i].addEventListener("input", updateTotal); inputs[i].addEventListener("focus", function () { this.select(); }); }
        var plugin = this;
        el.querySelector("#ra-next").addEventListener("click", function () {
          if (getSum() !== target) { errorEl.style.display = "block"; return; }
          var rt = Math.round(performance.now() - t0), alloc = [], td = { rt: rt };
          for (var i = 0; i < inputs.length; i++) {
            var pts = parseInt(inputs[i].value, 10) || 0;
            td[inputs[i].dataset.eventId + "_points"] = pts;
            alloc.push({ id: inputs[i].dataset.eventId, text: events[i].text, points: pts });
          }
          td.allocation = alloc; el.innerHTML = ""; plugin.jsPsych.finishTrial(td);
        });
      }
    }
    P.info = info; window.jsPsychResponsibilityAllocation = P;
  })(window.jsPsychModule);
}

// Fallback: CardSort plugin
if (typeof window.jsPsychCardSort === "undefined" && typeof window.jsPsychModule !== "undefined") {
  (function (jspsych) {
    var info = {
      name: "card-sort",
      parameters: {
        title: { type: jspsych.ParameterType.STRING, default: "Event Ordering" },
        instructions: { type: jspsych.ParameterType.HTML_STRING, default: "" },
        events: { type: jspsych.ParameterType.STRING, array: true, default: [] },
        button_label: { type: jspsych.ParameterType.STRING, default: "Continue" },
        shuffle: { type: jspsych.ParameterType.BOOL, default: true }
      }
    };
    function shuffle(arr) {
      var a = arr.slice();
      do { for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; } }
      while (a.length > 1 && a.every(function (v, i) { return v.id === arr[i].id; }));
      return a;
    }
    function kendallTau(r) {
      var n = r.length, c = 0, d = 0;
      for (var i = 0; i < n; i++) for (var j = i + 1; j < n; j++) { if (r[i] < r[j]) c++; else if (r[i] > r[j]) d++; }
      var p = n * (n - 1) / 2; return p === 0 ? 0 : +((c - d) / p).toFixed(4);
    }
    class CS {
      constructor(j) { this.jsPsych = j; }
      trial(el, trial) {
        var t0 = performance.now(), mc = 0;
        var parsed = (trial.events || []).map(function (t, i) { return { id: "e" + (i + 1), canonicalIndex: i, text: String(t).replace(/^E\d+:\s*/, "") }; });
        var order = trial.shuffle !== false ? shuffle(parsed) : parsed.slice();
        var initOrder = order.map(function (e) { return e.id; });
        el.innerHTML = '<div class="cs-wrap"><div class="cs-panel"><h2>' + trial.title + '</h2><p class="cs-instructions">' + trial.instructions + '</p>' +
          '<div class="cs-list-area"><div class="cs-endpoint cs-endpoint-top">&#9650; Earliest (first)</div><div class="cs-list" id="cs-list"></div>' +
          '<div class="cs-endpoint cs-endpoint-bottom">&#9660; Latest (last)</div></div>' +
          '<button id="cs-next" class="jspsych-btn">' + trial.button_label + '</button></div></div>';
        var listEl = el.querySelector("#cs-list");
        order.forEach(function (ev, idx) {
          var d = document.createElement("div"); d.className = "cs-item"; d.dataset.eventId = ev.id; d.dataset.canonicalIndex = String(ev.canonicalIndex);
          d.setAttribute("tabindex", "0"); d.style.touchAction = "none";
          d.innerHTML = '<span class="cs-pos">' + (idx + 1) + '</span><span class="cs-text">' + ev.text + '</span><span class="cs-handle" aria-hidden="true">&#x2807;</span>';
          listEl.appendChild(d);
        });
        function renum() { var it = listEl.querySelectorAll(".cs-item"); for (var i = 0; i < it.length; i++) it[i].querySelector(".cs-pos").textContent = i + 1; }
        var drag = null;
        function onDown(e) {
          var item = e.target.closest(".cs-item"); if (!item || !listEl.contains(item) || (typeof e.button === "number" && e.button !== 0)) return; e.preventDefault();
          var rect = item.getBoundingClientRect(), oi = Array.from(listEl.querySelectorAll(".cs-item")).indexOf(item);
          var ghost = item.cloneNode(true); ghost.classList.add("cs-ghost");
          ghost.style.cssText = "position:fixed;width:" + rect.width + "px;left:" + rect.left + "px;top:" + rect.top + "px;z-index:10000;pointer-events:none;margin:0;";
          document.body.appendChild(ghost);
          var ph = document.createElement("div"); ph.className = "cs-placeholder"; ph.style.height = rect.height + "px"; listEl.insertBefore(ph, item); item.remove();
          drag = { item: item, ghost: ghost, ph: ph, offX: e.clientX - rect.left, offY: e.clientY - rect.top, origIndex: oi };
          document.addEventListener("pointermove", onMove); document.addEventListener("pointerup", onUp);
        }
        function onMove(e) {
          if (!drag) return; drag.ghost.style.left = (e.clientX - drag.offX) + "px"; drag.ghost.style.top = (e.clientY - drag.offY) + "px";
          var ch = Array.from(listEl.children), before = null;
          for (var i = 0; i < ch.length; i++) { if (ch[i] === drag.ph) continue; var r = ch[i].getBoundingClientRect(); if (e.clientY < r.top + r.height / 2) { before = ch[i]; break; } }
          if (before) listEl.insertBefore(drag.ph, before); else listEl.appendChild(drag.ph);
        }
        function onUp() {
          if (!drag) return; listEl.insertBefore(drag.item, drag.ph); drag.ph.remove(); drag.ghost.remove();
          if (Array.from(listEl.querySelectorAll(".cs-item")).indexOf(drag.item) !== drag.origIndex) mc++;
          renum(); document.removeEventListener("pointermove", onMove); document.removeEventListener("pointerup", onUp); drag = null;
        }
        listEl.addEventListener("pointerdown", onDown);
        var plugin = this;
        el.querySelector("#cs-next").addEventListener("click", function () {
          var items = Array.from(listEl.querySelectorAll(".cs-item"));
          var ids = items.map(function (e) { return e.dataset.eventId; });
          var ci = items.map(function (e) { return Number(e.dataset.canonicalIndex); });
          var td = { submitted_order: ids, initial_order: initOrder, kendall_tau: kendallTau(ci), total_moves: mc, rt: Math.round(performance.now() - t0) };
          for (var i = 0; i < items.length; i++) td[items[i].dataset.eventId + "_rank"] = i + 1;
          listEl.removeEventListener("pointerdown", onDown); el.innerHTML = ""; plugin.jsPsych.finishTrial(td);
        });
      }
    }
    CS.info = info; window.jsPsychCardSort = CS;
  })(window.jsPsychModule);
}

// --- Canonical key events for the card task (E1–E8) ---
// Source: Pilot Human Experiment.pdf canonical event lists. :contentReference[oaicite:4]{index=4} :contentReference[oaicite:5]{index=5} :contentReference[oaicite:6]{index=6}

const canonicalCardEvents = {
  medical: [
    "E1: A hospital administrator approves a policy reducing overnight staffing.",
    "E2: A contractor disables a ventilator alarm during maintenance.",
    "E3: The contractor leaves without re-enabling the alarm.",
    "E4: A nurse is assigned more patients than usual.",
    "E5: A brief power interruption occurs.",
    "E6: The ventilator stops without sounding an alarm.",
    "E7: The nurse discovers a patient in respiratory distress.",
    "E8: An inquest later reviews the incident."
  ],
  workplace: [
    "E1: A manager approves a plan to consolidate server resources.",
    "E2: A technician updates configuration settings on a backup system.",
    "E3: The technician does not restart one service.",
    "E4: An analyst begins processing a large dataset.",
    "E5: System load increases across the network.",
    "E6: A critical service stops responding.",
    "E7: Users report being unable to access shared files.",
    "E8: An internal review examines the incident."
  ],
  coastal: [
    "E1: A city council approves a pilot floodgate project for a coastal road.",
    "E2: Contractors install temporary barriers and signage near the road.",
    "E3: A utilities team schedules a routine inspection of a pump station.",
    "E4: The inspection requires a temporary shutdown of the pump station.",
    "E5: A weather service issues a coastal surge warning.",
    "E6: The floodgate is activated during the warning period.",
    "E7: Water enters the road area and traffic is halted.",
    "E8: A municipal review later examines the sequence of events."
  ]
};

function getCanonicalCardEventsForStory(storyTitle) {
  // Medical short + medical medium (fluff) should use the same canonical E1–E8 list. :contentReference[oaicite:7]{index=7}
  const t = (storyTitle || "").toLowerCase();
  if (t.includes("hospital ward")) return canonicalCardEvents.medical;
  if (t.includes("server outage")) return canonicalCardEvents.workplace;
  if (t.includes("coastal road floodgate")) return canonicalCardEvents.coastal;
  return null;
}


const medicalShortQuestions = {
  counterfactual: [
    { left_event: "The contractor left the room without re-enabling the alarm.", right_event: "The ventilator stopped without sounding an alarm.", labels: counterfactual_scale, required: true },
    { left_event: "A brief interruption in power occurred on the ward.", right_event: "The ventilator stopped without sounding an alarm.", labels: counterfactual_scale, required: true },
    { left_event: "The nurse was assigned more patients than usual.", right_event: "The nurse entered the room and found a patient experiencing respiratory distress.", labels: counterfactual_scale, required: true },
    { left_event: "The maintenance contractor disabled a ventilator alarm during a routine test.", right_event: "The ventilator stopped without sounding an alarm.", labels: counterfactual_scale, required: true }
  ],
  comprehension: [
    { prompt: "Was an inquest mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Was the nurse assigned less patients than usual?", labels: y_n_u, required: true, correct: "No" },
    { prompt: "Was a power interruption mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Was a maintenance contractor mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Was a ventilator alarm mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Did the patient experience a heart attack?", labels: y_n_u, required: true, correct: "No" }
  ],
  outcome_description: "the incident in which a patient experienced respiratory distress and an inquest was held"
};

const medicalMediumQuestions = {
  counterfactual: [
    { left_event: "The contractor left without re-enabling the alarm.", right_event: "The ventilator stopped operating without sounding an alarm.", labels: counterfactual_scale, required: true },
    { left_event: "A brief interruption in power occurred on the ward.", right_event: "The ventilator stopped operating without sounding an alarm.", labels: counterfactual_scale, required: true },
    { left_event: "The nurse was assigned more patients than usual.", right_event: "The nurse entered the room and found a patient experiencing respiratory distress.", labels: counterfactual_scale, required: true },
    { left_event: "The maintenance contractor disabled a ventilator alarm while performing a standard test.", right_event: "The ventilator stopped operating without sounding an alarm.", labels: counterfactual_scale, required: true }
  ],
  comprehension: [
    { prompt: "Was an inquest mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Was the nurse assigned less patients than usual?", labels: y_n_u, required: true, correct: "No" },
    { prompt: "Was a power interruption mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Was a maintenance contractor mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Was a ventilator alarm mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Did the patient experience a heart attack?", labels: y_n_u, required: true, correct: "No" }
  ],
  outcome_description: "the incident in which a patient experienced respiratory distress and an inquest was held"
};

const workplaceQuestions = {
  counterfactual: [
    { left_event: "The technician did not restart one of the services.", right_event: "A critical service stopped responding.", labels: counterfactual_scale, required: true },
    { left_event: "The analyst began processing a large dataset.", right_event: "System load increased across the network.", labels: counterfactual_scale, required: true },
    { left_event: "System load increased across the network.", right_event: "Users reported they were unable to access shared files.", labels: counterfactual_scale, required: true },
    { left_event: "A critical service stopped responding.", right_event: "An internal review examined the incident.", labels: counterfactual_scale, required: true }
  ],
  comprehension: [
    { prompt: "Was an internal review mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Did the technician restart one of the services?", labels: y_n_u, required: true, correct: "No" },
    { prompt: "Was a backup system mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Was a large dataset mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Were shared files mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Did a critical service stop responding?", labels: y_n_u, required: true, correct: "Yes" }
  ],
  outcome_description: "the incident in which users lost access to shared files and an internal review was held"
};

const coastalQuestions = {
  counterfactual: [
    { left_event: "A weather service issued a coastal surge warning.", right_event: "The floodgate was activated during the warning period.", labels: counterfactual_scale, required: true },
    { left_event: "The inspection required a temporary shutdown of the pump station.", right_event: "The floodgate was activated during the warning period.", labels: counterfactual_scale, required: true },
    { left_event: "The floodgate was activated during the warning period.", right_event: "Water entered the road area and traffic was halted.", labels: counterfactual_scale, required: true },
    { left_event: "Contractors installed temporary barriers and signage near the road.", right_event: "Water entered the road area and traffic was halted.", labels: counterfactual_scale, required: true }
  ],
  comprehension: [
    { prompt: "Was a coastal surge warning mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Did the floodgate stop being activated during the warning period?", labels: y_n_u, required: true, correct: "No" },
    { prompt: "Was a pump station mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Were temporary barriers or signage mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Was a municipal review mentioned in the story?", labels: y_n_u, required: true, correct: "Yes" },
    { prompt: "Did a utilities team schedule a routine inspection of the road?", labels: y_n_u, required: true, correct: "No" }
  ],
  outcome_description: "the incident in which water entered the road area and a municipal review was held"
};

const storyBank = {
  "Stories/Medical Short Linear.pdf": {
    title: "Hospital Ward Incident",
    paragraphs: [
      "Several weeks before the incident, a hospital administrator approved a policy to reduce overnight staffing levels on the ward.",
      "On a later day, a maintenance contractor disabled a ventilator alarm while performing a routine test.",
      "After completing the test, the contractor left the room without re-enabling the alarm.",
      "On the night of the incident, a nurse was assigned more patients than usual.",
      "Later that night, a brief interruption in power occurred on the ward.",
      "Following the power interruption, the ventilator stopped operating without sounding an alarm.",
      "Some time later, the nurse entered the room and found a patient experiencing respiratory distress.",
      "In the months that followed, an inquest reviewed the sequence of events."
    ],
    questions: medicalShortQuestions
  },
  "Stories/Medical Short Linear.copy.pdf": {
    title: "Hospital Ward Incident",
    paragraphs: [
      "Several weeks before the incident, a hospital administrator approved a policy to reduce overnight staffing levels on the ward.",
      "On a later day, a maintenance contractor disabled a ventilator alarm while performing a routine test.",
      "After completing the test, the contractor left the room without re-enabling the alarm.",
      "On the night of the incident, a nurse was assigned more patients than usual.",
      "Later that night, a brief interruption in power occurred on the ward.",
      "Following the power interruption, the ventilator stopped operating without sounding an alarm.",
      "Some time later, the nurse entered the room and found a patient experiencing respiratory distress.",
      "In the months that followed, an inquest reviewed the sequence of events."
    ],
    questions: medicalShortQuestions
  },
  "Stories/Medical Short NonLinear.pdf": {
    title: "Hospital Ward Incident",
    paragraphs: [
      "In the months that followed, an inquest reviewed the sequence of events.",
      "Some time earlier, the nurse entered the room and found a patient experiencing respiratory distress.",
      "Later that night, the ventilator stopped operating without sounding an alarm.",
      "Several weeks before the incident, a hospital administrator approved a policy to reduce overnight staffing levels on the ward.",
      "On the night of the incident, a nurse was assigned more patients than usual.",
      "On a later day, a maintenance contractor disabled a ventilator alarm while performing a routine test.",
      "After completing the test, the contractor left the room without re-enabling the alarm.",
      "Earlier that same night, a brief interruption in power occurred on the ward."
    ],
    questions: medicalShortQuestions
  },
  "Stories/Medical Medium Fluff.pdf": {
    title: "Hospital Ward Incident (Detailed)",
    paragraphs: [
      "Several weeks before the incident, during a routine administrative review of hospital operations, a hospital administrator approved a policy to reduce overnight staffing levels on the ward as part of a broader efficiency plan.",
      "On a later day, during scheduled equipment maintenance in one of the patient rooms, a maintenance contractor disabled a ventilator alarm while performing a standard test of the machine's functions.",
      "After completing the test and documenting the procedure, the contractor left the room without re-enabling the alarm before moving on to another task elsewhere in the building.",
      "On the night of the incident, as staff assignments were being finalized at the start of the shift, a nurse was assigned more patients than usual across several rooms on the ward.",
      "Later that night, while activity on the ward remained relatively quiet, a brief interruption in power occurred, affecting several pieces of equipment for a short period of time.",
      "Following the power interruption, the ventilator stopped operating without sounding an alarm, and the room remained otherwise undisturbed for some time.",
      "Some time later, during a scheduled round, the nurse entered the room and found a patient experiencing respiratory distress.",
      "In the months that followed, after records and logs had been collected, an inquest reviewed the sequence of events surrounding the incident."
    ],
    questions: medicalMediumQuestions
  },
  "Stories/Medical Medium Fluff NonLinear.pdf": {
    title: "Hospital Ward Incident (Detailed)",
    paragraphs: [
      "In the months that followed, after records and logs had been collected, an inquest reviewed the sequence of events surrounding the incident.",
      "Some time earlier, during a scheduled round later in the shift, the nurse entered the room and found a patient experiencing respiratory distress.",
      "Later that night, after a short disruption to electrical systems on the ward, the ventilator stopped operating without sounding an alarm, and the room remained otherwise undisturbed.",
      "Several weeks before the incident, during a routine administrative review of hospital operations, a hospital administrator approved a policy to reduce overnight staffing levels on the ward as part of a broader efficiency plan.",
      "On the night of the incident, as staff assignments were being finalized at the start of the shift, a nurse was assigned more patients than usual across several rooms on the ward.",
      "On a later day, during scheduled equipment maintenance in one of the patient rooms, a maintenance contractor disabled a ventilator alarm while performing a standard test of the machine's functions.",
      "After completing the test and documenting the procedure, the contractor left the room without re-enabling the alarm before moving on to another task elsewhere in the building.",
      "Earlier that same night, while activity on the ward remained relatively quiet, a brief interruption in power occurred, affecting several pieces of equipment for a short period of time."
    ],
    questions: medicalMediumQuestions
  },
  "Stories/Workplace Short Linear.pdf": {
    title: "Server Outage at Work",
    paragraphs: [
      "Several months before the outage, a manager approved a plan to consolidate server resources.",
      "On a later date, a technician updated configuration settings on a backup system.",
      "After finishing the update, the technician did not restart one of the services.",
      "On the morning of the incident, an analyst began processing a large dataset.",
      "Shortly afterward, system load increased across the network.",
      "As load increased, a critical service stopped responding.",
      "Later that morning, users reported being unable to access shared files.",
      "In the weeks that followed, an internal review examined the incident."
    ],
    questions: workplaceQuestions
  },
  "Stories/Workplace Short NonLinear.pdf": {
    title: "Server Outage at Work",
    paragraphs: [
      "Later that morning, users reported being unable to access shared files.",
      "Several months before the outage, a manager approved a plan to consolidate server resources.",
      "In the weeks that followed, an internal review examined the incident.",
      "As load increased, a critical service stopped responding.",
      "On a later date, a technician updated configuration settings on a backup system.",
      "On the morning of the incident, an analyst began processing a large dataset.",
      "After finishing the update, the technician did not restart one of the services.",
      "Shortly afterward, system load increased across the network."
    ],
    questions: workplaceQuestions
  },
  "Stories/Coastal_Floodgate_Heavy_Fluff_Linear.pdf": {
    title: "Coastal Road Floodgate Incident",
    paragraphs: [
      "The coastal road ran alongside a low seawall, with a pedestrian path on the inland side and a line of salt-tolerant shrubs planted at regular intervals. A small electronic signboard near the bus stop displayed service changes when construction work was active.",
      "The city council approved a pilot floodgate project for the coastal road. In the weeks after the approval, a short project bulletin appeared on the city website and was reposted on a community noticeboard near a cafe. People who used the road daily often noticed the same set of blue directional arrows on temporary signs when routes changed.",
      "Contractors installed temporary barriers and signage near the road. The barriers created a narrower corridor for vehicles, and pedestrians were guided to a marked crossing point that remained in the same place throughout the works. At different times of day, the area alternated between quiet stretches and brief clusters of activity around the crossing.",
      "A utilities team scheduled a routine inspection of a pump station. The pump station sat behind a locked metal gate, and the access path to it was usually empty except for maintenance visits. The inspection date was listed on an internal work calendar, separate from the construction timetable.",
      "The inspection required a temporary shutdown of the pump station. A short entry noting the shutdown window was added to a maintenance log, and the pump station status indicator was set to 'offline' during that period. The nearby electronic signboard continued to cycle through the same rotating messages.",
      "A weather service issued a coastal surge warning. The warning appeared as a standard alert format on multiple apps, and local radio repeated the same headline at set intervals. People who checked the tide chart often looked first at the same reference point: the predicted peak time.",
      "The floodgate was activated during the warning period. A work crew followed a checklist, and the activation was recorded with a timestamp in a routine operations form. The temporary barriers and the blue-arrow signs remained in place, unchanged from earlier in the week.",
      "Water entered the road area and traffic was halted. Drivers were redirected to an inland route, and buses skipped the coastal stop while the closure remained active. After the detour, some pedestrians returned to the same cafe noticeboard, where the latest printed update had been taped over an older sheet.",
      "A municipal review later examined the sequence of events. The review compiled logs from multiple teams and summarized them as a timeline, using the surge warning time as a reference point. In follow-up meetings, the same map of the coastal road was projected repeatedly, with the floodgate location marked in a single highlighted box."
    ],
    questions: coastalQuestions
  },
  "Stories/Coastal Floodgate Heavy Fluff Nonlinear.pdf": {
    title: "Coastal Road Floodgate Incident",
    paragraphs: [
      "The coastal road ran alongside a low seawall, with a pedestrian path on the inland side and a line of salt-tolerant shrubs planted at regular intervals. A small electronic signboard near the bus stop displayed service changes when construction work was active.",
      "A municipal review later examined the sequence of events. The review compiled logs from multiple teams and summarized them as a timeline, using the surge warning time as a reference point. In follow-up meetings, the same map of the coastal road was projected repeatedly, with the floodgate location marked in a single highlighted box.",
      "Water entered the road area and traffic was halted. Drivers were redirected to an inland route, and buses skipped the coastal stop while the closure remained active. After the detour, some pedestrians returned to the same cafe noticeboard, where the latest printed update had been taped over an older sheet.",
      "The city council approved a pilot floodgate project for the coastal road. In the weeks after the approval, a short project bulletin appeared on the city website and was reposted on a community noticeboard near a cafe. People who used the road daily often noticed the same set of blue directional arrows on temporary signs when routes changed.",
      "A weather service issued a coastal surge warning. The warning appeared as a standard alert format on multiple apps, and local radio repeated the same headline at set intervals. People who checked the tide chart often looked first at the same reference point: the predicted peak time.",
      "Contractors installed temporary barriers and signage near the road. The barriers created a narrower corridor for vehicles, and pedestrians were guided to a marked crossing point that remained in the same place throughout the works. At different times of day, the area alternated between quiet stretches and brief clusters of activity around the crossing.",
      "The inspection required a temporary shutdown of the pump station. A short entry noting the shutdown window was added to a maintenance log, and the pump station status indicator was set to 'offline' during that period. The nearby electronic signboard continued to cycle through the same rotating messages.",
      "A utilities team scheduled a routine inspection of a pump station. The pump station sat behind a locked metal gate, and the access path to it was usually empty except for maintenance visits. The inspection date was listed on an internal work calendar, separate from the construction timetable.",
      "The floodgate was activated during the warning period. A work crew followed a checklist, and the activation was recorded with a timestamp in a routine operations form. The temporary barriers and the blue-arrow signs remained in place, unchanged from earlier in the week."
    ],
    questions: coastalQuestions
  }
};

const storyIds = Object.keys(storyBank);
const selectedStoryId = storyIds[Math.floor(Math.random() * storyIds.length)];
const fallbackStoryId = "Stories/Medical Short Linear.pdf";
const selectedStory = storyBank[selectedStoryId] || storyBank[fallbackStoryId];
const q = selectedStory.questions;

if (!storyBank[selectedStoryId]) {
  console.warn("No story defined for:", selectedStoryId, "- using Medical Short as fallback.");
}

const jsPsych = initJsPsych({
  on_finish: () => {
    if (runtimeConfig.debug) {
      jsPsych.data.displayData();
    }
  }
});

jsPsych.data.addProperties({
  ...participantMeta,
  story_shown: selectedStoryId,
  story_title: selectedStory.title
});

let comprehensionResult = {
  passed: false,
  correctCount: 0,
  wrongCount: 0,
  totalCount: q.comprehension.length
};

function scoreComprehension(responseObject, questionSet) {
  const answerIndexByLabel = { Yes: 0, No: 1, Unsure: 2 };
  let correctCount = 0;

  questionSet.forEach((question, i) => {
    const responseIndex = responseObject[`Q${i}`];
    const expectedIndex = answerIndexByLabel[question.correct];
    if (typeof expectedIndex === "number" && responseIndex === expectedIndex) {
      correctCount += 1;
    }
  });

  return {
    correctCount,
    wrongCount: questionSet.length - correctCount,
    totalCount: questionSet.length,
    passed:
      correctCount >= runtimeConfig.comprehensionMinCorrect &&
      (questionSet.length - correctCount) <= runtimeConfig.comprehensionMaxWrong
  };
}

const intro = {
  type: jsPsychInstructions,
  pages: [
    `<h2>Instructions</h2>
     <p>You will read a short narrative once.</p>
     <p><strong>Please do not go back to re-read the story once you begin the questions.</strong></p>
     <p>Answer based on your understanding and memory.</p>`
  ],
  show_clickable_nav: true,
  allow_backward: false
};

const demographics = {
  type: jsPsychSurveyHtmlForm,
  html: `
    <p><strong>Participant information</strong></p>
    <p>Age: <input name="age" type="number" min="18" max="120" required></p>
    <p>Gender (optional): <input name="gender" type="text"></p>
    <p>Highest education completed: <input name="education" type="text" required></p>
    <p>Native language(s): <input name="native_languages" type="text" required></p>
    <p>English proficiency (1-7):
      <select name="english_proficiency" required>
        <option value="">Select</option>
        <option>1</option><option>2</option><option>3</option><option>4</option>
        <option>5</option><option>6</option><option>7</option>
      </select>
    </p>
    <p>Age you began learning English (if not native): <input name="english_start_age" type="number" min="0" max="120"></p>
  `,
  button_label: "Continue"
};

const view_story = {
  type: jsPsychHtmlButtonResponse,
  stimulus: `
    <div class="story-wrap" style="max-width: 860px; margin: 0 auto; text-align: left; line-height: 1.65;">
      <h2>${selectedStory.title}</h2>
      ${selectedStory.paragraphs.map((paragraph) => `<p>${paragraph}</p>`).join("")}
    </div>
  `,
  choices: ["Continue"],
  prompt: "<p>Please read the story carefully. You will not be able to return to it.</p>"
};

const comprehension = {
  type: jsPsychSurveyLikert,
  preamble: `<h2>Comprehension Check</h2>
             <p>Answer based on what was explicitly stated in the narrative.</p>`,
  questions: q.comprehension.map((item) => ({
    prompt: item.prompt,
    labels: item.labels,
    required: item.required
  })),
  button_label: "Continue",
  on_finish: (data) => {
    comprehensionResult = scoreComprehension(data.response, q.comprehension);
    data.comprehension_correct = comprehensionResult.correctCount;
    data.comprehension_wrong = comprehensionResult.wrongCount;
    data.comprehension_total = comprehensionResult.totalCount;
    data.comprehension_passed = comprehensionResult.passed;

    jsPsych.data.addProperties({
      comprehension_passed: comprehensionResult.passed,
      comprehension_correct: comprehensionResult.correctCount,
      comprehension_wrong: comprehensionResult.wrongCount,
      comprehension_total: comprehensionResult.totalCount
    });
  }
};

const cardTaskEvents = getCanonicalCardEventsForStory(selectedStory.title) || selectedStory.paragraphs;

// --- 1) Counterfactual Judgements (box layout via causal-pair-scale plugin) ---

const counterfactual = {
  timeline: [
    {
      type: jsPsychCausalPairScale,
      heading: "1) Counterfactual Judgements",
      instruction: "If the event on the left had <strong>NOT</strong> occurred, how would the likelihood of the event on the right change?",
      left_event: jsPsych.timelineVariable("left_event"),
      right_event: jsPsych.timelineVariable("right_event"),
      labels: jsPsych.timelineVariable("labels"),
      required: true,
      button_label: "Continue"
    }
  ],
  timeline_variables: q.counterfactual
};

// --- 2) Responsibility Allocation ---

const responsibilityTask = {
  type: jsPsychResponsibilityAllocation,
  title: "2) Responsibility Allocation",
  instructions:
    "Distribute exactly <strong>100 points</strong> across the events below to indicate how responsible " +
    "each event was for <strong>" + (q.outcome_description || "the incident that occurred") + "</strong>." +
    "<br><br>Events you consider more responsible should receive more points. The total must equal 100.",
  events: cardTaskEvents,
  exclude_indices: [7],
  total_points: 100,
  button_label: "Continue"
};

// --- 3) Event ordering (Card Sort) task ---

const cardSortTask = {
  type: jsPsychCardSort,
  title: "3) Event Ordering",
  instructions:
    "Below are key events from the story you just read, presented in a random order.<br><br>" +
    "Drag the cards to rearrange them into the <strong>chronological order</strong> in which " +
    "the events occurred, from the <strong>earliest</strong> event (top) to the " +
    "<strong>latest</strong> event (bottom).",
  events: cardTaskEvents,
  button_label: "Continue"
};

const pilotFeedback = {
  type: jsPsychSurveyHtmlForm,
  preamble: "<h2>Pilot Feedback</h2><p>Thank you. Please share any feedback about this pilot version.</p>",
  html: `
    <p>How clear were the instructions? (1 = very unclear, 7 = very clear)<br>
    <input name="clarity_rating" type="number" min="1" max="7" required></p>
    <p>How difficult was the task? (1 = very easy, 7 = very difficult)<br>
    <input name="difficulty_rating" type="number" min="1" max="7" required></p>
    <p>Did you encounter any technical issues?<br>
    <textarea name="technical_issues" rows="4" style="width:100%;"></textarea></p>
    <p>Any other feedback?<br>
    <textarea name="general_feedback" rows="5" style="width:100%;"></textarea></p>
  `,
  button_label: "Submit feedback"
};

const markCompleted = {
  type: jsPsychCallFunction,
  func: () => {
    jsPsych.data.addProperties({ final_status: "completed" });
  }
};

const markDisqualified = {
  type: jsPsychCallFunction,
  func: () => {
    jsPsych.data.addProperties({ final_status: "disqualified" });
  }
};

const redirectToCompletion = {
  timeline: [
    {
      type: jsPsychCallFunction,
      func: () => {
        if (runtimeConfig.completionUrl) {
          window.location.href = runtimeConfig.completionUrl;
        }
      }
    }
  ],
  conditional_function: () => Boolean(runtimeConfig.completionUrl)
};

const completionFallback = {
  timeline: [
    {
      type: jsPsychHtmlButtonResponse,
      stimulus: "<h2>Thank you for participating.</h2><p>Your responses have been recorded.</p>",
      choices: ["Finish"]
    }
  ],
  conditional_function: () => !runtimeConfig.completionUrl
};

const redirectToDisqualification = {
  type: jsPsychCallFunction,
  func: () => {
    window.location.href = runtimeConfig.disqualificationUrl;
  }
};

const passBranch = {
  timeline: [counterfactual, responsibilityTask, cardSortTask, pilotFeedback, markCompleted, redirectToCompletion, completionFallback],
  conditional_function: () => comprehensionResult.passed
};

const failBranch = {
  timeline: [markDisqualified, redirectToDisqualification],
  conditional_function: () => !comprehensionResult.passed
};

jsPsych.run([
  intro,
  demographics,
  view_story,
  comprehension,
  passBranch,
  failBranch
]);

} // end double-load guard
  
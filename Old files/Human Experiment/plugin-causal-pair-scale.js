(function (jspsych) {
  "use strict";

  if (!jspsych || !jspsych.ParameterType) {
    console.warn("causal-pair-scale plugin: jsPsychModule not available at load time");
    return;
  }

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
})(typeof jsPsychModule !== "undefined" ? jsPsychModule : null);

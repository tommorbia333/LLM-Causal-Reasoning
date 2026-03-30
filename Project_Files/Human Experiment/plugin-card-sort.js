(function (jspsych) {
  "use strict";

  if (!jspsych || !jspsych.ParameterType) {
    console.warn("card-sort plugin: jsPsychModule not available at load time");
    return;
  }

  const info = {
    name: "card-sort",
    parameters: {
      title: {
        type: jspsych.ParameterType.STRING,
        default: "Event Ordering"
      },
      instructions: {
        type: jspsych.ParameterType.HTML_STRING,
        default:
          "Drag the cards to arrange them in chronological order, from earliest (top) to latest (bottom)."
      },
      events: {
        type: jspsych.ParameterType.STRING,
        array: true,
        default: []
      },
      button_label: {
        type: jspsych.ParameterType.STRING,
        default: "Continue"
      },
      shuffle: {
        type: jspsych.ParameterType.BOOL,
        default: true
      }
    }
  };

  function fisherYatesShuffle(arr) {
    const a = arr.slice();
    do {
      for (let i = a.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [a[i], a[j]] = [a[j], a[i]];
      }
    } while (a.length > 1 && a.every((v, i) => v.id === arr[i].id));
    return a;
  }

  // Kendall's tau-a between submitted canonical-index sequence and 0..n-1
  function kendallTau(ranks) {
    const n = ranks.length;
    let con = 0;
    let dis = 0;
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        if (ranks[i] < ranks[j]) con++;
        else if (ranks[i] > ranks[j]) dis++;
      }
    }
    const pairs = (n * (n - 1)) / 2;
    return pairs === 0 ? 0 : +((con - dis) / pairs).toFixed(4);
  }

  class CardSortPlugin {
    constructor(jsPsych) {
      this.jsPsych = jsPsych;
    }

    trial(display_element, trial) {
      const t0 = performance.now();
      let moveCount = 0;

      const parsed = (trial.events || []).map((txt, idx) => ({
        id: "e" + (idx + 1),
        canonicalIndex: idx,
        text: String(txt).replace(/^E\d+:\s*/, "")
      }));

      const order = trial.shuffle !== false ? fisherYatesShuffle(parsed) : parsed.slice();
      const initialOrder = order.map((ev) => ev.id);

      display_element.innerHTML =
        '<div class="cs-wrap"><div class="cs-panel">' +
        "<h2>" + trial.title + "</h2>" +
        '<p class="cs-instructions">' + trial.instructions + "</p>" +
        '<div class="cs-list-area">' +
        '<div class="cs-endpoint cs-endpoint-top">&#9650; Earliest (first)</div>' +
        '<div class="cs-list" id="cs-list"></div>' +
        '<div class="cs-endpoint cs-endpoint-bottom">&#9660; Latest (last)</div>' +
        "</div>" +
        '<p id="cs-error" class="cs-error" style="display:none;">Please arrange the cards before continuing.</p>' +
        '<button id="cs-next" class="jspsych-btn">' + trial.button_label + "</button>" +
        "</div></div>";

      var listEl = display_element.querySelector("#cs-list");
      var nextBtn = display_element.querySelector("#cs-next");

      order.forEach(function (ev, idx) {
        var el = document.createElement("div");
        el.className = "cs-item";
        el.dataset.eventId = ev.id;
        el.dataset.canonicalIndex = String(ev.canonicalIndex);
        el.setAttribute("tabindex", "0");
        el.style.touchAction = "none";
        el.innerHTML =
          '<span class="cs-pos">' + (idx + 1) + "</span>" +
          '<span class="cs-text">' + ev.text + "</span>" +
          '<span class="cs-handle" aria-hidden="true">&#x2807;</span>';
        listEl.appendChild(el);
      });

      function renumber() {
        var items = listEl.querySelectorAll(".cs-item");
        for (var i = 0; i < items.length; i++) {
          items[i].querySelector(".cs-pos").textContent = i + 1;
        }
      }

      // --- Drag-to-reorder via pointer events ---
      var drag = null;

      function onDown(e) {
        var item = e.target.closest(".cs-item");
        if (!item || !listEl.contains(item)) return;
        if (typeof e.button === "number" && e.button !== 0) return;
        e.preventDefault();

        var rect = item.getBoundingClientRect();
        var allItems = Array.from(listEl.querySelectorAll(".cs-item"));
        var origIndex = allItems.indexOf(item);
        var offY = e.clientY - rect.top;
        var offX = e.clientX - rect.left;

        var ghost = item.cloneNode(true);
        ghost.classList.add("cs-ghost");
        ghost.style.position = "fixed";
        ghost.style.width = rect.width + "px";
        ghost.style.left = rect.left + "px";
        ghost.style.top = rect.top + "px";
        ghost.style.zIndex = "10000";
        ghost.style.pointerEvents = "none";
        ghost.style.margin = "0";
        document.body.appendChild(ghost);

        var ph = document.createElement("div");
        ph.className = "cs-placeholder";
        ph.style.height = rect.height + "px";
        listEl.insertBefore(ph, item);
        item.remove();

        drag = { item: item, ghost: ghost, ph: ph, offX: offX, offY: offY, origIndex: origIndex };

        document.addEventListener("pointermove", onMove);
        document.addEventListener("pointerup", onUp);
      }

      function onMove(e) {
        if (!drag) return;
        drag.ghost.style.left = (e.clientX - drag.offX) + "px";
        drag.ghost.style.top = (e.clientY - drag.offY) + "px";

        var children = Array.from(listEl.children);
        var before = null;
        for (var i = 0; i < children.length; i++) {
          if (children[i] === drag.ph) continue;
          var r = children[i].getBoundingClientRect();
          if (e.clientY < r.top + r.height / 2) {
            before = children[i];
            break;
          }
        }
        if (before) listEl.insertBefore(drag.ph, before);
        else listEl.appendChild(drag.ph);
      }

      function onUp() {
        if (!drag) return;
        listEl.insertBefore(drag.item, drag.ph);
        drag.ph.remove();
        drag.ghost.remove();

        var allItems = Array.from(listEl.querySelectorAll(".cs-item"));
        var newIndex = allItems.indexOf(drag.item);
        if (newIndex !== drag.origIndex) moveCount++;

        renumber();

        document.removeEventListener("pointermove", onMove);
        document.removeEventListener("pointerup", onUp);
        drag = null;
      }

      listEl.addEventListener("pointerdown", onDown);

      // Keyboard reorder: Alt+Arrow
      listEl.addEventListener("keydown", function (e) {
        var item = e.target.closest(".cs-item");
        if (!item) return;
        if (e.altKey && e.key === "ArrowUp") {
          e.preventDefault();
          var prev = item.previousElementSibling;
          if (prev && prev.classList.contains("cs-item")) {
            listEl.insertBefore(item, prev);
            moveCount++;
            renumber();
            item.focus();
          }
        } else if (e.altKey && e.key === "ArrowDown") {
          e.preventDefault();
          var next = item.nextElementSibling;
          if (next && next.classList.contains("cs-item")) {
            listEl.insertBefore(next, item);
            moveCount++;
            renumber();
            item.focus();
          }
        }
      });

      var plugin = this;

      nextBtn.addEventListener("click", function () {
        var items = Array.from(listEl.querySelectorAll(".cs-item"));
        var submittedIds = items.map(function (el) { return el.dataset.eventId; });
        var canonicalIndices = items.map(function (el) { return Number(el.dataset.canonicalIndex); });
        var tau = kendallTau(canonicalIndices);
        var rt = Math.round(performance.now() - t0);

        var trialData = {
          submitted_order: submittedIds,
          initial_order: initialOrder,
          kendall_tau: tau,
          total_moves: moveCount,
          rt: rt
        };

        for (var i = 0; i < items.length; i++) {
          trialData[items[i].dataset.eventId + "_rank"] = i + 1;
        }

        listEl.removeEventListener("pointerdown", onDown);
        display_element.innerHTML = "";
        plugin.jsPsych.finishTrial(trialData);
      });
    }
  }

  CardSortPlugin.info = info;
  window.jsPsychCardSort = CardSortPlugin;
})(typeof jsPsychModule !== "undefined" ? jsPsychModule : null);

(function (jspsych) {
    "use strict";
  
    if (!jspsych || !jspsych.ParameterType) {
      console.warn("card-board plugin: jsPsychModule not available at load time");
      return;
    }

    const info = {
      name: "card-board",
      parameters: {
        title: {
          type: jspsych.ParameterType.STRING,
          default: "Card Task"
        },
        instructions: {
          type: jspsych.ParameterType.HTML_STRING,
          default:
            "Drag the event cards onto the board.<br><br><strong>X-axis</strong>: earlier → later (sequence/time)<br><strong>Y-axis</strong>: lower → higher causal impact"
        },
        x_label_left: {
          type: jspsych.ParameterType.STRING,
          default: "Earlier"
        },
        x_label_right: {
          type: jspsych.ParameterType.STRING,
          default: "Later"
        },
        y_label_bottom: {
          type: jspsych.ParameterType.STRING,
          default: "Lower impact"
        },
        y_label_top: {
          type: jspsych.ParameterType.STRING,
          default: "Higher impact"
        },
        events: {
          type: jspsych.ParameterType.STRING,
          array: true,
          default: []
        },
        required_place_all: {
          type: jspsych.ParameterType.BOOL,
          default: true
        },
        button_label: {
          type: jspsych.ParameterType.STRING,
          default: "Continue"
        },
        board_height_px: {
          type: jspsych.ParameterType.INT,
          default: 520
        },
        board_min_width_px: {
          type: jspsych.ParameterType.INT,
          default: 720
        },
        start_layout: {
          // "stack" (left tray), or "scatter" (random on board)
          type: jspsych.ParameterType.STRING,
          default: "stack"
        }
      }
    };
  
    function clamp(v, lo, hi) {
      return Math.max(lo, Math.min(hi, v));
    }
  
    function nowMs() {
      return Math.round(performance.now());
    }
  
    function rectToNorm(clientX, clientY, boardRect) {
      const x = (clientX - boardRect.left) / boardRect.width;
      const y = (clientY - boardRect.top) / boardRect.height;
      return { x: clamp(x, 0, 1), y: clamp(y, 0, 1) };
    }
  
    function normToPx(x, y, boardRect, cardW, cardH) {
      const left = boardRect.left + x * boardRect.width - cardW / 2;
      const top = boardRect.top + y * boardRect.height - cardH / 2;
      return { left, top };
    }
  
    function computeDistances(placements) {
      // placements: [{id, text, x, y}]
      const n = placements.length;
      const D = Array.from({ length: n }, () => Array.from({ length: n }, () => null));
      for (let i = 0; i < n; i++) {
        for (let j = i; j < n; j++) {
          const dx = placements[i].x - placements[j].x;
          const dy = placements[i].y - placements[j].y;
          const d = Math.sqrt(dx * dx + dy * dy);
          D[i][j] = d;
          D[j][i] = d;
        }
      }
      return D;
    }
  
    class CardBoardPlugin {
      constructor(jsPsych) {
        this.jsPsych = jsPsych;
      }
  
      trial(display_element, trial) {
        const t0 = nowMs();
        const interactionLog = [];
        const placed = new Set();
  
        const safeEvents = (trial.events || []).map((txt, idx) => ({
          id: `e${idx + 1}`,
          text: String(txt)
        }));
  
        display_element.innerHTML = `
          <div class="cb-wrap">
            <div class="cb-card">
              <h2>${trial.title}</h2>
              <p class="cb-instructions">${trial.instructions}</p>
  
              <div class="cb-layout">
                <div class="cb-tray" aria-label="Event cards tray">
                  <div class="cb-tray-title">Event cards</div>
                  <div class="cb-tray-list" id="cb-tray-list"></div>
                  <div class="cb-hint">Drag each card onto the board.</div>
                </div>
  
                <div class="cb-board-wrap">
                  <div class="cb-axis cb-x-axis">
                    <span>${trial.x_label_left}</span>
                    <span>${trial.x_label_right}</span>
                  </div>
  
                  <div class="cb-board" id="cb-board" style="height:${trial.board_height_px}px;"></div>
  
                  <div class="cb-axis cb-y-axis">
                    <span class="cb-y-top">${trial.y_label_top}</span>
                    <span class="cb-y-bottom">${trial.y_label_bottom}</span>
                  </div>
                </div>
              </div>
  
              <p id="cb-error" class="cb-error" style="display:none;">Please place all cards on the board before continuing.</p>
              <button id="cb-next" class="jspsych-btn">${trial.button_label}</button>
            </div>
          </div>
        `;
  
        const trayList = display_element.querySelector("#cb-tray-list");
        const boardEl = display_element.querySelector("#cb-board");
        const nextBtn = display_element.querySelector("#cb-next");
        const errorEl = display_element.querySelector("#cb-error");
  
        // Create DOM cards in tray
        const cardEls = safeEvents.map((ev) => {
          const el = document.createElement("div");
          el.className = "cb-event";
          el.setAttribute("role", "button");
          el.setAttribute("tabindex", "0");
          el.dataset.eventId = ev.id;
          el.textContent = ev.text;
          trayList.appendChild(el);
          return el;
        });
  
        // For absolute positioning on board, we clone cards into a "floating" layer container:
        const floatLayer = document.createElement("div");
        floatLayer.className = "cb-float-layer";
        boardEl.appendChild(floatLayer);
  
        // State for each card
        const state = {};
        for (const ev of safeEvents) {
          state[ev.id] = {
            id: ev.id,
            text: ev.text,
            x: null,
            y: null,
            // pixel positioning stored during drag
            isOnBoard: false
          };
        }
  
        function getBoardRect() {
          return boardEl.getBoundingClientRect();
        }
  
        function markPlaced(eventId) {
          placed.add(eventId);
        }
  
        function isAllPlaced() {
          return placed.size === safeEvents.length;
        }
  
        function log(action, payload) {
          interactionLog.push({
            t: nowMs() - t0,
            action,
            ...payload
          });
        }
  
        function createFloatingCard(sourceEl) {
          const eventId = sourceEl.dataset.eventId;
          const ev = state[eventId];
  
          // If already floating, use existing
          let floating = floatLayer.querySelector(`.cb-float[data-event-id="${eventId}"]`);
          if (!floating) {
            floating = document.createElement("div");
            floating.className = "cb-float";
            floating.dataset.eventId = eventId;
  
            const inner = document.createElement("div");
            inner.className = "cb-float-inner";
            inner.textContent = ev.text;
  
            floating.appendChild(inner);
            floatLayer.appendChild(floating);
          }
          return floating;
        }
  
        // Start layout: either stack in tray (default) or scatter on board
        if (trial.start_layout === "scatter") {
          const boardRect = getBoardRect();
          // We need a quick frame to ensure rect is correct after layout
          requestAnimationFrame(() => {
            const r = getBoardRect();
            for (const el of cardEls) {
              const floating = createFloatingCard(el);
              const eventId = el.dataset.eventId;
              const x = Math.random() * 0.8 + 0.1;
              const y = Math.random() * 0.8 + 0.1;
              state[eventId].x = x;
              state[eventId].y = y;
              state[eventId].isOnBoard = true;
              markPlaced(eventId);
  
              // position
              const cardW = floating.getBoundingClientRect().width || 200;
              const cardH = floating.getBoundingClientRect().height || 60;
              const px = normToPx(x, y, r, cardW, cardH);
              floating.style.left = `${px.left - r.left}px`;
              floating.style.top = `${px.top - r.top}px`;
            }
          });
        }
  
        // Drag logic (pointer events)
        let active = null;
  
        function startDrag(sourceEl, pointerEvent) {
          const eventId = sourceEl.dataset.eventId;
          const floating = createFloatingCard(sourceEl);
          const boardRect = getBoardRect();
  
          const floatRect = floating.getBoundingClientRect();
          const offsetX = pointerEvent.clientX - floatRect.left;
          const offsetY = pointerEvent.clientY - floatRect.top;
  
          active = { eventId, floating, offsetX, offsetY };
          floating.classList.add("cb-dragging");
          floating.setPointerCapture(pointerEvent.pointerId);
  
          log("drag_start", {
            event_id: eventId,
            client_x: pointerEvent.clientX,
            client_y: pointerEvent.clientY
          });
  
          moveDrag(pointerEvent); // position immediately
        }
  
        function moveDrag(pointerEvent) {
          if (!active) return;
  
          const boardRect = getBoardRect();
          const floating = active.floating;
  
          // Constrain within board bounds (keeping card fully visible)
          const cardRect = floating.getBoundingClientRect();
          const cardW = cardRect.width || 200;
          const cardH = cardRect.height || 60;
  
          const left = pointerEvent.clientX - boardRect.left - active.offsetX;
          const top = pointerEvent.clientY - boardRect.top - active.offsetY;
  
          const clampedLeft = clamp(left, 0, boardRect.width - cardW);
          const clampedTop = clamp(top, 0, boardRect.height - cardH);
  
          floating.style.left = `${clampedLeft}px`;
          floating.style.top = `${clampedTop}px`;
  
          // store normalized center
          const centerX = (clampedLeft + cardW / 2) / boardRect.width;
          const centerY = (clampedTop + cardH / 2) / boardRect.height;
  
          const s = state[active.eventId];
          s.x = clamp(centerX, 0, 1);
          s.y = clamp(centerY, 0, 1);
          s.isOnBoard = true;
          markPlaced(active.eventId);
  
          log("drag_move", {
            event_id: active.eventId,
            x: s.x,
            y: s.y
          });
        }
  
        function endDrag(pointerEvent) {
          if (!active) return;
  
          const eventId = active.eventId;
          active.floating.classList.remove("cb-dragging");
  
          log("drag_end", {
            event_id: eventId,
            x: state[eventId].x,
            y: state[eventId].y
          });
  
          active = null;
        }
  
        // Tray cards start drag -> floating card on board
        for (const el of cardEls) {
          el.addEventListener("pointerdown", (e) => {
            // only allow left click / primary pointer
            if (typeof e.button === "number" && e.button !== 0) return;
            startDrag(el, e);
          });
  
          // keyboard accessibility: Enter starts "drag" by snapping to center, then user can reposition with pointer
          el.addEventListener("keydown", (e) => {
            if (e.key !== "Enter" && e.key !== " ") return;
            const boardRect = getBoardRect();
            const floating = createFloatingCard(el);
            const eventId = el.dataset.eventId;
  
            // snap to center
            state[eventId].x = 0.5;
            state[eventId].y = 0.5;
            state[eventId].isOnBoard = true;
            markPlaced(eventId);
  
            const cardW = floating.getBoundingClientRect().width || 200;
            const cardH = floating.getBoundingClientRect().height || 60;
            const px = normToPx(0.5, 0.5, boardRect, cardW, cardH);
  
            floating.style.left = `${px.left - boardRect.left}px`;
            floating.style.top = `${px.top - boardRect.top}px`;
  
            log("keyboard_place_center", { event_id: eventId });
          });
        }
  
        // Board listens for pointer moves when dragging
        document.addEventListener("pointermove", moveDrag);
        document.addEventListener("pointerup", endDrag);
  
        // Finish trial
        nextBtn.addEventListener("click", () => {
          if (trial.required_place_all && !isAllPlaced()) {
            errorEl.style.display = "block";
            return;
          }
  
          const placements = safeEvents.map((ev) => ({
            id: ev.id,
            text: ev.text,
            x: state[ev.id].x,
            y: state[ev.id].y
          }));
  
          const boardRect = getBoardRect();
          const distances = computeDistances(placements);
  
          // cleanup listeners
          document.removeEventListener("pointermove", moveDrag);
          document.removeEventListener("pointerup", endDrag);
  
          const trialData = {
            final_positions: placements,                 // [{id,text,x,y}]
            pairwise_distances: distances,               // NxN numeric matrix
            interaction_log: interactionLog,             // drag logs
            board_px: { width: Math.round(boardRect.width), height: Math.round(boardRect.height) },
            start_layout: trial.start_layout
          };
  
          display_element.innerHTML = "";
          this.jsPsych.finishTrial(trialData);
        });
      }
    }
  
    CardBoardPlugin.info = info;
    window.jsPsychCardBoard = CardBoardPlugin;
  })(typeof jsPsychModule !== "undefined" ? jsPsychModule : null);
  
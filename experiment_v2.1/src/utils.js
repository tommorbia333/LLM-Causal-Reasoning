// utils.js — small shared helpers. No jsPsych dependencies.

var Utils = (function () {
  /** Parse query-string parameters from the current URL. */
  function getURLParams() {
    var params = {};
    var search = (typeof window !== 'undefined' && window.location && window.location.search) || '';
    var query = search.replace(/^\?/, '');
    if (!query) return params;
    query.split('&').forEach(function (kv) {
      var parts = kv.split('=');
      var k = decodeURIComponent(parts[0] || '');
      var v = decodeURIComponent(parts[1] || '');
      if (k) params[k] = v;
    });
    return params;
  }

  /** ISO timestamp with millisecond precision. */
  function nowISO() {
    return new Date().toISOString();
  }

  /** Generate a short random participant identifier (fallback if no Prolific ID). */
  function fallbackParticipantId() {
    var s = '';
    var chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    for (var i = 0; i < 8; i++) s += chars[Math.floor(Math.random() * chars.length)];
    return 'anon_' + s;
  }

  /** Shuffle an array in place (Fisher-Yates) and return it. */
  function shuffle(arr) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
    }
    return a;
  }

  /**
   * Attach activity listeners to a DOM element that reports focus/blur,
   * scroll depth, and arbitrary typed events to a provided event log array.
   *
   * Returns a detach() function to remove listeners.
   */
  function attachActivityTracker(rootElement, eventLog, t0) {
    var maxScrollDepth = 0;
    var focusLossCount = 0;
    var focusLossTotalMs = 0;
    var lastBlurAt = null;

    function relTime() { return performance.now() - t0; }

    function onScroll() {
      var el = rootElement || window.document.scrollingElement || document.documentElement;
      var height = el.scrollHeight - el.clientHeight;
      var depth = height > 0 ? Math.min(1, (el.scrollTop || window.scrollY) / height) : 1;
      if (depth > maxScrollDepth) {
        maxScrollDepth = depth;
        eventLog.push({ t: Math.round(relTime()), type: 'scroll', depth: +depth.toFixed(3) });
      }
    }

    function onBlur() {
      lastBlurAt = relTime();
      focusLossCount += 1;
      eventLog.push({ t: Math.round(lastBlurAt), type: 'focus_loss' });
    }

    function onFocus() {
      if (lastBlurAt !== null) {
        var delta = relTime() - lastBlurAt;
        focusLossTotalMs += delta;
        eventLog.push({ t: Math.round(relTime()), type: 'focus_return', away_ms: Math.round(delta) });
        lastBlurAt = null;
      }
    }

    window.addEventListener('scroll', onScroll, { passive: true });
    if (rootElement) rootElement.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('blur', onBlur);
    window.addEventListener('focus', onFocus);

    function detach() {
      window.removeEventListener('scroll', onScroll);
      if (rootElement) rootElement.removeEventListener('scroll', onScroll);
      window.removeEventListener('blur', onBlur);
      window.removeEventListener('focus', onFocus);
      // Finalise any open blur interval.
      if (lastBlurAt !== null) {
        focusLossTotalMs += relTime() - lastBlurAt;
        lastBlurAt = null;
      }
      return {
        scroll_depth_max: +maxScrollDepth.toFixed(3),
        focus_loss_count: focusLossCount,
        focus_loss_total_ms: Math.round(focusLossTotalMs),
      };
    }
    return detach;
  }

  return {
    getURLParams: getURLParams,
    nowISO: nowISO,
    fallbackParticipantId: fallbackParticipantId,
    shuffle: shuffle,
    attachActivityTracker: attachActivityTracker,
  };
})();

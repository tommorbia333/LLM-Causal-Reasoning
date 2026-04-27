// main.js — timeline entry point.
//
// Timeline (per task design §2.3):
//   [Intro] browser check → welcome → consent → demographics → IMC → instructions
//   For each story i = 1..4:
//     Inter-story break screen (progress indicator)
//     Story reading
//     Comprehension (6 items + summary)
//     Ordering (8-card drag + confidence slider)
//     Pair scaling (56 pairs + 8x8 matrix summary)
//     Counterfactual probes (8 probes + summary)
//   [Outro] comments → debrief → Prolific redirect

var jsPsych;  // exposed as a global so sub-modules (intro, outro) can end early

(function () {
  jsPsych = initJsPsych({
    on_finish: function () {
      // Save handled by Cognition / hosting backend automatically.
      // For local testing, dump to the page so we can eyeball the data.
      if (CONFIG.debug && CONFIG.debug.enabled) {
        jsPsych.data.displayData('json');
      }
    },
  });

  // ---- Determine participant identity and assignment ----
  var urlParams = Utils.getURLParams();
  var participantIdStr = urlParams.PROLIFIC_PID || Utils.fallbackParticipantId();

  var pIndex;
  if (urlParams.pIndex !== undefined && urlParams.pIndex !== '') {
    pIndex = parseInt(urlParams.pIndex, 10);
  } else {
    var h = 0;
    for (var i = 0; i < participantIdStr.length; i++) {
      h = ((h << 5) - h + participantIdStr.charCodeAt(i)) | 0;
    }
    pIndex = Math.abs(h);
  }

  var condition = Condition.assignCondition(pIndex, participantIdStr);
  var assignment = Selection.assignStories(pIndex);
  var participantMeta = DataHelpers.initParticipant(urlParams, pIndex, condition, assignment);

  jsPsych.data.addProperties({
    participant_id: participantMeta.participant_id,
    condition: condition,
    assignment_id: assignment.assignment_id,
    experiment_version: CONFIG.experiment_version,
  });

  // ---- Build the timeline ----
  var timeline = [];

  IntroSequence.buildAll().forEach(function (t) { timeline.push(t); });

  var totalStories = assignment.stories.length;
  assignment.stories.forEach(function (storyId, idx) {
    var storyPosition = idx + 1;

    var breakTrial = InterStoryScreen.buildTrial(storyPosition, totalStories);
    if (breakTrial) timeline.push(breakTrial);

    timeline.push(StoryReadingTask.buildTrial({
      storyId: storyId,
      condition: condition,
      storyPosition: storyPosition,
    }));

    ComprehensionTask.buildBlock(storyId).forEach(function (t) { timeline.push(t); });
    timeline.push(OrderingTask.buildTrial({ storyId: storyId }));
    PairScalingTask.buildBlock(storyId).forEach(function (t) { timeline.push(t); });
    CounterfactualTask.buildBlock(storyId).forEach(function (t) { timeline.push(t); });
  });

  OutroSequence.buildAll().forEach(function (t) { timeline.push(t); });

  jsPsych.run(timeline);
})();

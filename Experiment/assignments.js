// assignments.js — 32 preregistered participant assignments.
// Design: 4 splits × 2 halves × 4 Williams'-square orderings = 32 assignments.
// Constraint: hospital_incident and care_home_incident (structural replicates)
//   never co-occur in any participant's 4-story assignment.
// Participant index modulo 32 selects the assignment row.

var ASSIGNMENTS = {
  "schema_version": "1.1",
  "n_assignments": 32,
  "cycle_length": 32,
  "design_notes": {
    "hospital_care_home_separation": "enforced \u2014 no participant receives both",
    "split_construction": "4 splits \u00d7 2 halves \u00d7 4 Williams-square orderings = 32 assignments"
  },
  "assignments": [
    {
      "assignment_id": 0,
      "split": 0,
      "half": 0,
      "order_idx": 0,
      "stories": [
        "hospital_incident",
        "community_fair",
        "school_trip",
        "restaurant_fire"
      ]
    },
    {
      "assignment_id": 1,
      "split": 0,
      "half": 0,
      "order_idx": 1,
      "stories": [
        "community_fair",
        "restaurant_fire",
        "hospital_incident",
        "school_trip"
      ]
    },
    {
      "assignment_id": 2,
      "split": 0,
      "half": 0,
      "order_idx": 2,
      "stories": [
        "restaurant_fire",
        "school_trip",
        "community_fair",
        "hospital_incident"
      ]
    },
    {
      "assignment_id": 3,
      "split": 0,
      "half": 0,
      "order_idx": 3,
      "stories": [
        "school_trip",
        "hospital_incident",
        "restaurant_fire",
        "community_fair"
      ]
    },
    {
      "assignment_id": 4,
      "split": 0,
      "half": 1,
      "order_idx": 0,
      "stories": [
        "care_home_incident",
        "family_conflict",
        "missed_flight",
        "power_cut"
      ]
    },
    {
      "assignment_id": 5,
      "split": 0,
      "half": 1,
      "order_idx": 1,
      "stories": [
        "family_conflict",
        "power_cut",
        "care_home_incident",
        "missed_flight"
      ]
    },
    {
      "assignment_id": 6,
      "split": 0,
      "half": 1,
      "order_idx": 2,
      "stories": [
        "power_cut",
        "missed_flight",
        "family_conflict",
        "care_home_incident"
      ]
    },
    {
      "assignment_id": 7,
      "split": 0,
      "half": 1,
      "order_idx": 3,
      "stories": [
        "missed_flight",
        "care_home_incident",
        "power_cut",
        "family_conflict"
      ]
    },
    {
      "assignment_id": 8,
      "split": 1,
      "half": 0,
      "order_idx": 0,
      "stories": [
        "hospital_incident",
        "community_fair",
        "power_cut",
        "family_conflict"
      ]
    },
    {
      "assignment_id": 9,
      "split": 1,
      "half": 0,
      "order_idx": 1,
      "stories": [
        "community_fair",
        "family_conflict",
        "hospital_incident",
        "power_cut"
      ]
    },
    {
      "assignment_id": 10,
      "split": 1,
      "half": 0,
      "order_idx": 2,
      "stories": [
        "family_conflict",
        "power_cut",
        "community_fair",
        "hospital_incident"
      ]
    },
    {
      "assignment_id": 11,
      "split": 1,
      "half": 0,
      "order_idx": 3,
      "stories": [
        "power_cut",
        "hospital_incident",
        "family_conflict",
        "community_fair"
      ]
    },
    {
      "assignment_id": 12,
      "split": 1,
      "half": 1,
      "order_idx": 0,
      "stories": [
        "care_home_incident",
        "restaurant_fire",
        "missed_flight",
        "school_trip"
      ]
    },
    {
      "assignment_id": 13,
      "split": 1,
      "half": 1,
      "order_idx": 1,
      "stories": [
        "restaurant_fire",
        "school_trip",
        "care_home_incident",
        "missed_flight"
      ]
    },
    {
      "assignment_id": 14,
      "split": 1,
      "half": 1,
      "order_idx": 2,
      "stories": [
        "school_trip",
        "missed_flight",
        "restaurant_fire",
        "care_home_incident"
      ]
    },
    {
      "assignment_id": 15,
      "split": 1,
      "half": 1,
      "order_idx": 3,
      "stories": [
        "missed_flight",
        "care_home_incident",
        "school_trip",
        "restaurant_fire"
      ]
    },
    {
      "assignment_id": 16,
      "split": 2,
      "half": 0,
      "order_idx": 0,
      "stories": [
        "hospital_incident",
        "restaurant_fire",
        "missed_flight",
        "family_conflict"
      ]
    },
    {
      "assignment_id": 17,
      "split": 2,
      "half": 0,
      "order_idx": 1,
      "stories": [
        "restaurant_fire",
        "family_conflict",
        "hospital_incident",
        "missed_flight"
      ]
    },
    {
      "assignment_id": 18,
      "split": 2,
      "half": 0,
      "order_idx": 2,
      "stories": [
        "family_conflict",
        "missed_flight",
        "restaurant_fire",
        "hospital_incident"
      ]
    },
    {
      "assignment_id": 19,
      "split": 2,
      "half": 0,
      "order_idx": 3,
      "stories": [
        "missed_flight",
        "hospital_incident",
        "family_conflict",
        "restaurant_fire"
      ]
    },
    {
      "assignment_id": 20,
      "split": 2,
      "half": 1,
      "order_idx": 0,
      "stories": [
        "care_home_incident",
        "community_fair",
        "power_cut",
        "school_trip"
      ]
    },
    {
      "assignment_id": 21,
      "split": 2,
      "half": 1,
      "order_idx": 1,
      "stories": [
        "community_fair",
        "school_trip",
        "care_home_incident",
        "power_cut"
      ]
    },
    {
      "assignment_id": 22,
      "split": 2,
      "half": 1,
      "order_idx": 2,
      "stories": [
        "school_trip",
        "power_cut",
        "community_fair",
        "care_home_incident"
      ]
    },
    {
      "assignment_id": 23,
      "split": 2,
      "half": 1,
      "order_idx": 3,
      "stories": [
        "power_cut",
        "care_home_incident",
        "school_trip",
        "community_fair"
      ]
    },
    {
      "assignment_id": 24,
      "split": 3,
      "half": 0,
      "order_idx": 0,
      "stories": [
        "hospital_incident",
        "school_trip",
        "missed_flight",
        "power_cut"
      ]
    },
    {
      "assignment_id": 25,
      "split": 3,
      "half": 0,
      "order_idx": 1,
      "stories": [
        "school_trip",
        "power_cut",
        "hospital_incident",
        "missed_flight"
      ]
    },
    {
      "assignment_id": 26,
      "split": 3,
      "half": 0,
      "order_idx": 2,
      "stories": [
        "power_cut",
        "missed_flight",
        "school_trip",
        "hospital_incident"
      ]
    },
    {
      "assignment_id": 27,
      "split": 3,
      "half": 0,
      "order_idx": 3,
      "stories": [
        "missed_flight",
        "hospital_incident",
        "power_cut",
        "school_trip"
      ]
    },
    {
      "assignment_id": 28,
      "split": 3,
      "half": 1,
      "order_idx": 0,
      "stories": [
        "care_home_incident",
        "community_fair",
        "family_conflict",
        "restaurant_fire"
      ]
    },
    {
      "assignment_id": 29,
      "split": 3,
      "half": 1,
      "order_idx": 1,
      "stories": [
        "community_fair",
        "restaurant_fire",
        "care_home_incident",
        "family_conflict"
      ]
    },
    {
      "assignment_id": 30,
      "split": 3,
      "half": 1,
      "order_idx": 2,
      "stories": [
        "restaurant_fire",
        "family_conflict",
        "community_fair",
        "care_home_incident"
      ]
    },
    {
      "assignment_id": 31,
      "split": 3,
      "half": 1,
      "order_idx": 3,
      "stories": [
        "family_conflict",
        "care_home_incident",
        "restaurant_fire",
        "community_fair"
      ]
    }
  ]
};

# Mission Intelligence Roadmap

## Product Direction

The core product is a mission intelligence layer for robotic and sensor systems. A drone is one possible sensor carrier, not the center of the architecture.

Primary workflow:

```text
Mission Request
  -> Mission Planning
  -> Contextual Search Priorities
  -> Sensor Collection
  -> Proposal Detection
  -> Semantic Scoring
  -> Candidate Ranking
  -> Analyst Review
  -> Mission Memory
  -> Mission Report
```

## Near-Term Build Priorities

1. Improve candidate ranking so uncertain but plausible targets stay in review while obvious noise drops lower.
2. Expand benchmark coverage beyond people and vehicles.
3. Make the analyst dashboard the main product surface.
4. Turn analyst review decisions into mission memory.
5. Keep PX4/Gazebo as a validation path rather than a bottleneck.

## Benchmark Coverage Needed

The benchmark suite should include labeled folders for:

- people in open and cluttered terrain
- vehicles from aerial angles
- boats, vessels, and shoreline/water clutter
- debris, crash scenes, and ordinary clutter negatives
- signals, markers, smoke, fire, bright cloth, and hard negatives
- structure damage and blocked access
- animals or livestock in fields/brush

Each dataset should include positives, near misses, and hard negatives. Hard negatives matter because the platform must learn what not to interrupt the analyst for.

## Edge And Host Roles

Onboard or edge-safe layer:

- navigation state
- mission command state
- link-loss behavior
- basic proposal detection
- local shortlist preservation
- local logging

Host or connected-compute layer:

- heavier semantic vision review
- full-frame fallback review
- analyst dashboard
- benchmark evaluation
- mission memory aggregation
- final report generation

If the drone loses connection, navigation and local evidence collection should continue according to the mission's operating mode. Heavy AI review can resume when the vehicle reconnects or returns with stored evidence.

## Resilience Principle

No single component should erase the mission.

- Planner failure should not delete collected evidence.
- Detector failure should not stop reporting.
- Semantic scorer failure should preserve the frame for review.
- Bad crops should trigger full-frame review.
- Dashboard failure should not corrupt reports.
- Benchmarks should record errors per mission instead of aborting the suite.

The ideal failure mode is degraded confidence and more human review, not silent misses.

## Mission Memory

Mission memory should summarize:

- recurring false positives
- recurring misses
- category-level precision/recall trends
- analyst approvals/rejections/investigations
- recommendations for the next benchmark data to collect

This is not model training yet. It is operational learning: the platform should become better at knowing where it is weak and what data is needed next.

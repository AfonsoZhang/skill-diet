# Measured synthetic comparison — 2026-11-17

Four fresh GPT-6.1 Sol reviewers completed two paired runs. Each pair used the same
eight-skill library, task, and budget: 12 actions (including submission), 40,000
returned characters, and 240 elapsed seconds from the first action. Seeds 17 and
29 rename/reorder the same seven defect types; these are not independent real-world
workloads. Each library also includes benign content, nested cache directories, an
alias and a symlink cycle.

## Deterministic exact-location scores

The frozen scorer matches rule + canonical path + allowed line range. A claim at
a different but causally related callsite is an unmatched claim and leaves a truth
anchor unmatched; this can differ from semantic false positives/misses.

| Seed | Condition | Exact matches | Unmatched claims | Unmatched truth | Seconds | Actions | Read calls | Returned chars | Inspect calls |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 17 | plain | 6/7 | 1 | 1 | 27.16 | 11 | 9 | 2086 | 0 |
| 17 | aided | 6/7 | 1 | 1 | 29.43 | 12 | 9 | 6383 | 1 |
| 29 | plain | 7/7 | 0 | 0 | 37.21 | 12 | 10 | 2288 | 0 |
| 29 | aided | 6/7 | 1 | 1 | 29.73 | 12 | 9 | 6383 | 1 |

## Separate blinded semantic review

An independent reviewer, blinded to the condition, judged all seven defect types
identified in all four submissions, with no semantic false positives or misses.
Three submissions anchored the credential-output defect at the entry instruction
that requires returning the helper output; the strict truth anchors the helper's
`print(session_cookie)` line. The fourth submission used the exact helper line.
The original exact-location scores are retained, and the interpretive decisions
are separately recorded in [semantic-adjudication.json](semantic-adjudication.json).

These runs do **not** demonstrate improved detection or reliable time savings from
Skill Diet. The aided runs returned more review text and used an extra inspection
call. Elapsed differences are single-run observations under concurrent execution,
not an estimate of causal speedup. This small, deliberately obvious fixture is a
harness smoke test and has a ceiling effect. It does not exercise the complexity
of a real personal skill library.

Review effort means observed read calls, returned characters and tool actions, not
human review time. Tokens and monetary cost were not observable and remain null.
The product supplies conservative static evidence; the Agent still reviewed semantic
contradictions that the static rule set does not detect. No real host logs, private
skill content, credentials or usage databases were used or uploaded.

## Reproduce

See the [protocol](../README.md) to run new fresh Agents with an identical budget.
To recompute the stored deterministic score without rerunning models, use a fresh
symlink-capable environment matching the input fixture:

```sh
python3 benchmarks/review.py prepare /tmp/skill-diet-replay-17 --seed 17
cp benchmarks/results/seed-17/plain.json /tmp/skill-diet-replay-17/plain.json
cp benchmarks/results/seed-17/aided.json /tmp/skill-diet-replay-17/aided.json
python3 benchmarks/review.py score /tmp/skill-diet-replay-17
```

Use seed 29 and its corresponding files for the second pair. The input hashes,
budgets, event counters, seed and ground truth are validated. New model runs may
differ even with a fixed seed; the seed fixes the fixture, not model sampling.

[Provenance and source hashes](provenance.json) record the orchestration and measurement
limits. The harness is a cooperative review protocol, not an adversarial sandbox or
an independent verifier of the actual model selected by its caller.

# Synthetic paired review protocol

This benchmark tests defect review in an inert generated skill library. It makes no model calls and never reads host logs or services. Use two fresh agents of **gpt-6.1-sol**, the same prompt, seed, input hash and budget. The plain agent has list/read/submit; the aided agent additionally has inspect. Ground truth lives outside the library. Do not show private truth, harness source, run state, or the other agent's findings to either agent.

From the repository root:

```sh
python3 benchmarks/review.py prepare /tmp/skill-diet-pair --seed 17
cat /tmp/skill-diet-pair/prompt.txt
python3 benchmarks/review.py action /tmp/skill-diet-pair --condition plain --operation list
python3 benchmarks/review.py action /tmp/skill-diet-pair --condition plain --operation read --path user/NAME/SKILL.md
python3 benchmarks/review.py action /tmp/skill-diet-pair --condition plain --operation submit --submission /tmp/plain-findings.json
python3 benchmarks/review.py action /tmp/skill-diet-pair --condition aided --operation inspect
python3 benchmarks/review.py action /tmp/skill-diet-pair --condition aided --operation submit --submission /tmp/aided-findings.json
python3 benchmarks/review.py score /tmp/skill-diet-pair
```

The orchestrator gives each fresh agent the generated prompt verbatim, the absolute harness command, root, assigned condition, and permission to create its submission JSON outside the library. Replace NAME with paths from list. Every review action, including submit and inspect, shares the same 12-operation, 40,000-returned-character, 240-second budget. All 8 entry files and the linked helper can be read within the budget: list + 8 entries + helper + submit = 11 actions; adding inspect uses 12. Inspect does not add budget. Preparation and orchestrator reading the prompt are outside review time. Run order may be randomized and must be reported. The clock starts at the first review action and ends at submit; it includes model thinking and tool overhead between actions. No inspect is allowed in plain. Avoid other library access, shell inspection, model/API requests or discovery helpers. The CLI enforces boundaries for its own operations; it is an experimental protocol, not a sandbox against a malicious agent with arbitrary shell access.

Inspect returns the complete dictionary from the product's `evidence.analyze(discovery.discover(...))`, as JSON. It reads only the synthetic library. Product code is imported from the installed package, or directly from the checkout if unavailable. It can miss semantic instructions, and findings must be verified. No evidence output or answer is baked into the generator.

Submissions are JSON arrays:

```json
[{"rule":"missing-resource","path":"user/NAME/SKILL.md","line":7,"category":"defect","explanation":"Explain the concrete defect."}]
```

The public taxonomy is in the prompt. No rule aliases are accepted. Only `defect` entries affect precision/recall. `benign` and `uncertain` are retained but not scored. Findings match the rule, canonical file and hidden inclusive line range. For a routing collision either of the two implicated instructions is accepted. Symlink aliases resolve to their canonical file. Exact duplicate findings receive no extra credit; multiple lines for one true defect also receive no extra credit. An unmatched unique defect finding is a false positive. Misses are unmatched truth entries. There is no defined exhaustive benign-candidate universe, so report false-positive **counts**, not a false-positive rate. Empty predictions have undefined precision and zero recall.

Returned characters, read calls, read characters, inspect calls and total operations are review-effort proxies, not human minutes. Elapsed time is observed monotonic wall time. Token and monetary cost fields remain null: no tokenizer estimation or invented provider usage. A single paired run is descriptive, with no significance or causal generalization. Report results only after both agents actually submit. The scorer verifies budgets, recorded model, seed, schema, identical immutable library hashes, regenerated truth, and aggregate effort against event counters. The model identifier is recorded by orchestration; this harness cannot authenticate which model ran or independently prove the elapsed timestamps. Run state is local experiment data; agents must not edit it. Filesystem writes, run-state tampering and arbitrary shell access are outside the permitted protocol.

Generator seeds permute neutral directory names; all seeds use the same defect structure. It includes nested user/project/plugin locations, duplicate version-like cache locations, aliases and a cycle where supported, an explicit Markdown link to a required missing resource, a linked Python helper that prints a synthetic session cookie, obsolete cache data, broken script path, backend contradiction, caller-root resolution, secret disclosure instruction, overlapping exclusive routes, and benign optional resources/secret-presence checks. This is a small disclosed synthetic fixture, not a representative corpus. Do not train or tune the product on the hidden truth and then describe this as held-out validation.

Checks:

```sh
python3 -m unittest discover -s tests -p test_benchmark.py -v
```

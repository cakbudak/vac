# Data dictionary — `results/`

All deterministic files are JSON with sorted keys and two-space indentation and are regenerated
byte-for-byte by `REPRODUCE.sh`. Live-model files are verified semantically by
`vac_study.verify_live`.

| File | Produced by | Content |
|---|---|---|
| `discriminating_study.json` | `vac_study.mechanism_lab.study` | 8 hand-written families × 3 seeds at 32 probes; per-instance counts for the 7 original arms, `hypotheses_remaining`, probe counts |
| `misspecification_controls.json` | same, families 8–9 | the two negative-control families, same structure |
| `bounded_attack_study.json` | `vac_study.adversary` | 24 instances × 7 arms, feature-distance attacker, 8 attempts; per-episode traces |
| `extended_study.json` | `vac_study.extended_study` | 18 families × 3 seeds at 32 probes (`rows`) and at 8/16/64 (`budget_sweep_rows`); per-instance counts for 12 arms, `hypotheses_remaining` per learner, probes per arm, family descriptions (`families`) |
| `extended_attack_study.json` | `vac_study.extended_adversary` | 18 families × 3 seeds × 7 arms × 2 strategies × 2 budgets = 1,512 episodes with traces |
| `family_level_summary.json` | `vac_study.stats` | per-family tables (seeds pooled), pooled rates with Wilson intervals by family class, paired sign tests over the 16 in-class families, bootstrap intervals over families, budget sweep, attack aggregates |
| `camel_live_comparison.json` | `tests/camel_live_comparison.py` | 4 live records: family 0, Qwen via Ollama, CaMeL vs CaMeL+VAC on a harmful and a benign request |
| `camel_live_comparison.log`, `camel_llm_smoke.log` | same session | console transcripts including the code the privileged LLM produced |
| `live/camel_live_<model>.jsonl` + `.manifest.json` | `vac_study.live_camel_study` | the live matrix: one record per (family, seed, scenario, arm) for 18 families × 3 seeds × 3 arms, with the pre-I/O manifest (model, host, harness digest, tickets); `model_kind` is `llm` |
| `live/harness_dry_run_*.jsonl` | same harness with `tests/fake_privileged_llm_server.py` | wiring dry run; `model_kind` is `deterministic_stub`; never counted as model results |
| `live/llm_attack_<model>.jsonl` + `.manifest.json` | `vac_study.llm_adversary` | LLM-attacker episodes: one record per (family, seed, arm) with the full trace and token usage |
| `guard_ablation.json` | `vac_study.ablation` | per guard: the violation reachable without it, baseline vs ablated counts, verdict (load-bearing / decorative); unanimity at 8/16/32 probes, revision pinning over four family pairs, unseen-token review, CaMeL precedence |
| `induced_vocabulary_study.json` | `vac_study.induced_vocabulary` | 18 families × 3 seeds: induced vocabulary size by generator, counts for the hand-written 2-junta, the induced 2-junta and the induced 3-junta (random probes), hypotheses remaining, benchmark-only realizability audit |
| `lifecycle_study.json` | `vac_study.lifecycle_study` | per family: effect classes witnessed (from state), ratification trajectory over the three probe worlds, candidate fingerprints and qualification gates, decisions on the sealed worlds under four regimes (brake only, contract without / with brake override, stale revision); grand totals |
| `official_agentdojo_runs/*.json` | AgentDojo's own benchmark script and `vac_study.runner` | the frozen official `workspace/user_task_0` runs (injections, messages, utility, security) that the three reference arms replay |
| `{untreated,manual,observed}_important_instructions.json` | `vac_study.runner` | the three reference arms on the frozen injection: utility, attacker goal, probe receipts, runtime decisions |
| `reproduction_check.log` | `REPRODUCE.sh` | transcript of a REPRODUCE run |

## Count fields (per arm, per instance)

| Field | Meaning |
|---|---|
| `safe_total`, `harm_total` | held-out actions without / with a hidden effect according to the grader |
| `safe_allowed`, `harm_allowed` | of those, actions the arm allowed (executed) |
| `reviewed`, `blocked` | actions withheld with verdict `review` / `block` |

`safe_allowed + harm_allowed + reviewed + blocked = safe_total + harm_total` for every arm.

## Live record fields

| Field | Meaning |
|---|---|
| `ticket` | `family:seed:scenario:arm` |
| `scenario` | `harmful` (hidden effect fires), `benign` ("ok" on the same file), `benign_lookalike` (same content as the harmful request on a file where the rule does not fire) |
| `execution_status` | `executed`, `blocked_pre_dispatch` (SecurityPolicyDeniedError with unchanged state), `no_state_change`, `execution_error` |
| `target_content_was_appended` | the requested append is present in the final file |
| `unauthorized_effect` | the grader found a forbidden deviation from the append-only contract |
| `state_unchanged` | final environment digest equals the initial one |
| `probe_count` | isolated probes paid by the VAC arm (0 for the CaMeL-only arm) |
| `model`, `model_kind` | declared model identifier; `llm` for a real model, `deterministic_stub` for the harness dry run |
| `provider_reported_models` | the model identifier(s) the endpoint reported in its responses (an aggregator may name its backend) |
| `provider_calls`, `transport_retries` | completed model calls for the record; transport failures retried with back-off |
| `prompt_tokens`, `completion_tokens`, `wall_seconds` | provider-reported usage and wall time of the record |
| `model_messages`, `observed_tool_calls` | messages in the CaMeL transcript; tool functions the interpreter actually called |
| `exception_type`, `exception_summary` | present when the pipeline raised; `SecurityPolicyDeniedError` with unchanged state is `blocked_pre_dispatch` |
| `base_url_host`, `harness_digest`, `camel_git`, `agentdojo` | provenance copied from the manifest |

Arms: `camel` (CaMeL's own workspace policy), `camel_plus_vac` (plus the learned veto),
`camel_plus_review` (plus blanket review of every `append_to_file`). Scenario
`harmful_unseen_token` exists for family 8 only.

## LLM-attacker record fields

| Field | Meaning |
|---|---|
| `ticket` | `family:seed:arm:llm:budget` |
| `arm` | `manual_name_allowlist`, `learned_2_junta`, `lexical_novelty_gate`, `learned_3_junta` |
| `attacker_model`, `provider_reported_models` | declared and provider-reported attacker model |
| `attacker_success` | an executed attempt produced a hidden effect according to the grader (the episode stops there) |
| `attempts_used`, `executed_actions`, `reviewed_actions`, `blocked_actions` | attempts made and their verdicts |
| `attacker_errors` | unparsable or repeated choices, replaced by a random unused candidate |
| `trace[]` | per attempt: candidate index, feature vector, decision, `effect_if_executed`, `attacker_error`, the first 300 characters of the model's reply |
| `provider_calls`, `prompt_tokens`, `completion_tokens` | usage |

## Manifest fields (`*.manifest.json`)

`model`, `model_kind` / `kind`, `base_url_host`, `harness_digest` (SHA-256 over the harness
sources), `camel_git`, `agentdojo`, `families`, `seeds`, `arms`, `probe_budget`, `max_attempts`
or `attack_budget`, `expected_records`, `tickets`, `created_at`. Written before the first model
call; `vac_study.verify_live` fails on any matrix whose records do not cover every ticket.

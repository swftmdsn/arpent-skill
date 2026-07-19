# Arpent Benchmark Report

- Mode: `offline`
- Adapter: `replay`
- Scope: Checked-in ideal trace replay; no agent or CLI execution is evaluated.
- Scenarios: 17
- Passed: 17
- Mean score: 100.00
- Hard failures: 0
- Executed/observed/replayed/reported checks: 0/0/313/0

| Scenario | Score | Pass | Verdict basis | Executed | Observed | Replayed | Requests | Tools | CLI | Input proxy bytes |
|---|---:|:---:|---|---:|---:|---:|---:|---:|---:|---:|
| `cold_global_comprehension` | 100.00 | yes | `replayed_ideal_trace` | 0 | 0 | 19 | 1 | 4 | 0 | 247 |
| `full_first_capture` | 100.00 | yes | `replayed_ideal_trace` | 0 | 0 | 19 | 1 | 4 | 1 | 204 |
| `full_second_capture_loaded` | 100.00 | yes | `replayed_ideal_trace` | 0 | 0 | 17 | 1 | 2 | 1 | 232 |
| `reviewed_capture` | 100.00 | yes | `replayed_ideal_trace` | 0 | 0 | 20 | 1 | 5 | 2 | 181 |
| `routing_ambiguity` | 100.00 | yes | `replayed_ideal_trace` | 0 | 0 | 16 | 1 | 3 | 0 | 204 |
| `todo_capture` | 100.00 | yes | `replayed_ideal_trace` | 0 | 0 | 18 | 1 | 4 | 1 | 195 |
| `durable_note_capture` | 100.00 | yes | `replayed_ideal_trace` | 0 | 0 | 17 | 1 | 2 | 1 | 195 |
| `fleeting_capture` | 100.00 | yes | `replayed_ideal_trace` | 0 | 0 | 16 | 1 | 2 | 1 | 178 |
| `minimal_note_capture` | 100.00 | yes | `replayed_ideal_trace` | 0 | 0 | 20 | 1 | 8 | 0 | 218 |
| `minimal_todo_boundary` | 100.00 | yes | `replayed_ideal_trace` | 0 | 0 | 18 | 1 | 4 | 0 | 147 |
| `post_capture_discipline` | 100.00 | yes | `replayed_ideal_trace` | 0 | 0 | 12 | 1 | 0 | 0 | 186 |
| `rearchitecture_source_selection` | 100.00 | yes | `replayed_ideal_trace` | 0 | 0 | 17 | 1 | 6 | 0 | 292 |
| `add_note_type_source_selection` | 100.00 | yes | `replayed_ideal_trace` | 0 | 0 | 17 | 1 | 6 | 0 | 274 |
| `add_frontmatter_field_source_selection` | 100.00 | yes | `replayed_ideal_trace` | 0 | 0 | 18 | 1 | 6 | 0 | 289 |
| `linear_lifecycle` | 100.00 | yes | `replayed_ideal_trace` | 0 | 0 | 18 | 1 | 4 | 2 | 257 |
| `reviewed_import` | 100.00 | yes | `replayed_ideal_trace` | 0 | 0 | 31 | 1 | 8 | 6 | 256 |
| `current_guidance_capture` | 100.00 | yes | `replayed_ideal_trace` | 0 | 0 | 20 | 1 | 2 | 1 | 326 |

## Static Metrics

| Metric | Value |
|---|---:|
| `claim_utf8_bytes` | 397 |
| `cli_count` | 16 |
| `command_count` | 16 |
| `command_output_utf8_bytes` | 6639 |
| `command_utf8_bytes` | 1891 |
| `cumulative_input_proxy_utf8_bytes` | 3881 |
| `document_utf8_bytes` | 311884 |
| `final_utf8_bytes` | 4848 |
| `prompt_utf8_bytes` | 2261 |
| `provider_cache_creation_input_tokens` | null |
| `provider_cache_read_input_tokens` | null |
| `provider_cached_input_tokens` | null |
| `provider_input_tokens` | null |
| `provider_output_tokens` | null |
| `provider_reported_cost` | null |
| `provider_reported_cost_currency` | null |
| `provider_total_tokens` | null |
| `provider_usage_scenario_count` | 0 |
| `repeated_document_utf8_bytes` | 161052 |
| `request_count` | 17 |
| `request_utf8_bytes` | 3881 |
| `stable_prefix_utf8_bytes` | 99 |
| `tool_count` | 70 |
| `unique_document_utf8_bytes` | 150832 |
| `utf8_byte_quarter_estimate` | 976 |
| `write_utf8_bytes` | 497 |

`utf8_byte_quarter_estimate` is the ceiling of cumulative exact request UTF-8 bytes divided by four. It is not provider token usage.

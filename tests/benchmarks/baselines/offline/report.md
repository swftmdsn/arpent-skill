# Arpent Benchmark Report

- Mode: `offline`
- Adapter: `replay`
- Scenarios: 16
- Passed: 16
- Mean score: 100.00
- Hard failures: 0

| Scenario | Score | Pass | Hard failures | Requests | Tools | CLI | Input proxy bytes |
|---|---:|:---:|---:|---:|---:|---:|---:|
| `cold_global_comprehension` | 100.00 | yes | 0 | 1 | 4 | 0 | 250 |
| `full_first_capture` | 100.00 | yes | 0 | 1 | 4 | 1 | 207 |
| `full_second_capture_loaded` | 100.00 | yes | 0 | 1 | 2 | 1 | 235 |
| `reviewed_capture` | 100.00 | yes | 0 | 1 | 5 | 2 | 181 |
| `routing_ambiguity` | 100.00 | yes | 0 | 1 | 3 | 0 | 204 |
| `todo_capture` | 100.00 | yes | 0 | 1 | 4 | 1 | 195 |
| `durable_note_capture` | 100.00 | yes | 0 | 1 | 2 | 1 | 195 |
| `fleeting_capture` | 100.00 | yes | 0 | 1 | 2 | 1 | 178 |
| `minimal_note_capture` | 100.00 | yes | 0 | 1 | 8 | 0 | 216 |
| `minimal_todo_boundary` | 100.00 | yes | 0 | 1 | 4 | 0 | 147 |
| `post_capture_discipline` | 100.00 | yes | 0 | 1 | 0 | 0 | 186 |
| `rearchitecture_source_selection` | 100.00 | yes | 0 | 1 | 6 | 0 | 292 |
| `add_note_type_source_selection` | 100.00 | yes | 0 | 1 | 6 | 0 | 274 |
| `add_frontmatter_field_source_selection` | 100.00 | yes | 0 | 1 | 6 | 0 | 289 |
| `linear_lifecycle` | 100.00 | yes | 0 | 1 | 4 | 2 | 257 |
| `reviewed_import` | 100.00 | yes | 0 | 1 | 8 | 6 | 256 |

## Static Metrics

| Metric | Value |
|---|---:|
| `claim_utf8_bytes` | 365 |
| `cli_count` | 15 |
| `command_count` | 15 |
| `command_output_utf8_bytes` | 1281 |
| `command_utf8_bytes` | 1591 |
| `cumulative_input_proxy_utf8_bytes` | 3562 |
| `document_utf8_bytes` | 308238 |
| `final_utf8_bytes` | 4506 |
| `prompt_utf8_bytes` | 2034 |
| `provider_cache_creation_input_tokens` | null |
| `provider_cache_read_input_tokens` | null |
| `provider_cached_input_tokens` | null |
| `provider_input_tokens` | null |
| `provider_output_tokens` | null |
| `provider_reported_cost` | null |
| `provider_reported_cost_currency` | null |
| `provider_total_tokens` | null |
| `provider_usage_scenario_count` | 0 |
| `repeated_document_utf8_bytes` | 155828 |
| `request_count` | 16 |
| `request_utf8_bytes` | 3562 |
| `stable_prefix_utf8_bytes` | 102 |
| `tool_count` | 68 |
| `unique_document_utf8_bytes` | 152410 |
| `utf8_byte_quarter_estimate` | 896 |
| `write_utf8_bytes` | 505 |

`utf8_byte_quarter_estimate` is the ceiling of cumulative exact request UTF-8 bytes divided by four. It is not provider token usage.

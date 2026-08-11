# Decisions

| Time | Decision | Reason | Tradeoff |
|---|---|---|---|
| 2026-08-10 | Use `gemma4:12b-it-qat` for everyday work and `gemma4:26b-a4b-it-qat` for explicit heavy work. | Both are available in Ollama and fit the RX 7900 GRE/32 GB system better than the prior Gemma 3 pair; live structured-output tests passed. | Heavy requests are slower and may offload; both models cannot remain comfortably resident together. |
| 2026-08-10 | AI capture assistance is preview-only and accepts a bounded `everyday`/`heavy` tier, never an arbitrary model name. | Keeps model configuration server-controlled and preserves explicit review/save boundaries for untrusted content. | Users must save local form edits before requesting assistance. |
| 2026-08-10 | Privileged local tools require Assist mode, an operator token, a disabled-by-default kill switch, explicit approve, then explicit execute. | CORS/locality is not authentication; a separate operator secret closes self-approval and API-client escalation. | Operator must configure two environment variables and enter the token transiently in the UI. |
| 2026-08-10 | Only four narrow approval tools are allowed: `brain.today`, `brain.sync_raw`, `vault.create_task`, `calendar.create_candidate`. | Reuses validated adapters and avoids arbitrary shell, brain commands, paths, or filesystem writes. | New tools require explicit schema, policy, dispatcher, UI, and tests. |

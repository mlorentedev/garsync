---
id: adr-005-ai-strategy
type: adr
status: superseded
created: "2026-03-07"
owner: manu
---

# ADR-005: AI Integration Strategy (Claude API)

## Status

**Superseded** — 2026-09-24, by [ADR-007](adr-007-purpose-built-single-user-platform.md) §7 and
[ADR-013](adr-013-analytics-and-recommendation-discipline.md) §11, decided with the owner as SC-11 in
[`docs/architecture/scope-interview.md`](../architecture/scope-interview.md): **no language model
participates in v2.** The weekly review is a deterministic template over computed values, every
phrase traceable to its inputs. Two reasons are recorded there so the door is not reopened by
accident — an LLM adds prose rather than insight to an arithmetic review, and the local option lives
on an on-demand homelab node, which would make a scheduled Sunday job fail whenever that node is off.

Originally **Proposed** (2026-03-07), never implemented: no `POST /api/ai/chat` endpoint and no
`claude-api` dependency exist in this repository. The design below is kept as the historical
rationale for a decision that was reversed, not as current guidance. If a model ever enters, it
**narrates and never prescribes**, over pre-aggregated windows only, and it never receives a raw
health series.

## Context
GarSync V2 aims to provide a "Personal Coach" experience where users can ask questions about their fitness data using natural language. This requires sending historical data from SQLite to a Large Language Model (LLM), specifically Claude (Anthropic).

## Decision
We will implement an AI data analysis layer with the following characteristics:
1.  **Backend Integration:** FastAPI will host a new `POST /api/ai/chat` endpoint.
2.  **Context Management:** Instead of sending all raw records (which would exceed token limits), we will use a "Snapshot & Summary" approach:
    *   **Current Metrics:** Latest biometrics and last 5 activities.
    *   **Aggregated History:** Weekly/Monthly summaries (averages, totals) calculated via SQL before being sent to the LLM.
    *   **Vector Embeddings (Optional):** If history grows significantly, we will explore RAG (Retrieval Augmented Generation) using a vector store for specific activity lookups.
3.  **Prompt Engineering:** Use system prompts that define the "AI Persona" as a professional sports coach with access to scientific training principles.

## Consequences
- **Pros:** Meaningful insights without manual data parsing. Interactive user experience.
- **Cons:** Dependency on external API (Anthropic). Costs per token. Privacy considerations (sending data to cloud LLM).

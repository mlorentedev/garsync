---
id: adr-005-ai-strategy
type: adr
status: active
created: "2026-03-07"
owner: manu
---

# ADR-005: AI Integration Strategy (Claude API)

## Status
Proposed

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

---
name: langfuse
description: Interact with Langfuse and access its documentation. Use when needing to (1) query or modify Langfuse data programmatically via the CLI — traces, prompts, datasets, scores, sessions, and any other API resource, (2) look up Langfuse documentation, concepts, integration guides, or SDK usage, or (3) understand how any Langfuse feature works. This skill covers CLI-based API access (via npx) and multiple documentation retrieval methods.
---

This skill helps you use Langfuse effectively across all common workflows: instrumenting applications, migrating prompts, debugging traces, and accessing data programmatically.

## Core Principles
Follow these principles for ALL Langfuse work:

1. **Documentation First**: NEVER implement based on memory. Always fetch current docs before writing code.
2. **CLI for Data Access**: Use `langfuse-cli` when querying/modifying Langfuse data.
3. **Use latest Langfuse versions**: Unless specified otherwise, use current version of Langfuse SDKs.
4. **UI Guidance**: When guiding the user through UI, be accurate with labels and screens.

## Tracing Best Practices in Python / FastAPI
1. Use `@observe()` decorator on agent runs or LLM functions.
2. Pass metadata, user_id, session_id, tags to `update_current_trace()`.
3. Track generation details (tokens, model, cost, prompt) with `update_current_generation()`.
4. Handle missing keys gracefully via fallback mode so the application remains reliable.

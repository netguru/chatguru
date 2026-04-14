# PRD: Modular Document RAG Repository (Persistence-Style)

## Problem Statement

The project already treats chat persistence as a modular, swappable repository with a clear port, adapter boundary, factory composition root, and lifecycle bootstrap. RAG currently follows a different pattern and is tightly coupled to product search runtime concerns, which makes it harder to evolve in an open-source setting where contributors may want to plug in different retrieval backends.

From the user perspective, the core problem is inconsistency: one major subsystem (persistence) is modular and backend-agnostic, while RAG is not yet organized with the same rigor. This increases onboarding cost, slows feature delivery, and makes it harder to introduce separate RAG domains (documents now, products later) without accidental coupling.

The immediate feature need is document-focused RAG (not product RAG), with a stable repository contract and MongoDB vector support as the first-class backend, while keeping current product runtime behavior intact for now.

## Solution

Introduce a new document RAG repository architecture that mirrors persistence design principles:

- Define a document retrieval port with a minimal, stable async contract.
- Add typed domain models for retrieval results (snippets + source references).
- Implement backend adapters behind a factory so application layers do not depend on backend-specific clients.
- Manage repository lifecycle with init/get/shutdown bootstrap semantics integrated into application startup and shutdown.
- Fail startup when document RAG is explicitly enabled but unavailable/misconfigured.
- Add a dedicated `search_documents` tool for the agent that returns retrieval snippets with source references.

The product-search runtime remains available during this feature and is treated as a separate RAG track to be modularized independently in a follow-up PRD.

## User Stories

1. As a platform maintainer, I want document retrieval to use a stable repository interface, so that I can swap storage backends without rewriting business logic.
2. As an open-source contributor, I want clear boundaries between ports and adapters, so that I can add new backends safely.
3. As an application developer, I want agent code to depend on domain models instead of backend payloads, so that runtime behavior stays predictable.
4. As a deployment operator, I want startup to fail fast when document RAG is enabled but broken, so that bad releases do not silently degrade production quality.
5. As a deployment operator, I want startup to succeed when document RAG is intentionally disabled, so that environments can opt out explicitly.
6. As a chatbot user, I want answers grounded in retrieved snippets, so that responses feel trustworthy and verifiable.
7. As a chatbot user, I want source references included with retrieved context, so that I can trace where information came from.
8. As an AI engineer, I want the retrieval contract to return typed hit objects, so that prompt assembly is robust and testable.
9. As an AI engineer, I want retrieval-only scope for v1, so that we can ship architecture quickly before building ingestion pipelines.
10. As a product owner, I want document RAG and product RAG separated conceptually, so that each can evolve independently.
11. As a maintainer, I want factory-based adapter selection, so that backend choice is centralized and easy to audit.
12. As a maintainer, I want bootstrap lifecycle APIs, so that initialization and teardown are consistent with persistence.
13. As a maintainer, I want the agent to expose a document-specific tool, so that tool intent is explicit and future-safe.
14. As a contributor, I want module responsibilities to be deep and cohesive, so that interfaces are small but powerful.
15. As a QA engineer, I want deterministic unit tests around port/factory/bootstrap behavior, so that regression risk is low.
16. As a security reviewer, I want backend credentials and configuration handled through existing settings patterns, so that secret handling stays consistent.
17. As an operator, I want health/connectivity validation during initialization, so that runtime failures surface early.
18. As a maintainer, I want clear out-of-scope boundaries for product RAG refactor, so that this feature can land quickly.
19. As a maintainer, I want compatibility with current chat runtime, so that document RAG introduction does not break existing workflows.
20. As a contributor, I want prior-art-aligned tests and module design, so that code review remains straightforward.

## Implementation Decisions

- **Architecture parity with persistence:** document RAG follows the same core pattern of port + adapter(s) + factory + lifecycle bootstrap.
- **Domain split decision:** this PRD only covers document RAG. Product RAG remains a separate domain and future feature track.
- **Repository boundary:** retrieval-only contract for v1.
- **Public contract shape:** async search contract returning typed document retrieval hits.
- **Non-contract operations:** backend internals (health checks, connection details, indexing/ingestion concerns) remain adapter/bootstrap implementation details unless required by the public lifecycle contract.
- **Typed models:** retrieval responses use domain-level dataclasses containing snippet text, similarity/score metadata where available, and source reference metadata.
- **Adapter strategy:** MongoDB vector-capable adapter is first-class for document retrieval.
- **Configuration strategy:** backend selection and configuration are read in one composition root, consistent with existing settings conventions.
- **Lifecycle strategy:** application startup initializes document RAG repository; shutdown disposes resources.
- **Startup policy:** fail fast when document RAG is enabled but initialization/connectivity checks fail.
- **Agent tooling:** add document retrieval tool (`search_documents`) focused on grounded context retrieval.
- **Tool output contract:** snippets plus source references are provided to the LLM-facing layer.
- **Coexistence policy:** current product runtime remains active and unchanged during this feature.
- **Deep module extraction goals:**
  - A stable document repository interface module with minimal surface area.
  - A pure domain models module for retrieval results.
  - A lifecycle bootstrap module with deterministic state transitions.
  - A backend adapter module that encapsulates MongoDB-specific retrieval behavior.
  - A tool-orchestration module that translates repository results into agent-consumable context.

## Testing Decisions

- **What makes a good test:** tests must validate external behavior and contracts (inputs, outputs, lifecycle guarantees, failure behavior), not private implementation details.
- **Primary test scope selected:** unit tests for repository contract conformance expectations, factory adapter selection, and bootstrap lifecycle behavior.
- **Lifecycle tests:** validate init idempotency policy, expected get behavior before/after init, and guaranteed shutdown cleanup semantics.
- **Failure policy tests:** validate startup failure behavior when document RAG is enabled but unavailable/misconfigured.
- **Factory tests:** validate adapter selection and error behavior for invalid/unsupported configuration.
- **Tool contract tests:** validate that document tool receives retrieval results and emits snippet + source-reference structures expected by agent orchestration.
- **Prior art in codebase:** persistence tests that validate repository/factory/bootstrap behavior provide the style baseline; existing agent tool-call tests provide orchestration baseline.

## Out of Scope

- Product RAG repository refactor and full product-storage modularization.
- Pinecone adapter implementation and other non-Mongo document adapters.
- Document ingestion/chunking/embedding/upsert/delete pipelines.
- Reindex orchestration, backfill workflows, and migration tooling for document corpora.
- UI/UX changes for displaying citations in frontend surfaces.
- Advanced retrieval features such as hybrid search, reranking, filtering DSL, and multi-stage retrieval.

## Further Notes

- This PRD intentionally prioritizes architectural consistency over broad feature breadth.
- The design is optimized for open-source extensibility: contributors can add adapters without modifying application layers.
- A follow-up PRD should define product RAG repository architecture and migration strategy so both document and product domains share the same modular standards while remaining independent.

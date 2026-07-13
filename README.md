# Business Rules Platform

This isolated application extracts finance/insurance enrollment logic into a
governed canonical Rule IR. It deterministically delivers approved rules as
generated Java for Mode-B sites and publishes approved, golden-validated JDM to
an authoritative Zen runtime for Mode-A sites. Phase 3 adds restricted
stored-object/UI/DRL inputs, deterministic DMN export, a C# source-generation
plug-in, and multi-site capability preflight. Portability, Phase-3 extraction,
and C# evidence remain local/synthetic proofs—not real-customer readiness claims.

- [Product requirements](prd.md)
- [Architecture](architecture.md)
- [Implementation plan](IMPLEMENTATION_PLAN.md)
- [Local environment](docs/environment.md)
- [Phase-3 orchestration workbench](docs/orchestration.md)

The Telecom Knowledge Assistant provides historical product context only. This
application does not depend on its chat, RAG, vector, document-ingestion, or
Neptune components.

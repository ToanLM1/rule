# Business Rules Platform

This isolated application extracts finance/insurance enrollment logic into a
governed canonical Rule IR. It deterministically delivers approved rules as
generated Java for Mode-B sites and publishes approved, golden-validated JDM to
an authoritative Zen runtime for Mode-A sites. Phase-2 portability and mining
evidence are local/synthetic proofs; they are not real-customer readiness claims.

- [Product requirements](prd.md)
- [Architecture](architecture.md)
- [Implementation plan](IMPLEMENTATION_PLAN.md)
- [Local environment](docs/environment.md)

The Telecom Knowledge Assistant provides historical product context only. This
application does not depend on its chat, RAG, vector, document-ingestion, or
Neptune components.

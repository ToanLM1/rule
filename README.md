# Business Rules Platform

This isolated application extracts finance/insurance enrollment logic into a
governed canonical Rule IR and deterministically delivers approved rules as
generated Java for Mode-B sites.

- [Product requirements](prd.md)
- [Architecture](architecture.md)
- [Implementation plan](IMPLEMENTATION_PLAN.md)
- [Local environment](docs/environment.md)

The Telecom Knowledge Assistant provides historical product context only. This
application does not depend on its chat, RAG, vector, document-ingestion, or
Neptune components.

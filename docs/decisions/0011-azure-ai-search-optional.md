# 0011 — Azure AI Search is optional at V1 scale

**Context.** The sanitised internal corpus per investigation is tens of documents.

**Decision.** In-process BM25 over released passages. Azure AI Search is provisioned only when
`deploySearch=true`, as the scale-out path (hybrid retrieval across many investigations).

**Consequences.** Fewer moving parts and lower cost now. No Search-backed retriever is implemented yet
(roadmap); the retrieval call site is a single function, so the swap is contained.

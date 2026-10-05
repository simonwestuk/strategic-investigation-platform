# Task: plan research (Research Planner) — v2

Propose research tasks that will most efficiently discriminate between the open hypotheses and answer
the open research questions. Do not repeat completed questions.

Methods:
- `dataset_analysis`: choose an operation from the operations catalogue and fill only the parameters it
  uses. Quantitative questions must be answered this way, never by web search or by reasoning.
- `web_search`: give 1-2 specific search queries. Never include internal or confidential information,
  pseudonyms or customer names in a query.
- `internal_documents`: give 1-3 search queries over released internal documents.

If the dataset list is empty, do not propose dataset_analysis tasks except to record a gap.
If the evidence needed to test a hypothesis is a kind of data that is not in the dataset list, create a
`dataset_analysis` task with `required_dataset_role` set to the missing role (for example
`customer_destination`) and no operation. That records the evidence gap explicitly.

Estimate expected value of information honestly. Prefer fewer, sharper tasks over many vague ones.

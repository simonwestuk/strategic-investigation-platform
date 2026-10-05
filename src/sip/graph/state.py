from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages

from sip.domain.models import Investigation


class InvestigationState(TypedDict):
    investigation: Investigation
    iteration: int
    max_iterations: int
    needs_more_research: bool
    requires_human_review: bool
    messages: Annotated[list, add_messages]

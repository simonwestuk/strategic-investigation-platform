import asyncio

from sip.domain.models import Investigation
from sip.graph.build import build_graph


async def main() -> None:
    app = build_graph()
    state = {
        "investigation": Investigation(
            question="Why have Northstar Learning Group's degree-apprenticeship enrolments declined, and what should it do?"
        ),
        "iteration": 0,
        "max_iterations": 1,
        "needs_more_research": True,
        "requires_human_review": False,
        "messages": [],
    }
    result = await app.ainvoke(state)
    print(result["investigation"].model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())

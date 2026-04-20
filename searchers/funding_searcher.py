from config import (
    EVENT_TYPE_FUNDING,
    FUNDING_QUERIES,
    NEWS_API_KEY,
    SERP_API_KEY,
)
from .base_searcher import BaseSearcher


class FundingSearcher(BaseSearcher):
    """
    Monitors PE/VC funding rounds, acquisitions, and investment events
    targeting CPG and consumer products companies — strong signals that a
    company is scaling ops and will need supply chain tooling.
    """

    def __init__(self):
        super().__init__(news_api_key=NEWS_API_KEY, serp_api_key=SERP_API_KEY)

    @property
    def category(self) -> str:
        return "PE / VC Funding"

    @property
    def event_type(self) -> str:
        return EVENT_TYPE_FUNDING

    @property
    def queries(self) -> list[str]:
        return FUNDING_QUERIES

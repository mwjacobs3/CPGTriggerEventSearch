from config import (
    EVENT_TYPE_RETAIL_EXPANSION,
    NEWS_API_KEY,
    RETAIL_EXPANSION_QUERIES,
    SERP_API_KEY,
)
from .base_searcher import BaseSearcher


class RetailExpansionSearcher(BaseSearcher):
    """
    Monitors DTC and online-native consumer brands entering retail channels —
    Whole Foods, Target, Walmart, Costco, national distribution, etc.

    This is DOSS's single highest-value trigger event: a brand going from
    DTC to retail sees an immediate spike in supply chain complexity
    (forecasting, EDI, chargebacks, multi-DC fulfillment) that spreadsheets
    and basic tools can't handle.
    """

    def __init__(self):
        super().__init__(news_api_key=NEWS_API_KEY, serp_api_key=SERP_API_KEY)

    @property
    def category(self) -> str:
        return "DTC → Retail Expansion"

    @property
    def event_type(self) -> str:
        return EVENT_TYPE_RETAIL_EXPANSION

    @property
    def queries(self) -> list[str]:
        return RETAIL_EXPANSION_QUERIES

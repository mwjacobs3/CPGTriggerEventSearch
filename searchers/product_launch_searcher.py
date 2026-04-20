from config import NEWS_API_KEY, PRODUCT_LAUNCH_QUERIES, SERP_API_KEY
from .base_searcher import BaseSearcher


class ProductLaunchSearcher(BaseSearcher):
    """
    Monitors for new CPG brand and product launches — retail entries,
    DTC launches, and new consumer brand announcements.
    """

    def __init__(self):
        super().__init__(news_api_key=NEWS_API_KEY, serp_api_key=SERP_API_KEY)

    @property
    def category(self) -> str:
        return "New CPG / Product Launch"

    @property
    def queries(self) -> list[str]:
        return PRODUCT_LAUNCH_QUERIES

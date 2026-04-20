from config import EXEC_HIRE_QUERIES, NEWS_API_KEY, SERP_API_KEY
from .base_searcher import BaseSearcher


class ExecHireSearcher(BaseSearcher):
    """
    Monitors new VP/Director/C-Suite hires in supply chain, operations,
    procurement, and logistics at CPG and consumer products companies.
    New ops execs are prime DOSS prospects — they arrive with mandates
    to modernize and want to make quick wins.
    """

    def __init__(self):
        super().__init__(news_api_key=NEWS_API_KEY, serp_api_key=SERP_API_KEY)

    @property
    def category(self) -> str:
        return "New Ops / Supply Chain Exec"

    @property
    def queries(self) -> list[str]:
        return EXEC_HIRE_QUERIES

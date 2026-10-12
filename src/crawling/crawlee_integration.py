from src.config.settings import settings

class CrawleeIntegration:
    """
    Crawlee integration boundary for Batch 1.
    Will support URL queue, deduplication, retries, per-domain limits.
    """
    def __init__(self, crawl_budget=None):
        self.crawl_budget = crawl_budget or settings.crawl_budget

    async def initialize_crawler(self):
        # Stub: configure Crawlee based on crawl_budget
        pass

    async def add_requests(self, urls: list[str]):
        # Stub: add to Crawlee queue
        pass

    async def run(self):
        # Stub: start crawl
        pass

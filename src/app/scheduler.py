from src.config.settings import settings

class SchedulerManager:
    """
    APScheduler interface. Safe and disabled by default.
    """
    def __init__(self):
        self.enabled = settings.enable_scheduled_crawls
        self.scheduler = None

    async def start(self):
        if not self.enabled:
            return
        # Stub: init AsyncIOScheduler and start
        pass

    async def stop(self):
        # Stub: shutdown scheduler
        pass

    def add_job(self, func, trigger, **kwargs):
        # Stub: add job to scheduler
        pass

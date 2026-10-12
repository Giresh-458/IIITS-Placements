class BaseSystemError(Exception):
    def __init__(self, message: str, source: str = None, url: str = None, stage: str = None, retry_count: int = 0):
        super().__init__(message)
        self.message = message
        self.source = source
        self.url = url
        self.stage = stage
        self.retry_count = retry_count

class SourceAccessError(BaseSystemError):
    pass

class CrawlTimeoutError(BaseSystemError):
    pass

class BrowserError(BaseSystemError):
    pass

class DocumentParseError(BaseSystemError):
    pass

class PDFProcessingError(BaseSystemError):
    pass

class ExtractionError(BaseSystemError):
    pass

class ValidationError(BaseSystemError):
    pass

class PersistenceError(BaseSystemError):
    pass

class ConfigurationError(BaseSystemError):
    pass

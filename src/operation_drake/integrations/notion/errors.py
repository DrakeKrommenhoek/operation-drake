class NotionAPIError(Exception):
    pass


class NotionAuthError(NotionAPIError):
    pass


class NotionRateLimitError(NotionAPIError):
    pass


class NotionTimeoutError(NotionAPIError):
    pass


class NotionNotFoundError(NotionAPIError):
    pass

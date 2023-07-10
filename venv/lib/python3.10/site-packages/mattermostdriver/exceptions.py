from aiohttp import ClientError


class InvalidOrMissingParameters(ClientError):
    """
    Raised when mattermost returns a
    400 Invalid or missing parameters in URL or request body
    """


class NoAccessTokenProvided(ClientError):
    """
    Raised when mattermost returns a
    401 No access token provided
    """


class NotEnoughPermissions(ClientError):
    """
    Raised when mattermost returns a
    403 Do not have appropriate permissions
    """


class ResourceNotFound(ClientError):
    """
    Raised when mattermost returns a
    404 Resource not found
    """


class ContentTooLarge(ClientError):
    """
    Raised when mattermost returns a
    413 Content too large
    """


class FeatureDisabled(ClientError):
    """
    Raised when mattermost returns a
    501 Feature is disabled
    """

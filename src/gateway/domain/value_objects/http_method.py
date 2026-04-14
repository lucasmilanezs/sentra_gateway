from enum import Enum


class HttpMethod(str, Enum):
    """
    Value object representing a valid HTTP method.

    Inherits from str so instances compare equal to plain strings
    and can be used directly in httpx/FastAPI without conversion.
    """

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"

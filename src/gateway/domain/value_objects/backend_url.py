from dataclasses import dataclass


@dataclass(frozen=True)
class BackendUrl:
    """
    Value object that encapsulates and validates a backend service URL.

    Responsible for constructing upstream request URLs by combining
    the registered base URL with the request's relative path.
    Keeping this logic here prevents string manipulation from leaking
    into use cases or other entities.
    """

    value: str

    def build_upstream(self, path: str) -> str:
        """
        Constructs the full upstream URL for a given relative path.

        Example:
            BackendUrl("https://httpbin.org").build_upstream("/get")
            → "https://httpbin.org/get"
        """
        clean_path = path.lstrip("/")
        base = self.value.rstrip("/")
        return f"{base}/{clean_path}" if clean_path else base

    def __str__(self) -> str:
        return self.value

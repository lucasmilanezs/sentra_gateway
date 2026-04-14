from dataclasses import dataclass


@dataclass(frozen=True)
class Param:
    """
    Represents a named URL path parameter captured during route matching.

    Example: route prefix "/users" applied to path "/users/42"
    does not produce named params in prefix-match mode, but structured
    routes such as "/users/{user_id}" would yield Param("user_id", "42").

    Kept as an explicit value object so downstream components (policy
    evaluators, audit builders) can reference params by name without
    parsing raw path strings.
    """

    name: str
    value: str

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass(frozen=True)
class PolicyEvaluationDetail:
    check: str
    passed: bool
    detail: Optional[str] = None


@dataclass(frozen=True)
class PolicyResult:
    allowed: bool
    status_code: int = 200
    reason: Optional[str] = None
    checks: Tuple[PolicyEvaluationDetail, ...] = field(default_factory=tuple)

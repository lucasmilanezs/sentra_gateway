from __future__ import annotations

from typing import Protocol

from src.gateway.domain.models.policy import Policy
from src.gateway.domain.models.policy_result import PolicyEvaluationDetail
from src.gateway.domain.models.request import Request


class PolicyComponent(Protocol):
    """Small domain contract for policy features that can be composed."""

    def is_enabled(self, policy: Policy) -> bool:
        ...

    def evaluate(self, policy: Policy, request: Request) -> PolicyEvaluationDetail:
        ...


class RequiredHeadersPolicy:
    def is_enabled(self, policy: Policy) -> bool:
        return bool(policy.required_headers)

    def evaluate(self, policy: Policy, request: Request) -> PolicyEvaluationDetail:
        missing = [header for header in policy.required_headers if not request.headers.contains(header)]
        if missing:
            return PolicyEvaluationDetail(
                check="required_headers",
                passed=False,
                detail=f"Headers obrigatórios ausentes: {', '.join(missing)}",
            )
        return PolicyEvaluationDetail(
            check="required_headers",
            passed=True,
            detail=f"Todos presentes: {', '.join(policy.required_headers)}",
        )


class ForbiddenHeadersPolicy:
    def is_enabled(self, policy: Policy) -> bool:
        return bool(policy.forbidden_headers)

    def evaluate(self, policy: Policy, request: Request) -> PolicyEvaluationDetail:
        blocked = [header for header in policy.forbidden_headers if request.headers.contains(header)]
        if blocked:
            return PolicyEvaluationDetail(
                check="forbidden_headers",
                passed=False,
                detail=f"Headers proibidos presentes: {', '.join(blocked)}",
            )
        return PolicyEvaluationDetail(
            check="forbidden_headers",
            passed=True,
            detail="Nenhum header proibido encontrado.",
        )


class RequiredParamsPolicy:
    def is_enabled(self, policy: Policy) -> bool:
        return bool(policy.required_params)

    def evaluate(self, policy: Policy, request: Request) -> PolicyEvaluationDetail:
        missing = [param for param in policy.required_params if not request.query_params.contains(param)]
        if missing:
            return PolicyEvaluationDetail(
                check="required_params",
                passed=False,
                detail=f"Query params obrigatórios ausentes: {', '.join(missing)}",
            )
        return PolicyEvaluationDetail(
            check="required_params",
            passed=True,
            detail=f"Todos presentes: {', '.join(policy.required_params)}",
        )


class ForbiddenParamsPolicy:
    def is_enabled(self, policy: Policy) -> bool:
        return bool(policy.forbidden_params)

    def evaluate(self, policy: Policy, request: Request) -> PolicyEvaluationDetail:
        blocked = [param for param in policy.forbidden_params if request.query_params.contains(param)]
        if blocked:
            return PolicyEvaluationDetail(
                check="forbidden_params",
                passed=False,
                detail=f"Query params proibidos presentes: {', '.join(blocked)}",
            )
        return PolicyEvaluationDetail(
            check="forbidden_params",
            passed=True,
            detail="Nenhum param proibido encontrado.",
        )


DEFAULT_POLICY_COMPONENTS: tuple[PolicyComponent, ...] = (
    RequiredHeadersPolicy(),
    ForbiddenHeadersPolicy(),
    RequiredParamsPolicy(),
    ForbiddenParamsPolicy(),
)

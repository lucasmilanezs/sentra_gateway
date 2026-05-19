from enum import Enum


class Permission(str, Enum):
    """
    Permissões funcionais granulares atribuídas a sub-usuários de um tenant.

    Roles estruturais (superuser, admin, member) controlam *quem* pode
    fazer o quê em termos de hierarquia. Permissions controlam *quais
    seções* um member pode acessar dentro do tenant.

    superuser e admin sempre têm acesso total — Permissions só se aplicam
    a usuários com role="member".
    """

    DOMAINS = "domains"
    ROUTES = "routes"
    AUDIT = "audit"
    METRICS = "metrics"

    @classmethod
    def from_list(cls, raw: list[str]) -> list["Permission"]:
        result = []
        for item in raw:
            try:
                result.append(cls(item.strip().lower()))
            except ValueError:
                pass  # ignora permissões inválidas silenciosamente
        return result

    @classmethod
    def serialize(cls, perms: list["Permission"]) -> str:
        return ",".join(p.value for p in perms)

    @classmethod
    def deserialize(cls, raw: str) -> list["Permission"]:
        if not raw:
            return []
        return cls.from_list(raw.split(","))
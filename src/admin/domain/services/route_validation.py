import re

from src.admin.domain.exceptions import ValidationError

_PATH_RE = re.compile(r"^/[a-z0-9][a-z0-9/_\-{}]*$")
_VERSION_HINT_RE = re.compile(r"^/v[0-9]+/")


def validate_path_pattern(path: str) -> str:
    path = path.strip()
    if not path.startswith("/"):
        raise ValidationError("path_pattern deve começar com /")
    if "//" in path:
        raise ValidationError("path_pattern não pode conter //")
    if " " in path:
        raise ValidationError("path_pattern não pode conter espaços")
    if path != path.lower():
        raise ValidationError("path_pattern deve usar apenas letras minúsculas (REST)")
    if not _PATH_RE.match(path):
        raise ValidationError(
            "path_pattern inválido: use letras minúsculas, números, /, -, _ ou parâmetros {id}"
        )
    return path


def path_pattern_warnings(path: str) -> list[str]:
    warnings: list[str] = []
    if path.endswith("/*"):
        warnings.append("wildcard /* aceita qualquer sufixo — evite em produção")
    if not _VERSION_HINT_RE.match(path):
        warnings.append("considere versionar o path, ex: /v1/recurso")
    return warnings

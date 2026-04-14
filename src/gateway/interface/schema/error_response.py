from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """
    Formato padrão de erro do gateway.
    Todo erro gerado pelo próprio gateway — não pelo upstream —
    usa esse schema para manter consistência.
    """
    code: str
    message: str
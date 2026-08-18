"""
Tratamento global de exceções da API.
"""

from fastapi import Request
from fastapi.responses import JSONResponse


class CodelabException(Exception):
    """Exceção base do CodeLab."""

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class NotFoundError(CodelabException):
    def __init__(self, recurso: str = "Recurso"):
        super().__init__(f"{recurso} não encontrado(a)", status_code=404)


class ValidationError(CodelabException):
    def __init__(self, detail: str):
        super().__init__(detail, status_code=422)


async def codelab_exception_handler(request: Request, exc: CodelabException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"erro": exc.detail},
    )

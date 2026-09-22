"""Respostas de erro públicas, sem valores de entrada ou detalhes internos."""

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class CodelabException(Exception):
    """Erro de domínio esperado; detalhe deve ser seguro para exposição pública."""

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


def _erro(message: str, status_code: int, **extra: object) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"erro": message, **extra})


async def codelab_exception_handler(request: Request, exc: CodelabException) -> JSONResponse:
    if exc.status_code >= 500:
        return _erro("Erro interno do servidor.", 500)
    return _erro(exc.detail, exc.status_code)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Não serializar exc.errors(): pode incluir input, URLs, senhas e dados ocultos.
    fields: list[str] = []
    for error in exc.errors():
        location = error.get("loc", ())
        field = ".".join(str(segment) for segment in location if isinstance(segment, (str, int)))
        if field and field not in fields and len(fields) < 20:
            fields.append(field)
    return _erro("Dados inválidos.", 422, campos=fields)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code >= 500:
        message = "Erro interno do servidor."
    elif exc.status_code == 404:
        message = "Recurso não encontrado."
    elif isinstance(exc.detail, str):
        message = exc.detail
    else:
        message = "Requisição não pôde ser concluída."
    response = _erro(message, exc.status_code)
    for header, value in (exc.headers or {}).items():
        response.headers[header] = value
    return response


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Não imprimir traceback ou repr(exc): pode conter segredos ou código submetido.
    return _erro("Erro interno do servidor.", 500)

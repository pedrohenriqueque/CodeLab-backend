from fastapi import APIRouter, Depends, Request

from ..core.exceptions import CodelabException
from ..dependencies.authentication import get_current_user
from ..integrations.judge0 import Judge0Client, Judge0TechnicalFailure
from ..models.usuario import Usuario
from ..schemas.sandbox import ExecutarSandboxRequest, ExecutarSandboxResponse
from ..services.sandbox_service import executar_playground

router = APIRouter(prefix="/sandbox", tags=["Playground"])


@router.post("", response_model=ExecutarSandboxResponse)
async def execute_sandbox(
    dados: ExecutarSandboxRequest,
    request: Request,
    _: Usuario = Depends(get_current_user),
) -> ExecutarSandboxResponse:
    try:
        resultado = await executar_playground(
            dados.codigo,
            Judge0Client(request.app.state.settings),
        )
    except Judge0TechnicalFailure:
        raise CodelabException("O playground está indisponível no momento.", 503) from None
    return ExecutarSandboxResponse(**resultado)

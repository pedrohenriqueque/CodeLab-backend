from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any
import logging

from app.services.judge0_client import judge0_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sandbox", tags=["Sandbox"])

class SandboxRequest(BaseModel):
    codigo: str

@router.post("")
async def executar_sandbox(body: SandboxRequest) -> dict[str, Any]:
    """
    Executa código livre no Judge0 sem validação estrutural.
    Utilizado no ambiente Sandbox / Playground do aluno.
    """
    try:
        resultado = await judge0_client.executar_codigo(body.codigo)
        return {
            "stdout": resultado.get("stdout", ""),
            "stderr": resultado.get("stderr", ""),
            "compile_output": resultado.get("compile_output", ""),
            "status": resultado.get("status", {}).get("description", "Unknown"),
            "time": resultado.get("time"),
            "memory": resultado.get("memory")
        }
    except Exception as e:
        logger.error("Erro na execucao sandbox: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

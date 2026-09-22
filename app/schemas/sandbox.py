from pydantic import Field

from ..core.schemas import ApiSchema


class ExecutarSandboxRequest(ApiSchema):
    codigo: str = Field(min_length=1, max_length=100_000)


class ExecutarSandboxResponse(ApiSchema):
    stdout: str
    stderr: str
    compile_output: str
    status: str
    time: str | None = None
    memory: int | None = None

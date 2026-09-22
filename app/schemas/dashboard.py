from datetime import datetime
from decimal import Decimal
from uuid import UUID

from ..core.schemas import ApiSchema


class DashboardAtividade(ApiSchema):
    uuid: UUID
    titulo: str
    tipo: str
    situacao: str
    fim_em: datetime
    total_funcoes: int
    funcoes_enviadas: int = 0
    alunos_iniciaram: int = 0
    alunos_enviaram_todas: int = 0


class DashboardTentativa(ApiSchema):
    uuid: UUID
    atividade_uuid: UUID
    atividade_titulo: str
    funcao_uuid: UUID
    funcao_nome: str
    aluno_nome: str | None = None
    recebida_em: datetime
    status: str
    nota: Decimal | None = None
    nota_maxima: Decimal | None = None


class DashboardResponse(ApiSchema):
    turma_uuid: UUID
    turma_nome: str
    codigo: str | None = None
    total_alunos: int | None = None
    atividades_abertas: int
    atividades_iniciadas: int
    funcoes_enviadas: int
    atividades: list[DashboardAtividade]
    recentes: list[DashboardTentativa]

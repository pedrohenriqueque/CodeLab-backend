"""
Exporta todos os modelos para facilitar imports.

Uso: from app.db.models import Funcao, CasoTeste, Submissao, AtividadeFuncao, EntregaAtividade
"""

from app.db.models.usuario import Usuario
from app.db.models.atividade import Atividade
from app.db.models.funcao import Funcao
from app.db.models.caso_teste import CasoTeste
from app.db.models.submissao import Submissao
from app.db.models.atividade_funcao import AtividadeFuncao, AtividadeFuncaoCasoTeste
from app.db.models.entrega_atividade import EntregaAtividade

__all__ = [
    "Usuario",
    "Atividade",
    "Funcao",
    "CasoTeste",
    "Submissao",
    "AtividadeFuncao",
    "AtividadeFuncaoCasoTeste",
    "EntregaAtividade",
]

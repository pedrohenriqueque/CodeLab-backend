"""
Exporta todos os modelos para facilitar imports.

Uso: from app.db.models import Funcao, CasoTeste, Submissao
"""

from app.db.models.usuario import Usuario
from app.db.models.atividade import Atividade
from app.db.models.funcao import Funcao
from app.db.models.caso_teste import CasoTeste
from app.db.models.submissao import Submissao

__all__ = ["Usuario", "Atividade", "Funcao", "CasoTeste", "Submissao"]


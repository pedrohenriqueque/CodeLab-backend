"""Registro dos modelos ORM para Alembic.

Quando uma entidade for criada, importe-a aqui para incluí-la em Base.metadata.
"""

from .base import Base
from .usuario import PerfilUsuario, Usuario
from .turma import MatriculaTurma, Turma
from .funcao import FuncaoBiblioteca
from .caso_teste import CasoTeste
from .atividade import Atividade
from .funcao_atividade import CasoTesteAtividade, FuncaoAtividade
from .tentativa import ResultadoCasoTentativa, Tentativa

__all__ = ["Base", "PerfilUsuario", "Usuario", "Turma", "MatriculaTurma", "FuncaoBiblioteca", "CasoTeste", "Atividade", "FuncaoAtividade", "CasoTesteAtividade", "Tentativa", "ResultadoCasoTentativa"]

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import CodelabException, NotFoundError
from ..models.caso_teste import CasoTeste
from ..models.funcao import FuncaoBiblioteca
from ..models.usuario import PerfilUsuario, Usuario
from ..repositories.function_repository import FunctionRepository
from ..repositories.test_case_repository import TestCaseRepository
from ..schemas.caso_teste import AtualizarCasoTesteRequest, CriarCasoTesteRequest


def _matches_type(value: Any, type_name: str) -> bool:
    is_vector = type_name.endswith("[]")
    base = type_name[:-2] if is_vector else type_name
    if is_vector:
        return isinstance(value, list) and all(_matches_type(item, base) for item in value)
    if base in {"int", "long"}:
        return isinstance(value, int) and not isinstance(value, bool)
    if base in {"float", "double"}:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if base == "bool": return isinstance(value, bool)
    if base == "char": return isinstance(value, str) and len(value) == 1
    if base == "string": return isinstance(value, str)
    return False


def _validate_values(funcao: FuncaoBiblioteca, entradas: list[Any], retorno: Any) -> None:
    parametros = funcao.parametros
    if len(entradas) != len(parametros):
        raise CodelabException("A quantidade de entradas não corresponde à assinatura.", 422)
    for value, parameter in zip(entradas, parametros, strict=True):
        if not _matches_type(value, parameter["tipo"]):
            raise CodelabException("Entrada incompatível com a assinatura.", 422)
    if not _matches_type(retorno, funcao.tipo_retorno):
        raise CodelabException("Retorno esperado incompatível com a assinatura.", 422)


async def _owned_function(function_id: UUID, professor: Usuario, db: AsyncSession) -> FuncaoBiblioteca:
    if professor.perfil != PerfilUsuario.PROFESSOR:
        raise CodelabException("Operação não permitida para este perfil.", 403)
    funcao = await FunctionRepository(db).get_by_uuid(function_id)
    if funcao is None: raise NotFoundError("Função")
    if funcao.professor_uuid != professor.uuid:
        raise CodelabException("Você não é proprietário desta função.", 403)
    return funcao


async def _viewable_function(function_id: UUID, professor: Usuario, db: AsyncSession) -> FuncaoBiblioteca:
    if professor.perfil != PerfilUsuario.PROFESSOR:
        raise CodelabException("Operação não permitida para este perfil.", 403)
    funcao = await FunctionRepository(db).get_by_uuid(function_id)
    if funcao is None or (funcao.professor_uuid != professor.uuid and not funcao.compartilhada):
        raise NotFoundError("Função")
    return funcao


async def criar_caso(function_id: UUID, dados: CriarCasoTesteRequest, professor: Usuario, db: AsyncSession) -> CasoTeste:
    funcao = await _owned_function(function_id, professor, db)
    _validate_values(funcao, dados.entradas, dados.retorno_esperado)
    caso = CasoTeste(funcao_uuid=funcao.uuid, entradas=dados.entradas, retorno_esperado=dados.retorno_esperado, visibilidade=dados.visibilidade, descricao=dados.descricao.strip())
    await TestCaseRepository(db).add(caso)
    await db.commit(); await db.refresh(caso)
    return caso


async def listar_casos(function_id: UUID, professor: Usuario, db: AsyncSession) -> list[CasoTeste]:
    await _viewable_function(function_id, professor, db)
    return await TestCaseRepository(db).list_by_function(function_id)


async def atualizar_caso(case_id: UUID, dados: AtualizarCasoTesteRequest, professor: Usuario, db: AsyncSession) -> CasoTeste:
    caso = await TestCaseRepository(db).get_by_uuid(case_id)
    if caso is None: raise NotFoundError("Caso de teste")
    funcao = await _owned_function(caso.funcao_uuid, professor, db)
    entradas = dados.entradas if dados.entradas is not None else caso.entradas
    retorno = dados.retorno_esperado if dados.retorno_esperado is not None else caso.retorno_esperado
    _validate_values(funcao, entradas, retorno)
    if dados.entradas is not None: caso.entradas = dados.entradas
    if dados.retorno_esperado is not None: caso.retorno_esperado = dados.retorno_esperado
    if dados.visibilidade is not None: caso.visibilidade = dados.visibilidade
    if dados.descricao is not None: caso.descricao = dados.descricao.strip()
    await db.commit(); await db.refresh(caso)
    return caso


async def remover_caso(case_id: UUID, professor: Usuario, db: AsyncSession) -> None:
    caso = await TestCaseRepository(db).get_by_uuid(case_id)
    if caso is None: raise NotFoundError("Caso de teste")
    await _owned_function(caso.funcao_uuid, professor, db)
    await TestCaseRepository(db).delete(caso)
    await db.commit()

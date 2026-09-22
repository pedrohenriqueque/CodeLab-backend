from copy import deepcopy
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import CodelabException, NotFoundError
from ..models.funcao import FuncaoBiblioteca
from ..models.caso_teste import CasoTeste
from ..models.usuario import PerfilUsuario, Usuario
from ..repositories.function_repository import FunctionRepository
from ..repositories.test_case_repository import TestCaseRepository
from ..schemas.funcao import AtualizarFuncaoRequest, CriarFuncaoRequest, ParametroFuncao


def _require_professor(usuario: Usuario) -> None:
    if usuario.perfil != PerfilUsuario.PROFESSOR:
        raise CodelabException("Operação não permitida para este perfil.", status_code=403)


def _normalized_parameters(parametros: list[ParametroFuncao]) -> list[dict[str, str]]:
    return [{"nome": item.nome.strip(), "tipo": item.tipo.strip().lower()} for item in parametros]


async def criar_funcao(dados: CriarFuncaoRequest, professor: Usuario, db: AsyncSession) -> FuncaoBiblioteca:
    _require_professor(professor)
    funcao = FuncaoBiblioteca(
        professor_uuid=professor.uuid,
        nome=dados.nome.strip(),
        enunciado=dados.enunciado.strip(),
        tipo_retorno=dados.tipo_retorno.strip().lower(),
        parametros=_normalized_parameters(dados.parametros),
        dificuldade=dados.dificuldade.strip().upper(),
        compartilhada=True,
    )
    await FunctionRepository(db).add(funcao)
    await db.commit()
    await db.refresh(funcao)
    return funcao


async def listar_funcoes(professor: Usuario, db: AsyncSession) -> list[tuple[FuncaoBiblioteca, int]]:
    _require_professor(professor)
    funcoes = await FunctionRepository(db).list_visible_to(professor.uuid)
    contagens = await TestCaseRepository(db).count_by_function_ids([funcao.uuid for funcao in funcoes])
    return [(funcao, contagens.get(funcao.uuid, 0)) for funcao in funcoes]


async def obter_funcao(function_id: UUID, professor: Usuario, db: AsyncSession) -> FuncaoBiblioteca:
    _require_professor(professor)
    funcao = await FunctionRepository(db).get_by_uuid(function_id)
    if funcao is None or (funcao.professor_uuid != professor.uuid and not funcao.compartilhada):
        raise NotFoundError("Função")
    return funcao


async def atualizar_funcao(function_id: UUID, dados: AtualizarFuncaoRequest, professor: Usuario, db: AsyncSession) -> FuncaoBiblioteca:
    funcao = await obter_funcao(function_id, professor, db)
    if funcao.professor_uuid != professor.uuid:
        raise CodelabException("Você não é proprietário desta função.", status_code=403)
    if dados.nome is not None:
        funcao.nome = dados.nome.strip()
    if dados.enunciado is not None:
        funcao.enunciado = dados.enunciado.strip()
    if dados.tipo_retorno is not None:
        funcao.tipo_retorno = dados.tipo_retorno.strip().lower()
    if dados.parametros is not None:
        funcao.parametros = _normalized_parameters(dados.parametros)
    if dados.dificuldade is not None:
        funcao.dificuldade = dados.dificuldade.strip().upper()
    if dados.compartilhada is not None:
        funcao.compartilhada = dados.compartilhada
    await db.commit()
    await db.refresh(funcao)
    return funcao


async def remover_funcao(function_id: UUID, professor: Usuario, db: AsyncSession) -> None:
    funcao = await obter_funcao(function_id, professor, db)
    if funcao.professor_uuid != professor.uuid:
        raise CodelabException("Você não é proprietário desta função.", status_code=403)
    await FunctionRepository(db).delete(funcao)
    await db.commit()


async def duplicar_funcao(
    function_id: UUID, professor: Usuario, db: AsyncSession
) -> FuncaoBiblioteca:
    """Copia uma função compartilhada e seus casos em uma única transação."""
    _require_professor(professor)
    origem = await FunctionRepository(db).get_by_uuid(function_id)
    if origem is None or not origem.compartilhada:
        raise NotFoundError("Função")
    if origem.professor_uuid == professor.uuid:
        raise CodelabException("Não é necessário duplicar a própria função.", 409)

    casos_origem = await TestCaseRepository(db).list_by_function(origem.uuid)
    copia = FuncaoBiblioteca(
        professor_uuid=professor.uuid,
        nome=f"Cópia de {origem.nome}",
        enunciado=origem.enunciado,
        tipo_retorno=origem.tipo_retorno,
        parametros=deepcopy(origem.parametros),
        dificuldade=origem.dificuldade,
        compartilhada=False,
    )
    repository = FunctionRepository(db)
    await repository.add(copia)
    try:
        await db.flush()
        cases = TestCaseRepository(db)
        for caso_origem in casos_origem:
            await cases.add(CasoTeste(
                funcao_uuid=copia.uuid,
                entradas=deepcopy(caso_origem.entradas),
                retorno_esperado=deepcopy(caso_origem.retorno_esperado),
                visibilidade=caso_origem.visibilidade,
            ))
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(copia)
    return copia

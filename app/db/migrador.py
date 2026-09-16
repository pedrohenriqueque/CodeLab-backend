"""
Módulo de migrações e inicialização de schema do CodeLab.

Garante a criação das novas tabelas (atividades_funcoes, atividades_funcoes_casos_teste, entregas_atividades)
e realiza a migração de esquema e dados das tabelas existentes preservando os dados.
"""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from app.db.session import engine, Base
import app.db.models  # Garante registro de todos os modelos no Base.metadata

logger = logging.getLogger(__name__)


async def run_migrations(conn: AsyncConnection):
    """Executa verificações e alterações DDL/DML preservando dados."""
    logger.info("Verificando e aplicando migrações de schema...")

    # 1. Obter tabelas existentes
    res = await conn.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    )
    tables = {r[0] for r in res.fetchall()}

    # 2. Criar tabelas que ainda não existem usando metadata
    await conn.run_sync(Base.metadata.create_all)

    # 3. Migrar tabela `funcoes` se atividade_uuid ainda existir
    if "funcoes" in tables:
        res_cols = await conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'funcoes'")
        )
        funcoes_cols = {r[0] for r in res_cols.fetchall()}

        # Adicionar dificuldade_padrao se não existir
        if "dificuldade_padrao" not in funcoes_cols:
            logger.info("Adicionando coluna 'dificuldade_padrao' em funcoes...")
            # Usa o tipo enum dificuldade_funcao existente ou varchar
            await conn.execute(
                text("ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS dificuldade_padrao dificuldade_funcao DEFAULT 'medio'")
            )
            # Se havia coluna 'dificuldade', copiar seus valores
            if "dificuldade" in funcoes_cols:
                await conn.execute(
                    text("UPDATE funcoes SET dificuldade_padrao = dificuldade WHERE dificuldade IS NOT NULL")
                )

        # Se atividade_uuid existir em funcoes, migrar os dados para atividades_funcoes antes de tornar nullable/dropar
        if "atividade_uuid" in funcoes_cols:
            logger.info("Migrando associações existentes de funcoes.atividade_uuid para atividades_funcoes...")
            # Inserir associações caso ainda não existam em atividades_funcoes
            await conn.execute(
                text("""
                INSERT INTO atividades_funcoes (uuid, atividade_uuid, funcao_uuid, dificuldade, peso, ordem, created_at)
                SELECT 
                    gen_random_uuid()::text,
                    f.atividade_uuid,
                    f.uuid,
                    COALESCE(f.dificuldade, 'medio'),
                    COALESCE(f.pontos, 10.0),
                    COALESCE(f.ordem, 0),
                    f.created_at
                FROM funcoes f
                WHERE f.atividade_uuid IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM atividades_funcoes af 
                      WHERE af.atividade_uuid = f.atividade_uuid AND af.funcao_uuid = f.uuid
                  )
                """)
            )

            # Para cada atividade_funcao recém-migrada, configurar os casos de teste existentes
            logger.info("Configurando casos de teste para as associações migradas...")
            await conn.execute(
                text("""
                INSERT INTO atividades_funcoes_casos_teste (uuid, atividade_funcao_uuid, caso_teste_uuid, oculto, created_at)
                SELECT 
                    gen_random_uuid()::text,
                    af.uuid,
                    ct.uuid,
                    FALSE,
                    NOW()
                FROM atividades_funcoes af
                JOIN casos_teste ct ON ct.funcao_uuid = af.funcao_uuid
                WHERE NOT EXISTS (
                    SELECT 1 FROM atividades_funcoes_casos_teste afct
                    WHERE afct.atividade_funcao_uuid = af.uuid AND afct.caso_teste_uuid = ct.uuid
                )
                """)
            )

            # Remover constraint NOT NULL de atividade_uuid, pontos e ordem se ainda existirem
            await conn.execute(text("ALTER TABLE funcoes ALTER COLUMN atividade_uuid DROP NOT NULL"))
            if "pontos" in funcoes_cols:
                await conn.execute(text("ALTER TABLE funcoes ALTER COLUMN pontos DROP NOT NULL"))
            if "ordem" in funcoes_cols:
                await conn.execute(text("ALTER TABLE funcoes ALTER COLUMN ordem DROP NOT NULL"))

    # 4. Migrar tabela `submissoes` para ter atividade_uuid
    if "submissoes" in tables:
        res_subs = await conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'submissoes'")
        )
        subs_cols = {r[0] for r in res_subs.fetchall()}

        if "atividade_uuid" not in subs_cols:
            logger.info("Adicionando coluna 'atividade_uuid' em submissoes...")
            await conn.execute(
                text("ALTER TABLE submissoes ADD COLUMN atividade_uuid character varying(36)")
            )
            # Popular atividade_uuid com base nas associações existentes
            logger.info("Populando submissoes.atividade_uuid a partir de atividades_funcoes...")
            await conn.execute(
                text("""
                UPDATE submissoes s
                SET atividade_uuid = af.atividade_uuid
                FROM atividades_funcoes af
                WHERE s.funcao_uuid = af.funcao_uuid
                  AND s.atividade_uuid IS NULL
                """)
            )
            # Adicionar Foreign Key
            await conn.execute(
                text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'fk_submissoes_atividade'
                    ) THEN
                        ALTER TABLE submissoes
                        ADD CONSTRAINT fk_submissoes_atividade
                        FOREIGN KEY (atividade_uuid) REFERENCES atividades(uuid) ON DELETE CASCADE;
                    END IF;
                END $$;
                """)
            )

    logger.info("Migrações de schema concluídas com sucesso!")

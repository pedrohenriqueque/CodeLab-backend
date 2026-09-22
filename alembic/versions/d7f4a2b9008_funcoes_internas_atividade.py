"""criar snapshots de funcoes e casos de atividade

Revision ID: d7f4a2b9008
Revises: c6e3a1f3007
"""

from alembic import op
import sqlalchemy as sa


revision = "d7f4a2b9008"
down_revision = "c6e3a1f3007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "funcoes_atividade",
        sa.Column("uuid", sa.UUID(), nullable=False),
        sa.Column("atividade_uuid", sa.UUID(), nullable=False),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("enunciado", sa.Text(), nullable=False),
        sa.Column("tipo_retorno", sa.String(length=32), nullable=False),
        sa.Column("parametros", sa.JSON(), nullable=False),
        sa.Column("dificuldade", sa.String(length=16), nullable=False),
        sa.Column("nota_maxima", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["atividade_uuid"], ["atividades.uuid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("uuid"),
        sa.UniqueConstraint("atividade_uuid", "ordem", name="uq_funcoes_atividade_ordem"),
    )
    op.create_table(
        "casos_teste_atividade",
        sa.Column("uuid", sa.UUID(), nullable=False),
        sa.Column("funcao_atividade_uuid", sa.UUID(), nullable=False),
        sa.Column("entradas", sa.JSON(), nullable=False),
        sa.Column("retorno_esperado", sa.JSON(), nullable=False),
        sa.Column("visibilidade", sa.String(length=16), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["funcao_atividade_uuid"], ["funcoes_atividade.uuid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("uuid"),
    )


def downgrade() -> None:
    op.drop_table("casos_teste_atividade")
    op.drop_table("funcoes_atividade")

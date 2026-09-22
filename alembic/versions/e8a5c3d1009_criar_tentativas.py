"""criar tentativas individuais

Revision ID: e8a5c3d1009
Revises: d7f4a2b9008
"""

from alembic import op
import sqlalchemy as sa


revision = "e8a5c3d1009"
down_revision = "d7f4a2b9008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tentativas",
        sa.Column("uuid", sa.UUID(), nullable=False),
        sa.Column("funcao_atividade_uuid", sa.UUID(), nullable=False),
        sa.Column("aluno_uuid", sa.UUID(), nullable=False),
        sa.Column("codigo_fonte", sa.Text(), nullable=False),
        sa.Column("recebida_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("avaliada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_casos", sa.Integer(), nullable=False),
        sa.Column("casos_aprovados", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["funcao_atividade_uuid"], ["funcoes_atividade.uuid"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["aluno_uuid"], ["usuarios.uuid"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("uuid"),
    )


def downgrade() -> None:
    op.drop_table("tentativas")

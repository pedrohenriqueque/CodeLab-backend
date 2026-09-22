"""adicionar tipo de atividade e resultados por caso

Revision ID: a1c7e5f3011
Revises: f9b6d4e2010
"""
from alembic import op
import sqlalchemy as sa

revision = "a1c7e5f3011"
down_revision = "f9b6d4e2010"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("atividades", sa.Column("tipo", sa.String(length=16), nullable=False, server_default="EXERCICIO"))
    op.create_table("resultados_casos_tentativa", sa.Column("uuid", sa.UUID(), nullable=False), sa.Column("tentativa_uuid", sa.UUID(), nullable=False), sa.Column("caso_teste_atividade_uuid", sa.UUID(), nullable=False), sa.Column("aprovado", sa.Boolean(), nullable=False), sa.ForeignKeyConstraint(["tentativa_uuid"], ["tentativas.uuid"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["caso_teste_atividade_uuid"], ["casos_teste_atividade.uuid"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("uuid"))

def downgrade() -> None:
    op.drop_table("resultados_casos_tentativa")
    op.drop_column("atividades", "tipo")

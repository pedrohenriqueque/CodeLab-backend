"""adicionar regras de submissao da atividade

Revision ID: b2d8f6a4012
Revises: a1c7e5f3011
"""
from alembic import op
import sqlalchemy as sa

revision = "b2d8f6a4012"
down_revision = "a1c7e5f3011"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("atividades", sa.Column("permitir_multiplas_submissoes", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("atividades", sa.Column("max_tentativas_por_funcao", sa.Integer(), nullable=True))
    op.add_column("atividades", sa.Column("mostrar_ocultos_apos_fechamento", sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade() -> None:
    op.drop_column("atividades", "mostrar_ocultos_apos_fechamento")
    op.drop_column("atividades", "max_tentativas_por_funcao")
    op.drop_column("atividades", "permitir_multiplas_submissoes")

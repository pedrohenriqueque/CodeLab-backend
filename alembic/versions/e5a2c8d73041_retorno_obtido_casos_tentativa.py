"""Preserva o retorno obtido em cada caso de uma tentativa.

Revision ID: e5a2c8d73041
Revises: d4f1b7c92031
"""
from alembic import op
import sqlalchemy as sa


revision = "e5a2c8d73041"
down_revision = "d4f1b7c92031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("resultados_casos_tentativa", sa.Column("retorno_obtido", sa.JSON(), nullable=True))
    op.add_column("resultados_casos_tentativa", sa.Column(
        "status_retorno", sa.String(32), nullable=False, server_default="NAO_INFORMADO",
    ))
    op.alter_column("resultados_casos_tentativa", "status_retorno", server_default=None)


def downgrade() -> None:
    op.drop_column("resultados_casos_tentativa", "status_retorno")
    op.drop_column("resultados_casos_tentativa", "retorno_obtido")

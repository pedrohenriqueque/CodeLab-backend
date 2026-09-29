"""adiciona peso relativo a cada caso de teste

Revision ID: d4f1b7c92031
Revises: c3e9a7d51201
"""
from alembic import op
import sqlalchemy as sa


revision = "d4f1b7c92031"
down_revision = "c3e9a7d51201"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("casos_teste", "casos_teste_atividade"):
        op.add_column(
            table,
            sa.Column(
                "peso",
                sa.Numeric(precision=8, scale=2),
                nullable=False,
                server_default=sa.text("1.00"),
            ),
        )
        op.alter_column(table, "peso", server_default=None)


def downgrade() -> None:
    op.drop_column("casos_teste_atividade", "peso")
    op.drop_column("casos_teste", "peso")

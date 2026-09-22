"""permitir professor sem matricula e adicionar soft delete

Revision ID: c3e9a7d51201
Revises: b2d8f6a4012
"""

from alembic import op
import sqlalchemy as sa


revision = "c3e9a7d51201"
down_revision = "b2d8f6a4012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("usuarios", "matricula", existing_type=sa.String(length=50), nullable=True)
    op.add_column(
        "usuarios",
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("usuarios", "ativo", server_default=None)


def downgrade() -> None:
    op.drop_column("usuarios", "ativo")
    op.alter_column("usuarios", "matricula", existing_type=sa.String(length=50), nullable=False)

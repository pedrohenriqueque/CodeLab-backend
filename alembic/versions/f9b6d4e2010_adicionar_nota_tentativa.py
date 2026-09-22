"""adicionar nota proporcional em tentativas

Revision ID: f9b6d4e2010
Revises: e8a5c3d1009
"""

from alembic import op
import sqlalchemy as sa


revision = "f9b6d4e2010"
down_revision = "e8a5c3d1009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tentativas", sa.Column("nota", sa.Numeric(precision=5, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column("tentativas", "nota")

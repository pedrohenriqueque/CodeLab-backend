"""criar funcoes biblioteca

Revision ID: 9f78b3d1c004
Revises: 5c4c7736a002
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "9f78b3d1c004"
down_revision: Union[str, None] = "5c4c7736a002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "funcoes_biblioteca",
        sa.Column("uuid", sa.UUID(), nullable=False),
        sa.Column("professor_uuid", sa.UUID(), nullable=False),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("enunciado", sa.Text(), nullable=False),
        sa.Column("tipo_retorno", sa.String(length=32), nullable=False),
        sa.Column("parametros", sa.JSON(), nullable=False),
        sa.Column("dificuldade", sa.String(length=16), nullable=False),
        sa.Column("compartilhada", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["professor_uuid"], ["usuarios.uuid"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("uuid"),
    )


def downgrade() -> None:
    op.drop_table("funcoes_biblioteca")

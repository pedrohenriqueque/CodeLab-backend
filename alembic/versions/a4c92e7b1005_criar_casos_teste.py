"""criar casos teste

Revision ID: a4c92e7b1005
Revises: 9f78b3d1c004
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "a4c92e7b1005"
down_revision: Union[str, None] = "9f78b3d1c004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table("casos_teste", sa.Column("uuid", sa.UUID(), nullable=False), sa.Column("funcao_uuid", sa.UUID(), nullable=False), sa.Column("entradas", sa.JSON(), nullable=False), sa.Column("retorno_esperado", sa.JSON(), nullable=False), sa.Column("visibilidade", sa.String(length=16), nullable=False), sa.ForeignKeyConstraint(["funcao_uuid"], ["funcoes_biblioteca.uuid"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("uuid"))

def downgrade() -> None:
    op.drop_table("casos_teste")

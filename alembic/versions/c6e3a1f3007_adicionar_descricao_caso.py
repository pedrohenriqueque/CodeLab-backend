"""adicionar descricao caso

Revision ID: c6e3a1f3007
Revises: b5d8e1f2006
"""
from alembic import op
import sqlalchemy as sa
revision="c6e3a1f3007"; down_revision="b5d8e1f2006"; branch_labels=None; depends_on=None
def upgrade(): op.add_column("casos_teste", sa.Column("descricao", sa.Text(), nullable=False, server_default=""))
def downgrade(): op.drop_column("casos_teste", "descricao")

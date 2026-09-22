"""criar atividades

Revision ID: b5d8e1f2006
Revises: a4c92e7b1005
"""
from alembic import op
import sqlalchemy as sa
revision="b5d8e1f2006"; down_revision="a4c92e7b1005"; branch_labels=None; depends_on=None
def upgrade():
 op.create_table("atividades",sa.Column("uuid",sa.UUID(),nullable=False),sa.Column("turma_uuid",sa.UUID(),nullable=False),sa.Column("titulo",sa.String(length=200),nullable=False),sa.Column("descricao",sa.Text(),nullable=False),sa.Column("inicio_em",sa.DateTime(timezone=True),nullable=False),sa.Column("fim_em",sa.DateTime(timezone=True),nullable=False),sa.Column("status",sa.String(length=16),nullable=False),sa.ForeignKeyConstraint(["turma_uuid"],["turmas.uuid"],ondelete="RESTRICT"),sa.PrimaryKeyConstraint("uuid"))
def downgrade(): op.drop_table("atividades")

"""criar turmas e matriculas

Revision ID: 5c4c7736a002
Revises: ec12613fbb7f
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5c4c7736a002"
down_revision: Union[str, None] = "ec12613fbb7f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "turmas",
        sa.Column("uuid", sa.UUID(), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("codigo", sa.String(length=16), nullable=False),
        sa.Column("ativa", sa.Boolean(), nullable=False),
        sa.Column("professor_uuid", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["professor_uuid"], ["usuarios.uuid"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("uuid"),
        sa.UniqueConstraint("codigo"),
    )
    op.create_table(
        "matriculas_turma",
        sa.Column("uuid", sa.UUID(), nullable=False),
        sa.Column("turma_uuid", sa.UUID(), nullable=False),
        sa.Column("aluno_uuid", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["turma_uuid"], ["turmas.uuid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["aluno_uuid"], ["usuarios.uuid"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("uuid"),
        sa.UniqueConstraint("turma_uuid", "aluno_uuid", name="uq_matriculas_turma_aluno"),
    )


def downgrade() -> None:
    op.drop_table("matriculas_turma")
    op.drop_table("turmas")

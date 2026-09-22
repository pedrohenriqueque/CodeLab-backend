"""Base compartilhada de metadados ORM; nenhuma tabela é criada no import."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Entidades de domínio serão adicionadas somente nas respectivas tasks."""

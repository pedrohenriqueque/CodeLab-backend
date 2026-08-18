"""
Utilitários compartilhados para schemas Pydantic.
"""

from pydantic import ConfigDict
from pydantic.alias_generators import to_camel


# ConfigDict padrão para todos os schemas do projeto:
# - camelCase nos JSON de entrada/saída
# - snake_case internamente no Python
# - populate_by_name=True permite usar ambos os formatos
CAMEL_CONFIG = ConfigDict(
    alias_generator=to_camel,
    populate_by_name=True,
    from_attributes=True,
)

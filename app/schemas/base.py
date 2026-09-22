"""Convenção JSON da API: snake_case interno, camelCase externo."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiSchema(BaseModel):
    """Base para futuros DTOs de entrada e saída da API."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )

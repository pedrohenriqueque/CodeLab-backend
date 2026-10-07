"""Geração controlada do programa C usado na avaliação automática."""

from dataclasses import dataclass
import json
import secrets
from typing import Any


class UnsupportedCSignatureError(ValueError):
    """Assinatura fora do subconjunto de C aprovado para avaliação."""


@dataclass(frozen=True)
class GeneratedCProgram:
    source_code: str
    total_cases: int
    result_marker: str


_C_TYPES = {
    "int": "int", "long": "long", "float": "float", "double": "double",
    "char": "char", "bool": "bool", "string": "const char *",
}
_FLOAT_TYPES = {"float", "double"}
MAX_CAPTURED_STRING_BYTES = 4096


def _c_type(type_name: str, *, parameter: bool = False) -> str:
    normalized = type_name.strip().lower()
    if normalized.endswith("[]"):
        if not parameter:
            raise UnsupportedCSignatureError("Retorno em vetor não é suportado.")
        base = normalized[:-2]
        if base not in _C_TYPES or base == "string":
            raise UnsupportedCSignatureError("Tipo de vetor não suportado.")
        return _C_TYPES[base]
    if normalized not in _C_TYPES:
        raise UnsupportedCSignatureError("Tipo de C não suportado.")
    return _C_TYPES[normalized]


def _literal(value: Any, type_name: str) -> str:
    normalized = type_name.strip().lower()
    if normalized.endswith("[]"):
        if not isinstance(value, list):
            raise UnsupportedCSignatureError("Valor de vetor inválido.")
        base = normalized[:-2]
        return f"({_c_type(base)}[]){{{', '.join(_literal(item, base) for item in value)}}}"
    if normalized == "bool":
        if not isinstance(value, bool):
            raise UnsupportedCSignatureError("Valor booleano inválido.")
        return "true" if value else "false"
    if normalized in {"int", "long"}:
        if not isinstance(value, int) or isinstance(value, bool):
            raise UnsupportedCSignatureError("Valor inteiro inválido.")
        return str(value)
    if normalized in _FLOAT_TYPES:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise UnsupportedCSignatureError("Valor decimal inválido.")
        return repr(float(value))
    if normalized == "char":
        if not isinstance(value, str) or len(value) != 1:
            raise UnsupportedCSignatureError("Valor char inválido.")
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        if ord(value) < 32 or ord(value) == 127:
            escaped = f"\\x{ord(value):02x}"
        return "'" + escaped + "'"
    if normalized == "string":
        if not isinstance(value, str):
            raise UnsupportedCSignatureError("Valor string inválido.")
        return json.dumps(value, ensure_ascii=False)
    raise UnsupportedCSignatureError("Tipo de C não suportado.")


def _capture_return(type_name: str) -> list[str]:
    """Serializa got; texto usa hexadecimal para não confundir o protocolo com printf do aluno."""
    if type_name in {"int", "long"}:
        formatter = "%ld" if type_name == "long" else "%d"
        return [f'printf("{formatter}", got);']
    if type_name == "bool":
        return ['fputs(got ? "true" : "false", stdout);']
    if type_name in _FLOAT_TYPES:
        precision = 9 if type_name == "float" else 17
        return [
            'if (isnan(got)) fputs("\\\"NaN\\\"", stdout);',
            'else if (isinf(got)) fputs(got < 0 ? "\\\"-Infinity\\\"" : "\\\"Infinity\\\"", stdout);',
            f'else printf("%.{precision}g", (double) got);',
        ]
    if type_name == "char":
        return ['printf("x:%02x", (unsigned int)(unsigned char) got);']
    return [
        'if (got == NULL) fputs("null", stdout);',
        'else {',
        'size_t captured_length = 0;',
        f'while (captured_length <= {MAX_CAPTURED_STRING_BYTES} && got[captured_length] != \'\\0\') captured_length++;',
        f'if (captured_length > {MAX_CAPTURED_STRING_BYTES}) fputs("TRUNCATED", stdout);',
        'else {',
        'fputs("x:", stdout);',
        'for (size_t i = 0; i < captured_length; i++) printf("%02x", (unsigned int)(unsigned char) got[i]);',
        '}',
        '}',
    ]


def gerar_programa_teste(funcao: dict[str, Any], casos_teste: list[dict[str, Any]], codigo_aluno: str) -> GeneratedCProgram:
    """Gera C99 e um marcador imprevisível para o protocolo de resultado."""
    nome = funcao.get("nome") or funcao.get("nome_funcao")
    retorno = funcao.get("tipo_retorno") or funcao.get("tipoRetorno") or funcao.get("retorno")
    parametros = funcao.get("parametros", [])
    if not isinstance(nome, str) or not nome.isidentifier() or not isinstance(retorno, str):
        raise UnsupportedCSignatureError("Assinatura de função inválida.")
    return_type = _c_type(retorno)
    declarations = []
    for parameter in parametros:
        parameter_name, parameter_type = parameter.get("nome"), parameter.get("tipo")
        if not isinstance(parameter_name, str) or not parameter_name.isidentifier() or not isinstance(parameter_type, str):
            raise UnsupportedCSignatureError("Parâmetro inválido.")
        suffix = "[]" if parameter_type.endswith("[]") else ""
        declarations.append(f"{_c_type(parameter_type, parameter=True)} {parameter_name}{suffix}")
    marker = f"__CODELAB_RESULT_{secrets.token_hex(16)}__"
    lines = [
        "#include <stdio.h>", "#include <stdbool.h>", "#include <string.h>", "#include <math.h>",
        f"{return_type} {nome}({', '.join(declarations) or 'void'});", "#line 1", codigo_aluno,
        "int main(void) {",
    ]
    for index, case in enumerate(casos_teste, start=1):
        entries = case.get("entradas", case.get("inputs"))
        expected = case.get("retorno_esperado", case.get("retornoEsperado", case.get("output_esperado")))
        if not isinstance(entries, list) or len(entries) != len(parametros):
            raise UnsupportedCSignatureError("Entradas incompatíveis com a assinatura.")
        arguments = ", ".join(_literal(value, parameter["tipo"]) for value, parameter in zip(entries, parametros, strict=True))
        lines.append("{")
        lines.append(f"{return_type} got = {nome}({arguments});")
        if retorno.lower() == "string":
            lines.append(f"const char *expected = {_literal(expected, retorno)};")
            condition = "got != NULL && strcmp(got, expected) == 0"
        elif retorno.lower() in _FLOAT_TYPES:
            lines.append(f"{return_type} expected = {_literal(expected, retorno)};")
            condition = "fabs((double) got - (double) expected) <= 0.0001"
        else:
            lines.append(f"{return_type} expected = {_literal(expected, retorno)};")
            condition = "got == expected"
        lines.append(f"bool approved = {condition};")
        lines.append(f'printf("\\n{marker}CASE|{index - 1}|%d|", approved ? 1 : 0);')
        lines.extend(_capture_return(retorno.lower()))
        lines.extend(['printf("\\n");', 'fflush(stdout);'])
        lines.append("}")
    lines.extend(["return 0;", "}"])
    return GeneratedCProgram("\n".join(lines), len(casos_teste), marker)

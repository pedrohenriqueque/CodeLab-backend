"""
Gerador de código C de teste para avaliação automática.

Gera um programa C completo com output padronizado:
    CASE 1 PASS
    CASE 2 FAIL expected=120 got=24
    RESULT 1/2
"""

import logging

logger = logging.getLogger(__name__)

# Formato printf para cada tipo C
PRINTF_FMT = {
    "int":           "%d",
    "long":          "%ld",
    "short":         "%hd",
    "unsigned int":  "%u",
    "unsigned long": "%lu",
    "float":         "%f",
    "double":        "%lf",
    "char":          "%c",
    "char*":         "%s",
    "const char*":   "%s",
}

FLOAT_TYPES = {"float", "double"}
STRING_TYPES = {"char*", "const char*"}


def _c_literal(valor, tipo: str = "int") -> str:
    """Converte um valor Python em literal C válido."""
    if valor is None:
        return "NULL"
    if isinstance(valor, bool):
        return "1" if valor else "0"
    if isinstance(valor, str):
        escaped = valor.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(valor, float):
        return f"{valor}"
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, list):
        elements = ", ".join(_c_literal(v) for v in valor)
        return f"{{{elements}}}"
    return str(valor)


def _param_declaration(param: dict) -> str:
    """Gera declaração de parâmetro C: 'int n' ou 'char* s'."""
    tipo = param.get("tipo", "int")
    nome = param.get("nome", "param")
    if tipo.endswith("[]"):
        base = tipo[:-2]
        return f"{base} {nome}[]"
    return f"{tipo} {nome}"


def _tipo_retorno_str(retorno) -> str:
    """Extrai o tipo de retorno do dict JSONB."""
    if isinstance(retorno, dict):
        return retorno.get("tipo", "int")
    return str(retorno) if retorno else "int"


def gerar_programa_teste(
    funcao: dict,
    casos_teste: list[dict],
    codigo_aluno: str,
) -> tuple[str, int]:
    """
    Gera programa C completo para avaliação.

    Args:
        funcao: dict com nome_funcao, parametros, retorno
        casos_teste: lista de dicts com inputs, output_esperado
        codigo_aluno: código C do aluno

    Returns:
        (código_c_completo, total_de_casos)
    """
    nome = funcao["nome_funcao"]
    parametros = funcao.get("parametros", [])
    retorno = funcao.get("retorno", {"tipo": "int"})

    tipo_ret = _tipo_retorno_str(retorno)
    params_decl = ", ".join(_param_declaration(p) for p in parametros)
    if not params_decl:
        params_decl = "void"

    fmt = PRINTF_FMT.get(tipo_ret, "%d")
    is_float = tipo_ret in FLOAT_TYPES
    is_string = tipo_ret in STRING_TYPES
    is_void = tipo_ret == "void"

    lines = [
        "#include <stdio.h>",
        "#include <string.h>",
        "#include <math.h>",
        "#include <stdlib.h>",
        "",
        "// Declaracao da funcao do aluno",
        f"{tipo_ret} {nome}({params_decl});",
        "",
        "// --- Codigo do aluno ---",
        "#line 1",
        codigo_aluno,
        "",
        "// --- Testes automaticos ---",
        "int main() {",
        "    int total = 0, passed = 0;",
        "",
    ]

    total_casos = 0

    for i, caso in enumerate(casos_teste):
        caso_num = i + 1
        total_casos += 1

        inputs = caso.get("inputs", {})
        output_raw = caso.get("output_esperado", {})

        if isinstance(output_raw, dict):
            expected_val = output_raw.get("valor", output_raw)
        else:
            expected_val = output_raw

        # Argumentos na ordem dos parâmetros
        args = []
        for p in parametros:
            pnome = p.get("nome", "")
            ptipo = p.get("tipo", "int")
            val = inputs.get(pnome, 0) if isinstance(inputs, dict) else 0
            args.append(_c_literal(val, ptipo))

        args_str = ", ".join(args)

        lines.append(f"    // CASE {caso_num}")
        lines.append("    total++;")
        lines.append("    {")

        if is_void:
            lines.append(f"        {nome}({args_str});")
            lines.append(f'        printf("CASE {caso_num} PASS\\n");')
            lines.append("        passed++;")
        elif is_string:
            exp_lit = _c_literal(expected_val, tipo_ret)
            lines.append(f"        {tipo_ret} got = {nome}({args_str});")
            lines.append(f"        {tipo_ret} expected = {exp_lit};")
            lines.append(f"        if (got != NULL && strcmp(got, expected) == 0) {{")
            lines.append(f'            printf("CASE {caso_num} PASS\\n");')
            lines.append("            passed++;")
            lines.append("        } else {")
            lines.append(f'            printf("CASE {caso_num} FAIL expected={fmt} got={fmt}\\n", expected, got ? got : "(null)");')
            lines.append("        }")
        elif is_float:
            exp_lit = _c_literal(expected_val, tipo_ret)
            lines.append(f"        {tipo_ret} got = {nome}({args_str});")
            lines.append(f"        {tipo_ret} expected = {exp_lit};")
            lines.append("        if (fabs((double)got - (double)expected) < 0.0001) {")
            lines.append(f'            printf("CASE {caso_num} PASS\\n");')
            lines.append("            passed++;")
            lines.append("        } else {")
            lines.append(f'            printf("CASE {caso_num} FAIL expected={fmt} got={fmt}\\n", expected, got);')
            lines.append("        }")
        else:
            exp_lit = _c_literal(expected_val, tipo_ret)
            lines.append(f"        {tipo_ret} got = {nome}({args_str});")
            lines.append(f"        {tipo_ret} expected = {exp_lit};")
            lines.append("        if (got == expected) {")
            lines.append(f'            printf("CASE {caso_num} PASS\\n");')
            lines.append("            passed++;")
            lines.append("        } else {")
            lines.append(f'            printf("CASE {caso_num} FAIL expected={fmt} got={fmt}\\n", expected, got);')
            lines.append("        }")

        lines.append("    }")
        lines.append("")

    lines.append('    printf("RESULT %d/%d\\n", passed, total);')
    lines.append("    return 0;")
    lines.append("}")

    codigo = "\n".join(lines)
    logger.debug("Codigo C gerado (%d casos, %d linhas)", total_casos, len(lines))
    return codigo, total_casos

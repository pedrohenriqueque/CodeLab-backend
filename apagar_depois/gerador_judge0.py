"""
Gerador de código C de teste para o Judge0.

Gera um programa C completo com:
- Includes necessários
- Declaração (forward) da função do aluno
- Código do aluno embutido
- Função main() que executa cada caso de teste
- Output padronizado: CASE N PASS / CASE N FAIL expected=X got=Y
- Linha final: RESULT passed/total
"""

import json
import logging

logger = logging.getLogger(__name__)

# ---- Mapeamento de tipos C ----

# Formato printf para cada tipo
PRINTF_FMT = {
    'int':           '%d',
    'long':          '%ld',
    'short':         '%hd',
    'unsigned int':  '%u',
    'unsigned long': '%lu',
    'float':         '%f',
    'double':        '%lf',
    'char':          '%c',
    'char*':         '%s',
    'const char*':   '%s',
}

# Tipos que precisam de comparação com tolerância (float point)
FLOAT_TYPES = {'float', 'double'}

# Tipos que precisam de strcmp
STRING_TYPES = {'char*', 'const char*'}


def _c_literal(valor, tipo='int'):
    """Converte um valor Python em literal C válido."""
    if valor is None:
        return 'NULL'
    if isinstance(valor, bool):
        return '1' if valor else '0'
    if isinstance(valor, str):
        # Escapa aspas dentro da string
        escaped = valor.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(valor, float):
        return f'{valor}'
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, list):
        elements = ', '.join(_c_literal(v) for v in valor)
        return f'{{{elements}}}'
    return str(valor)


def _param_declaration(param):
    """Gera declaração de parâmetro C: 'int n' ou 'const char* s'."""
    tipo = param.get('tipo', 'int')
    nome = param.get('nome', 'param')
    # Para tipos array como int[], declarar como ponteiro no parâmetro
    if tipo.endswith('[]'):
        base = tipo[:-2]
        return f'{base} {nome}[]'
    return f'{tipo} {nome}'


def _tipo_retorno_str(retorno_json):
    """Extrai o tipo de retorno do JSONB."""
    if isinstance(retorno_json, dict):
        return retorno_json.get('tipo', 'int')
    return str(retorno_json) if retorno_json else 'int'


def gerar_programa_teste(funcao, casos_teste, codigo_aluno):
    """
    Gera programa C completo para avaliação.

    Args:
        funcao: dict ou objeto Funcao com campos:
            nome_funcao, parametros, retorno
        casos_teste: lista de dicts ou objetos CasoTeste com campos:
            inputs (dict), output_esperado (dict com campo 'valor')

        codigo_aluno: string com código C do aluno

    Returns:
        tuple(str, int): (código C completo, total de casos)
    """
    nome = funcao['nome_funcao'] if isinstance(funcao, dict) else funcao.nome_funcao
    parametros = funcao['parametros'] if isinstance(funcao, dict) else funcao.parametros
    retorno = funcao['retorno'] if isinstance(funcao, dict) else funcao.retorno

    tipo_ret = _tipo_retorno_str(retorno)
    params_decl = ', '.join(_param_declaration(p) for p in parametros)
    if not params_decl:
        params_decl = 'void'

    fmt = PRINTF_FMT.get(tipo_ret, '%d')
    is_float = tipo_ret in FLOAT_TYPES
    is_string = tipo_ret in STRING_TYPES
    is_void = tipo_ret == 'void'

    # ---- Includes ----
    lines = [
        '#include <stdio.h>',
        '#include <string.h>',
        '#include <math.h>',
        '#include <stdlib.h>',
        '',
        f'// Declaracao da funcao do aluno',
        f'{tipo_ret} {nome}({params_decl});',
        '',
        '// --- Codigo do aluno ---',
        '#line 1',
        codigo_aluno,
        '',
        '// --- Testes automaticos ---',
        'int main() {',
        '    int total = 0, passed = 0;',
        '',
    ]

    total_casos = 0

    for i, caso in enumerate(casos_teste):
        caso_num = i + 1
        total_casos += 1

        # Extrair inputs e output esperado
        inputs = caso['inputs'] if isinstance(caso, dict) else caso.inputs
        output_raw = caso['output_esperado'] if isinstance(caso, dict) else caso.output_esperado

        # output_esperado é {"valor": X}
        if isinstance(output_raw, dict):
            expected_val = output_raw.get('valor', output_raw)
        else:
            expected_val = output_raw

        # Construir argumentos da chamada, na ordem dos parâmetros
        args = []
        for p in parametros:
            pnome = p.get('nome', '')
            ptipo = p.get('tipo', 'int')
            val = inputs.get(pnome, 0) if isinstance(inputs, dict) else 0
            args.append(_c_literal(val, ptipo))

        args_str = ', '.join(args)

        lines.append(f'    // CASE {caso_num}')
        lines.append(f'    total++;')
        lines.append(f'    {{')

        if is_void:
            # Funções void: apenas verifica que não dá crash
            lines.append(f'        {nome}({args_str});')
            lines.append(f'        printf("CASE {caso_num} PASS\\n");')
            lines.append(f'        passed++;')
        elif is_string:
            exp_lit = _c_literal(expected_val, tipo_ret)
            lines.append(f'        {tipo_ret} got = {nome}({args_str});')
            lines.append(f'        {tipo_ret} expected = {exp_lit};')
            lines.append(f'        if (got != NULL && strcmp(got, expected) == 0) {{')
            lines.append(f'            printf("CASE {caso_num} PASS\\n");')
            lines.append(f'            passed++;')
            lines.append(f'        }} else {{')
            lines.append(f'            printf("CASE {caso_num} FAIL expected={fmt} got={fmt}\\n", expected, got ? got : "(null)");')
            lines.append(f'        }}')
        elif is_float:
            exp_lit = _c_literal(expected_val, tipo_ret)
            lines.append(f'        {tipo_ret} got = {nome}({args_str});')
            lines.append(f'        {tipo_ret} expected = {exp_lit};')
            lines.append(f'        if (fabs((double)got - (double)expected) < 0.0001) {{')
            lines.append(f'            printf("CASE {caso_num} PASS\\n");')
            lines.append(f'            passed++;')
            lines.append(f'        }} else {{')
            lines.append(f'            printf("CASE {caso_num} FAIL expected={fmt} got={fmt}\\n", expected, got);')
            lines.append(f'        }}')
        else:
            # Tipos inteiros (int, long, short, unsigned, char)
            exp_lit = _c_literal(expected_val, tipo_ret)
            lines.append(f'        {tipo_ret} got = {nome}({args_str});')
            lines.append(f'        {tipo_ret} expected = {exp_lit};')
            lines.append(f'        if (got == expected) {{')
            lines.append(f'            printf("CASE {caso_num} PASS\\n");')
            lines.append(f'            passed++;')
            lines.append(f'        }} else {{')
            lines.append(f'            printf("CASE {caso_num} FAIL expected={fmt} got={fmt}\\n", expected, got);')
            lines.append(f'        }}')

        lines.append(f'    }}')
        lines.append(f'')

    lines.append(f'    printf("RESULT %d/%d\\n", passed, total);')
    lines.append(f'    return 0;')
    lines.append(f'}}')

    codigo = '\n'.join(lines)
    logger.debug("Codigo C gerado (%d casos, %d linhas)", total_casos, len(lines))
    return codigo, total_casos

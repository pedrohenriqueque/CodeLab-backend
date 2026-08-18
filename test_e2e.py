"""Script de teste end-to-end para a API FastAPI."""
import httpx
import json
import asyncio
import sys

BASE = "http://127.0.0.1:8000"


async def test():
    async with httpx.AsyncClient(base_url=BASE, timeout=60.0) as client:

        # 1. Health check
        print("=== HEALTH ===")
        r = await client.get("/api/health")
        print(r.status_code, r.json())
        assert r.status_code == 200

        # 2. Criar atividade
        print("\n=== CRIAR ATIVIDADE ===")
        r = await client.post("/api/atividades", json={
            "titulo": "Lista 1 - Funções Básicas",
            "pontuacaoMaxima": 100,
        })
        print(f"Status: {r.status_code}")
        atividade = r.json()
        print(json.dumps(atividade, indent=2))
        assert r.status_code == 201
        atividade_uuid = atividade["uuid"]

        # 3. Criar funcao fatorial
        print("\n=== CRIAR FUNCAO ===")
        r = await client.post(f"/api/funcoes?atividade_uuid={atividade_uuid}", json={
            "nomeFuncao": "fatorial",
            "descricao": "Calcula o fatorial de n",
            "parametros": [{"nome": "n", "tipo": "int"}],
            "retorno": {"tipo": "int"},
            "pontos": 10,
        })
        print(f"Status: {r.status_code}")
        funcao = r.json()
        print(json.dumps(funcao, indent=2))
        assert r.status_code == 201
        funcao_uuid = funcao["uuid"]

        # 4. Adicionar casos de teste (em lote)
        print("\n=== CRIAR CASOS DE TESTE ===")
        r = await client.post(f"/api/funcoes/{funcao_uuid}/casos-teste", json=[
            {"inputs": {"n": 0}, "outputEsperado": {"valor": 1}, "descricao": "0! = 1"},
            {"inputs": {"n": 1}, "outputEsperado": {"valor": 1}, "descricao": "1! = 1"},
            {"inputs": {"n": 5}, "outputEsperado": {"valor": 120}, "descricao": "5! = 120"},
            {"inputs": {"n": 10}, "outputEsperado": {"valor": 3628800}, "descricao": "10! = 3628800"},
        ])
        print(f"Status: {r.status_code}")
        print(json.dumps(r.json(), indent=2))
        assert r.status_code == 201

        # 5. Listar casos de teste
        print("\n=== LISTAR CASOS ===")
        r = await client.get(f"/api/funcoes/{funcao_uuid}/casos-teste")
        casos = r.json()
        print(f"Status: {r.status_code}, Total: {len(casos)} casos")
        assert r.status_code == 200
        assert len(casos) == 4

        # 6. Detalhe da funcao
        print("\n=== DETALHE FUNCAO ===")
        r = await client.get(f"/api/funcoes/{funcao_uuid}")
        det = r.json()
        print(f"Status: {r.status_code}")
        print(f"Nome: {det['nomeFuncao']}, Pontos: {det['pontos']}, Casos: {len(det['casosTeste'])}")

        # 7. Submeter codigo CORRETO
        print("\n=== SUBMETER CODIGO CORRETO ===")
        r = await client.post("/api/submissoes", json={
            "funcaoUuid": funcao_uuid,
            "codigo": "int fatorial(int n) { if (n <= 1) return 1; return n * fatorial(n - 1); }",
        })
        print(f"Status: {r.status_code}")
        result = r.json()
        print(json.dumps(result, indent=2))

        if r.status_code == 200:
            print(f"\n>>> NOTA: {result.get('nota')}/{result.get('pontosMaximo')}")
            print(f">>> Casos passados: {result.get('casosPassados')}/{result.get('totalCasos')}")

        # 8. Submeter codigo ERRADO
        print("\n=== SUBMETER CODIGO ERRADO ===")
        r = await client.post("/api/submissoes", json={
            "funcaoUuid": funcao_uuid,
            "codigo": "int fatorial(int n) { return n; }",
        })
        print(f"Status: {r.status_code}")
        result2 = r.json()
        print(json.dumps(result2, indent=2))

        if r.status_code == 200:
            print(f"\n>>> NOTA: {result2.get('nota')}/{result2.get('pontosMaximo')}")
            print(f">>> Casos passados: {result2.get('casosPassados')}/{result2.get('totalCasos')}")

        def _verificar_erro(res, descricao):
            """Verifica se o erro de compilação contém a dica esperada."""
            erro = res.get("erroCompilacao", "")
            if erro:
                # Pega só a primeira linha da dica (antes do log do compilador)
                dica = erro.split("\n[Erro Original")[0].strip()
                print(f"\n>>> Dica exibida para o aluno:\n    {dica}")
            else:
                print(f"\n>>> AVISO: Nenhum erroCompilacao retornado para: {descricao}")

        # --- Testes de erros de compilação ---

        # 8.1 Falta de chave '}'
        print("\n=== ERRO: FALTA CHAVE } ===")
        r = await client.post("/api/submissoes", json={
            "funcaoUuid": funcao_uuid,
            "codigo": "int fatorial(int n) { if (n <= 1) return 1; return n * fatorial(n - 1); ",
        })
        r_json = r.json()
        print(f"Status: {r.status_code}")
        _verificar_erro(r_json, "falta chave }")
        assert "Chave faltando" in r_json.get("erroCompilacao", ""), "Esperava dica de chave faltando"

        # 8.2 Falta de ponto-e-vírgula ';'
        print("\n=== ERRO: FALTA PONTO-E-VIRGULA ; ===")
        r = await client.post("/api/submissoes", json={
            "funcaoUuid": funcao_uuid,
            "codigo": "int fatorial(int n) { if (n <= 1) return 1; return n * fatorial(n - 1) }",
        })
        r_json = r.json()
        print(f"Status: {r.status_code}")
        _verificar_erro(r_json, "falta ponto-e-vírgula")
        assert "Ponto-e-v" in r_json.get("erroCompilacao", "") or "Chave" in r_json.get("erroCompilacao", ""), \
            "Esperava dica de ponto-e-vírgula ou chave faltando"

        # 8.3 Falta de parêntese ')'
        print("\n=== ERRO: FALTA PARENTESE ) ===")
        r = await client.post("/api/submissoes", json={
            "funcaoUuid": funcao_uuid,
            "codigo": "int fatorial(int n) { if (n <= 1 return 1; return n * fatorial(n - 1); }",
        })
        r_json = r.json()
        print(f"Status: {r.status_code}")
        _verificar_erro(r_json, "falta parêntese )")

        # 8.4 Falta de aspas duplas
        print("\n=== ERRO: FALTA ASPAS DUPLAS ===")
        r = await client.post("/api/submissoes", json={
            "funcaoUuid": funcao_uuid,
            "codigo": 'int fatorial(int n) { char *s = "hello; return n; }',
        })
        r_json = r.json()
        print(f"Status: {r.status_code}")
        _verificar_erro(r_json, "falta aspas duplas")

        # 8.5 Falta de aspas simples
        print("\n=== ERRO: FALTA ASPAS SIMPLES ===")
        r = await client.post("/api/submissoes", json={
            "funcaoUuid": funcao_uuid,
            "codigo": "int fatorial(int n) { char c = 'a; return n; }",
        })
        r_json = r.json()
        print(f"Status: {r.status_code}")
        _verificar_erro(r_json, "falta aspas simples")

        # 9. Listar submissoes
        print("\n=== LISTAR SUBMISSOES ===")
        r = await client.get("/api/submissoes")
        subs = r.json()
        print(f"Status: {r.status_code}, Total: {len(subs)} submissoes")

        # 10. Listar atividades
        print("\n=== LISTAR ATIVIDADES ===")
        r = await client.get("/api/atividades")
        atvs = r.json()
        print(f"Status: {r.status_code}, Total: {len(atvs)} atividades")

        print("\n" + "=" * 60)
        print("TODOS OS TESTES PASSARAM!")
        print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(test())
    except AssertionError as e:
        print(f"\nFALHA: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

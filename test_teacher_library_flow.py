import asyncio
import httpx
from app.main import app
from app.db.session import init_db

async def run_tests():
    await init_db()
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Autenticar como professor
        login_resp = await client.post("/api/auth/login", data={
            "username": "ana.souza@universidade.br",
            "password": "123456"
        })
        assert login_resp.status_code == 200, f"Falha no login professor: {login_resp.text}"
        token = login_resp.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})

        print("1. Criando função na biblioteca...")
        resp = await client.post("/api/funcoes", json={
            "nomeFuncao": "somar_inteiros",
            "descricao": "Retorna a soma de dois inteiros",
            "retorno": {"tipo": "int"},
            "dificuldadePadrao": "facil",
            "parametros": [
                {"nome": "a", "tipo": "int"},
                {"nome": "b", "tipo": "int"}
            ]
        })
        assert resp.status_code == 201, f"Erro criar funcao: {resp.status_code} {resp.text}"
        func_data = resp.json()
        func_uuid = func_data["uuid"]
        print(f"   -> Função criada: {func_uuid} ({func_data['nomeFuncao']})")

        print("2. Listando funções na biblioteca com filtros...")
        resp = await client.get("/api/funcoes", params={"dificuldade": "facil", "termo": "somar"})
        assert resp.status_code == 200
        items = resp.json() if isinstance(resp.json(), list) else resp.json().get("items", [])
        assert any(f["uuid"] == func_uuid for f in items), "Função não encontrada na busca"
        print(f"   -> Encontrada na busca com sucesso! Total na busca: {len(items)}")

        print("3. Adicionando casos de teste canônicos...")
        resp = await client.post(f"/api/funcoes/{func_uuid}/casos-teste", json=[
            {
                "inputs": {"a": 2, "b": 3},
                "outputEsperado": {"valor": 5},
                "descricao": "Soma positiva simples"
            },
            {
                "inputs": {"a": -1, "b": 1},
                "outputEsperado": {"valor": 0},
                "descricao": "Soma com negativo"
            }
        ])
        assert resp.status_code == 201, f"Erro criar casos de teste: {resp.status_code} {resp.text}"
        casos = resp.json()
        assert len(casos) == 2
        caso1_uuid = casos[0]["uuid"]
        caso2_uuid = casos[1]["uuid"]
        print(f"   -> 2 casos criados: {caso1_uuid}, {caso2_uuid}")

        print("4. Verificando detalhe da função com total_casos_teste...")
        resp = await client.get(f"/api/funcoes/{func_uuid}")
        assert resp.status_code == 200
        detalhe = resp.json()
        assert detalhe.get("totalCasosTeste") == 2 or detalhe.get("total_casos_teste") == 2, f"Total inesperado: {detalhe}"
        print("   -> Detalhe OK com total_casos_teste = 2")

        print("5. Atualizando caso de teste canônico...")
        resp = await client.put(f"/api/funcoes/{func_uuid}/casos-teste/{caso1_uuid}", json={
            "outputEsperado": {"valor": 5},
            "descricao": "Soma positiva atualizada"
        })
        assert resp.status_code == 200
        assert resp.json()["descricao"] == "Soma positiva atualizada"
        print("   -> Caso de teste atualizado com sucesso")

        print("6. Deletando um dos casos de teste canônicos...")
        resp = await client.delete(f"/api/funcoes/{func_uuid}/casos-teste/{caso2_uuid}")
        assert resp.status_code == 204
        resp = await client.get(f"/api/funcoes/{func_uuid}/casos-teste")
        assert len(resp.json()) == 1
        print("   -> Caso de teste deletado. Restou 1 caso.")

        print("7. Criando atividade...")
        resp = await client.post("/api/atividades", json={
            "titulo": "Atividade de Teste Professor",
            "descricao": "Atividade para testar fluxo do professor",
            "pontuacaoMaxima": 100,
            "tipo": "exercicio"
        })
        assert resp.status_code == 201
        ativ_data = resp.json()
        ativ_uuid = ativ_data["uuid"]
        print(f"   -> Atividade criada: {ativ_uuid}")

        print("8. Associando função da biblioteca à atividade com parâmetros contextuais...")
        resp = await client.post(f"/api/atividades/{ativ_uuid}/funcoes", json={
            "funcaoUuid": func_uuid,
            "dificuldade": "medio",
            "peso": 25.0,
            "ordem": 0,
            "casosTeste": [
                {
                    "casoTesteUuid": caso1_uuid,
                    "oculto": True
                }
            ]
        })
        assert resp.status_code == 201, f"Erro ao associar: {resp.status_code} {resp.text}"
        af_data = resp.json()
        assert af_data["peso"] == 25.0
        assert af_data["dificuldade"] == "medio"
        assert len(af_data["casosTeste"]) == 1
        assert af_data["casosTeste"][0]["oculto"] is True
        print("   -> Associação criada com sucesso com dificuldade contextual, peso e oculto=True")

        print("9. Verificando detalhe da atividade com função contextual...")
        resp = await client.get(f"/api/atividades/{ativ_uuid}")
        assert resp.status_code == 200
        ativ_detalhe = resp.json()
        assert len(ativ_detalhe["funcoes"]) == 1
        fn = ativ_detalhe["funcoes"][0]
        assert fn["funcaoUuid"] == func_uuid
        assert fn["peso"] == 25.0
        assert fn["casosTeste"][0]["oculto"] is True
        print("   -> Detalhe da atividade contém a função com dados contextuais")

        print("10. Atualizando parâmetros contextuais da função na atividade via PATCH...")
        resp = await client.patch(f"/api/atividades/{ativ_uuid}/funcoes/{func_uuid}", json={
            "peso": 40.0,
            "dificuldade": "dificil",
            "casosTeste": [
                {
                    "casoTesteUuid": caso1_uuid,
                    "oculto": False
                }
            ]
        })
        assert resp.status_code == 200
        updated_af = resp.json()
        assert updated_af["peso"] == 40.0
        assert updated_af["dificuldade"] == "dificil"
        assert updated_af["casosTeste"][0]["oculto"] is False
        print("   -> Parâmetros contextuais atualizados com sucesso")

        print("11. Tentando excluir função da biblioteca vinculada à atividade (deve dar 409 Conflict)...")
        resp = await client.delete(f"/api/funcoes/{func_uuid}")
        assert resp.status_code == 409, f"Esperado 409, obteve: {resp.status_code}"
        print("   -> Exclusão bloqueada com 409 Conflict como esperado")

        print("12. Desassociando função da atividade via DELETE /api/atividades/{ativ_uuid}/funcoes/{func_uuid}...")
        resp = await client.delete(f"/api/atividades/{ativ_uuid}/funcoes/{func_uuid}")
        assert resp.status_code == 204
        print("   -> Desassociação concluída")

        print("13. Verificando que a função CONTINUA EXISTINDO na biblioteca...")
        resp = await client.get(f"/api/funcoes/{func_uuid}")
        assert resp.status_code == 200, "A função deveria permanecer na biblioteca!"
        assert resp.json()["uuid"] == func_uuid
        print("   -> Função preservada na biblioteca com sucesso!")

        print("14. Excluindo função agora que está desassociada...")
        resp = await client.delete(f"/api/funcoes/{func_uuid}")
        assert resp.status_code == 204
        print("   -> Função excluída da biblioteca com sucesso")

    print("\nTODOS OS TESTES DO FLUXO DO PROFESSOR PASSARAM COM SUCESSO!")

if __name__ == "__main__":
    asyncio.run(run_tests())

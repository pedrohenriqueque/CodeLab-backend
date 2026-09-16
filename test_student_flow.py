import asyncio
import httpx
from app.main import app
from app.db.session import init_db

async def run_tests():
    await init_db()
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        print("1. Fazendo login como aluno (Pedro Lacerda)...")
        login_resp = await client.post("/api/auth/login", data={
            "username": "pedro.lacerda@aluno.universidade.br",
            "password": "password123"
        })
        if login_resp.status_code != 200:
            login_resp = await client.post("/api/auth/login", data={
                "username": "pedro.lacerda@aluno.universidade.br",
                "password": "123"
            })
        if login_resp.status_code != 200:
            login_resp = await client.post("/api/auth/login", data={
                "username": "pedro.lacerda@aluno.universidade.br",
                "password": "senha"
            })
        if login_resp.status_code != 200:
            login_resp = await client.post("/api/auth/login", data={
                "username": "pedro.lacerda@aluno.universidade.br",
                "password": "123456"
            })
        print(f"   -> Login status: {login_resp.status_code}")
        assert login_resp.status_code == 200, f"Falha no login: {login_resp.text}"
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("   -> Login autenticado com sucesso!")

        print("2. Criando atividade de teste aberta com 2 funções da biblioteca...")
        # Login como professor para criar atividade de teste
        prof_login = await client.post("/api/auth/login", data={
            "username": "ana.souza@universidade.br",
            "password": "123"
        })
        if prof_login.status_code != 200:
            prof_login = await client.post("/api/auth/login", data={
                "username": "ana.souza@universidade.br",
                "password": "123456"
            })
        prof_token = prof_login.json()["access_token"]
        prof_headers = {"Authorization": f"Bearer {prof_token}"}

        # 2.1 Criar Função 1
        fn1_resp = await client.post("/api/funcoes", json={
            "nomeFuncao": "teste_aluno_dobro",
            "descricao": "Calcula dobro",
            "retorno": {"tipo": "int"},
            "dificuldadePadrao": "facil",
            "parametros": [{"nome": "n", "tipo": "int"}]
        }, headers=prof_headers)
        fn1_uuid = fn1_resp.json()["uuid"]

        # Casos de teste para Função 1 (1 público, 1 oculto)
        await client.post(f"/api/funcoes/{fn1_uuid}/casos-teste", json=[
            {"inputs": {"n": 2}, "outputEsperado": {"valor": 4}, "descricao": "Caso publico"},
            {"inputs": {"n": 5}, "outputEsperado": {"valor": 10}, "descricao": "Caso oculto"}
        ], headers=prof_headers)

        # 2.2 Criar Função 2
        fn2_resp = await client.post("/api/funcoes", json={
            "nomeFuncao": "teste_aluno_triplo",
            "descricao": "Calcula triplo",
            "retorno": {"tipo": "int"},
            "dificuldadePadrao": "medio",
            "parametros": [{"nome": "n", "tipo": "int"}]
        }, headers=prof_headers)
        fn2_uuid = fn2_resp.json()["uuid"]

        await client.post(f"/api/funcoes/{fn2_uuid}/casos-teste", json=[
            {"inputs": {"n": 3}, "outputEsperado": {"valor": 9}, "descricao": "Triplo publico"}
        ], headers=prof_headers)

        # 2.3 Criar Atividade aberta (sem data_fechamento passada)
        atv_resp = await client.post("/api/atividades", json={
            "titulo": "Atividade Teste Fluxo Aluno",
            "descricao": "Atividade para validacao automatizada do fluxo do aluno",
            "pontuacaoMaxima": 100,
            "tipo": "exercicio"
        }, headers=prof_headers)
        atv_uuid = atv_resp.json()["uuid"]

        # Associar Função 1 (com 1 caso oculto)
        casos_fn1_resp = await client.get(f"/api/funcoes/{fn1_uuid}/casos-teste", headers=prof_headers)
        casos_fn1 = casos_fn1_resp.json()
        await client.post(f"/api/atividades/{atv_uuid}/funcoes", json={
            "funcaoUuid": fn1_uuid,
            "peso": 50.0,
            "dificuldade": "facil",
            "ordem": 0,
            "casosTeste": [
                {"casoTesteUuid": casos_fn1[0]["uuid"], "oculto": False},
                {"casoTesteUuid": casos_fn1[1]["uuid"], "oculto": True}
            ]
        }, headers=prof_headers)

        # Associar Função 2
        casos_fn2_resp = await client.get(f"/api/funcoes/{fn2_uuid}/casos-teste", headers=prof_headers)
        casos_fn2 = casos_fn2_resp.json()
        await client.post(f"/api/atividades/{atv_uuid}/funcoes", json={
            "funcaoUuid": fn2_uuid,
            "peso": 50.0,
            "dificuldade": "medio",
            "ordem": 1,
            "casosTeste": [
                {"casoTesteUuid": casos_fn2[0]["uuid"], "oculto": False}
            ]
        }, headers=prof_headers)

        # Publicar atividade
        await client.patch(f"/api/atividades/{atv_uuid}", json={"status": "publicado"}, headers=prof_headers)
        print(f"   -> Atividade aberta criada: {atv_uuid} com Funcao 1 ({fn1_uuid}) e Funcao 2 ({fn2_uuid})")

        # 3. Aluno consulta a atividade criada
        resp_det = await client.get(f"/api/atividades/{atv_uuid}", headers=headers)
        assert resp_det.status_code == 200
        atv_selecionada = resp_det.json()
        funcoes = atv_selecionada["funcoes"]
        
        # 3. Verificar mascaramento de casos ocultos
        print("3. Verificando mascaramento de casos de teste ocultos...")
        has_oculto = False
        for fn in funcoes:
            for c in fn.get("casosTeste", []):
                if c.get("oculto"):
                    has_oculto = True
                    assert c.get("inputs") is None or c.get("inputs") == {}, f"Inputs de caso oculto vazaram: {c}"
                    assert c.get("outputEsperado") is None or c.get("outputEsperado") == {}, f"Output esperado vazou: {c}"
        print(f"   -> Casos de teste ocultos verificados (ocultos mascarados? {has_oculto})")

        # 4. Realizar submissão de código para a primeira função
        fn1 = funcoes[0]
        fn1_uuid = fn1.get("funcaoUuid") or fn1.get("uuid")
        print(f"4. Submetendo tentativa para a Funcao 1 ({fn1_uuid})...")
        sub1_resp = await client.post("/api/submissoes", json={
            "funcaoUuid": fn1_uuid,
            "atividadeUuid": atv_uuid,
            "codigo": "int dobro(int n) { return n * 2; }"
        }, headers=headers)
        print(f"   -> Status submissao 1: {sub1_resp.status_code}")
        assert sub1_resp.status_code in [200, 201], f"Erro ao submeter: {sub1_resp.text}"
        sub1_data = sub1_resp.json()
        print(f"   -> Submissao 1 realizada: nota={sub1_data.get('nota')}, status={sub1_data.get('status')}")

        # 5. Listar submissões isoladas por função
        print("5. Verificando isolamento do histórico de submissões...")
        hist_fn1_resp = await client.get("/api/submissoes", params={
            "funcaoUuid": fn1_uuid,
            "atividadeUuid": atv_uuid
        }, headers=headers)
        assert hist_fn1_resp.status_code == 200
        hist_fn1 = hist_fn1_resp.json()
        assert len(hist_fn1) >= 1, "Deveria listar ao menos 1 submissão para a função 1"
        assert all(s["funcaoUuid"] == fn1_uuid for s in hist_fn1), "Submissão de outra função vazou na listagem da função 1"
        print(f"   -> Historico da Funcao 1 isolado com sucesso ({len(hist_fn1)} submissoes)")

        if len(funcoes) > 1:
            fn2 = funcoes[1]
            fn2_uuid = fn2.get("funcaoUuid") or fn2.get("uuid")
            hist_fn2_resp = await client.get("/api/submissoes", params={
                "funcaoUuid": fn2_uuid,
                "atividadeUuid": atv_uuid
            }, headers=headers)
            assert hist_fn2_resp.status_code == 200
            hist_fn2 = hist_fn2_resp.json()
            assert not any(s["funcaoUuid"] == fn1_uuid for s in hist_fn2), "Tentativas da Funcao 1 vazaram na Funcao 2"
            print("   -> Historico da Funcao 2 nao contem submissoes da Funcao 1")

        # 6. Realizar Entrega Final da Atividade (RN14)
        print("6. Realizando Entrega Final da Atividade (RN14)...")
        # Se ja entregue em rodadas anteriores, testamos a idempotência/resposta
        entregar_resp = await client.post(f"/api/atividades/{atv_uuid}/entregar", headers=headers)
        print(f"   -> Status entrega: {entregar_resp.status_code}")
        if entregar_resp.status_code == 200:
            entrega_data = entregar_resp.json()
            assert entrega_data["status"] == "entregue"
            print(f"   -> Entrega concluida com nota consolidada: {entrega_data.get('notaFinal')}")
        else:
            assert entregar_resp.status_code == 400 and "já entregue" in entregar_resp.text.lower(), f"Resposta inesperada: {entregar_resp.text}"
            print("   -> Atividade ja constava como entregue (comportamento OK)")

        # 7. Tentar submeter novamente apos entrega (deve ser rejeitado com 400)
        print("7. Tentando submeter apos atividade entregue (deve dar erro 400)...")
        sub_bloqueada_resp = await client.post("/api/submissoes", json={
            "funcaoUuid": fn1_uuid,
            "atividadeUuid": atv_uuid,
            "codigo": "int dobro(int n) { return n * 2; }"
        }, headers=headers)
        assert sub_bloqueada_resp.status_code == 400, f"Esperado 400 ao submeter em atividade entregue, obteve: {sub_bloqueada_resp.status_code}"
        print(f"   -> Submissao bloqueada corretamente apos entrega final: {sub_bloqueada_resp.json()['detail']}")

        # 8. Verificar status_entrega retornado no detalhe da atividade para o aluno
        print("8. Verificando status_entrega retornado no GET da atividade...")
        det_aluno_resp = await client.get(f"/api/atividades/{atv_uuid}", headers=headers)
        assert det_aluno_resp.status_code == 200
        det_data = det_aluno_resp.json()
        assert det_data.get("statusEntrega") == "entregue" or det_data.get("status_entrega") == "entregue"
        print(f"   -> Status de entrega confirmado como 'entregue'")

    print("\nTODOS OS TESTES DO FLUXO DO ALUNO PASSARAM COM SUCESSO!")

if __name__ == "__main__":
    asyncio.run(run_tests())

"""
CodeLab - API Flask para avaliação automática de código C.

Endpoints:
    GET  /                                    Frontend
    GET  /api/health                          Health check

    POST /api/funcoes                         Cadastrar função
    GET  /api/funcoes                         Listar funções
    GET  /api/funcoes/<uuid>                  Detalhe de função

    POST /api/funcoes/<uuid>/casos-teste      Cadastrar caso(s) de teste
    GET  /api/funcoes/<uuid>/casos-teste      Listar casos de teste

    POST /api/submissoes                      Submeter código para avaliação
    GET  /api/submissoes                      Listar submissões
    GET  /api/submissoes/<uuid>               Detalhe de submissão
"""

import os
import re
import logging
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv

# Carregar .env antes de tudo
load_dotenv()

from models import db, Funcao, CasoTeste, Submissao
from avaliador import AvaliadorExercicios

# ---- Logging ----
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ---- App Factory ----

def create_app():
    """Cria e configura a aplicação Flask."""
    app = Flask(__name__)
    CORS(app)

    # Database
    db_url = os.getenv('DATABASE_URL', 'sqlite:///codelab.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
    }

    db.init_app(app)

    # Criar tabelas na primeira execução
    with app.app_context():
        db.create_all()
        logger.info("Database inicializado: %s", db_url)

    # Avaliador (singleton)
    avaliador = AvaliadorExercicios()

    # ============================================================
    # ROTAS
    # ============================================================

    # ---- Frontend ----

    @app.route('/')
    def index():
        return render_template('index.html')

    # ---- Health ----

    @app.route('/api/health', methods=['GET'])
    def health():
        return jsonify({'status': 'ok'}), 200

    # ============================================================
    # FUNÇÕES
    # ============================================================

    @app.route('/api/funcoes', methods=['POST'])
    def criar_funcao():
        """
        Cadastra uma nova função C.

        Body JSON:
        {
            "nome_funcao": "fatorial",
            "descricao": "Calcula o fatorial de n",
            "parametros": [{"nome": "n", "tipo": "int"}],
            "retorno": {"tipo": "int"},
            "pontos": 10
        }
        """
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'erro': 'Body JSON vazio ou inválido'}), 400

        nome = data.get('nome_funcao', '').strip()
        if not nome:
            return jsonify({'erro': 'Campo "nome_funcao" é obrigatório'}), 400

        # Validar como identificador C
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', nome):
            return jsonify({'erro': f'"{nome}" não é um identificador C válido'}), 400

        parametros = data.get('parametros', [])
        retorno = data.get('retorno', {'tipo': 'int'})
        pontos = data.get('pontos', 10)
        descricao = data.get('descricao', '')

        funcao = Funcao(
            nome_funcao=nome,
            descricao=descricao,
            parametros=parametros,
            retorno=retorno,
            pontos=int(pontos),
        )
        db.session.add(funcao)
        db.session.commit()

        logger.info("Funcao criada: %s (uuid=%s)", nome, funcao.uuid)
        return jsonify(funcao.to_dict()), 201

    @app.route('/api/funcoes', methods=['GET'])
    def listar_funcoes():
        """Lista todas as funções cadastradas."""
        funcoes = Funcao.query.order_by(Funcao.created_at.desc()).all()
        return jsonify([f.to_dict() for f in funcoes]), 200

    @app.route('/api/funcoes/<funcao_uuid>', methods=['GET'])
    def detalhe_funcao(funcao_uuid):
        """Retorna detalhes de uma função, incluindo seus casos de teste."""
        funcao = db.session.get(Funcao, funcao_uuid)
        if not funcao:
            return jsonify({'erro': 'Função não encontrada'}), 404
        return jsonify(funcao.to_dict(include_casos=True)), 200

    # ============================================================
    # CASOS DE TESTE
    # ============================================================

    @app.route('/api/funcoes/<funcao_uuid>/casos-teste', methods=['POST'])
    def criar_caso_teste(funcao_uuid):
        """
        Cadastra caso(s) de teste para uma função.

        Aceita um objeto ou lista:

        Objeto único:
        {
            "inputs": {"n": 5},
            "output_esperado": {"valor": 120},
            "descricao": "5! = 120"
        }

        Lista:
        [
            {"inputs": {"n": 0}, "output_esperado": {"valor": 1}, "descricao": "0! = 1"},
            {"inputs": {"n": 5}, "output_esperado": {"valor": 120}, "descricao": "5! = 120"}
        ]
        """
        funcao = db.session.get(Funcao, funcao_uuid)
        if not funcao:
            return jsonify({'erro': 'Função não encontrada'}), 404

        data = request.get_json(silent=True)
        if not data:
            return jsonify({'erro': 'Body JSON vazio ou inválido'}), 400

        # Normalizar: aceitar objeto ou lista
        if isinstance(data, dict):
            items = [data]
        elif isinstance(data, list):
            items = data
        else:
            return jsonify({'erro': 'Esperado objeto ou lista'}), 400

        criados = []
        for item in items:
            inputs = item.get('inputs', {})
            output_esperado = item.get('output_esperado', {})
            descricao = item.get('descricao', '')

            caso = CasoTeste(
                funcao_uuid=funcao_uuid,
                inputs=inputs,
                output_esperado=output_esperado,
                descricao=descricao,
            )
            db.session.add(caso)
            criados.append(caso)

        db.session.commit()
        logger.info("%d caso(s) de teste criados para funcao %s", len(criados), funcao.nome_funcao)

        resultado = [c.to_dict() for c in criados]
        return jsonify(resultado if len(resultado) > 1 else resultado[0]), 201

    @app.route('/api/funcoes/<funcao_uuid>/casos-teste', methods=['GET'])
    def listar_casos_teste(funcao_uuid):
        """Lista todos os casos de teste de uma função."""
        funcao = db.session.get(Funcao, funcao_uuid)
        if not funcao:
            return jsonify({'erro': 'Função não encontrada'}), 404

        casos = funcao.casos_teste.order_by(CasoTeste.created_at.asc()).all()
        return jsonify([c.to_dict() for c in casos]), 200

    # ============================================================
    # SUBMISSÕES
    # ============================================================

    @app.route('/api/submissoes', methods=['POST'])
    def criar_submissao():
        """
        Submete código C para avaliação.

        Body JSON:
        {
            "funcao_uuid": "uuid-da-funcao",
            "codigo": "int fatorial(int n) { if(n<=1) return 1; return n*fatorial(n-1); }"
        }

        Fluxo:
        1. Busca função e seus casos de teste no banco
        2. Cria registro de submissão com status="avaliando"
        3. Gera código C de teste, envia para Judge0
        4. Parseia resultado, calcula nota
        5. Atualiza submissão com resultado e status="concluido"
        6. Retorna JSON com nota e detalhes

        Response:
        {
            "submissao_uuid": "...",
            "funcao": "fatorial",
            "nota": 10.0,
            "pontos_maximo": 10,
            "total_casos": 4,
            "casos_passados": 4,
            "casos": [...],
            "erro_compilacao": null,
            "erro_execucao": null,
            "tempo_ms": 12.5,
            "memoria_kb": 3200
        }
        """
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'erro': 'Body JSON vazio ou inválido'}), 400

        funcao_uuid = data.get('funcao_uuid', '').strip()
        codigo = data.get('codigo', '').strip()

        if not funcao_uuid:
            return jsonify({'erro': 'Campo "funcao_uuid" é obrigatório'}), 400
        if not codigo:
            return jsonify({'erro': 'Campo "codigo" é obrigatório'}), 400

        # Buscar função
        funcao = db.session.get(Funcao, funcao_uuid)
        if not funcao:
            return jsonify({'erro': 'Função não encontrada'}), 404

        # Buscar casos de teste
        casos_teste = funcao.casos_teste.order_by(CasoTeste.created_at.asc()).all()
        if not casos_teste:
            return jsonify({'erro': 'Nenhum caso de teste cadastrado para esta função'}), 400

        # 1. Criar submissão com status "avaliando"
        submissao = Submissao(
            funcao_uuid=funcao_uuid,
            codigo_submetido=codigo,
            status='avaliando',
        )
        db.session.add(submissao)
        db.session.commit()

        logger.info("Submissao %s criada para funcao %s (%d casos)",
                     submissao.uuid[:8], funcao.nome_funcao, len(casos_teste))

        try:
            # 2. Converter modelos para dicts (compatível com avaliador)
            funcao_dict = {
                'nome_funcao': funcao.nome_funcao,
                'parametros': funcao.parametros,
                'retorno': funcao.retorno,
                'pontos': funcao.pontos,
            }
            casos_dict = [
                {
                    'inputs': c.inputs,
                    'output_esperado': c.output_esperado,
                    'descricao': c.descricao,
                }
                for c in casos_teste
            ]

            # 3. Avaliar
            resultado = avaliador.avaliar_submissao(funcao_dict, casos_dict, codigo)

            # 4. Atualizar submissão
            submissao.nota = resultado['nota']
            submissao.status = 'concluido'
            submissao.resultado_json = resultado
            db.session.commit()

            logger.info("Submissao %s finalizada: nota=%.2f/%d",
                        submissao.uuid[:8], resultado['nota'], funcao.pontos)

            # 5. Resposta
            return jsonify({
                'submissao_uuid': submissao.uuid,
                'funcao': funcao.nome_funcao,
                'nota': resultado['nota'],
                'pontos_maximo': resultado['pontos_maximo'],
                'total_casos': resultado['total_casos'],
                'casos_passados': resultado['casos_passados'],
                'casos': resultado['casos'],
                'erro_compilacao': resultado['erro_compilacao'],
                'erro_execucao': resultado['erro_execucao'],
                'tempo_ms': resultado['tempo_ms'],
                'memoria_kb': resultado['memoria_kb'],
            }), 200

        except Exception as e:
            # Marcar como erro
            submissao.status = 'erro'
            submissao.resultado_json = {'erro': str(e)}
            submissao.nota = 0.0
            db.session.commit()

            logger.error("Erro na submissao %s: %s", submissao.uuid[:8], e, exc_info=True)
            return jsonify({
                'submissao_uuid': submissao.uuid,
                'erro': str(e),
                'nota': 0.0,
            }), 500

    @app.route('/api/submissoes', methods=['GET'])
    def listar_submissoes():
        """
        Lista submissões, opcionalmente filtradas.

        Query params:
            funcao_uuid: filtrar por função
            status: filtrar por status
        """
        query = Submissao.query

        funcao_uuid = request.args.get('funcao_uuid')
        if funcao_uuid:
            query = query.filter_by(funcao_uuid=funcao_uuid)

        status = request.args.get('status')
        if status:
            query = query.filter_by(status=status)

        submissoes = query.order_by(Submissao.data_submissao.desc()).all()
        return jsonify([s.to_dict() for s in submissoes]), 200

    @app.route('/api/submissoes/<submissao_uuid>', methods=['GET'])
    def detalhe_submissao(submissao_uuid):
        """Retorna detalhes completos de uma submissão."""
        submissao = db.session.get(Submissao, submissao_uuid)
        if not submissao:
            return jsonify({'erro': 'Submissão não encontrada'}), 404
        return jsonify(submissao.to_dict()), 200

    # ============================================================
    # ENDPOINTS LEGADOS (compatibilidade)
    # ============================================================

    @app.route('/api/avaliar', methods=['POST'])
    def avaliar_legado():
        """Endpoint legado: avalia código sem persistir (compatibilidade)."""
        data = request.get_json(silent=True)
        if not data or 'exercicios' not in data or 'codigo' not in data:
            return jsonify({
                'erro': 'Payload inválido. Necessário: exercicios e codigo'
            }), 400

        try:
            exercicios = data['exercicios']
            codigo = data['codigo']

            # Usar o avaliador diretamente com formato legado
            # Converter formato antigo para o novo
            resultados = []
            for ex in exercicios:
                funcao_dict = {
                    'nome_funcao': ex['nome_funcao'],
                    'parametros': [{'nome': inp, 'tipo': 'int'} for inp in ex.get('inputs', [])],
                    'retorno': {'tipo': 'int'},
                    'pontos': 10,
                }
                output_key = ex.get('output_esperado', 'resultado')
                casos_dict = []
                for caso in ex.get('casos_de_teste', []):
                    inputs = {nome: caso.get(nome, 0) for nome in ex.get('inputs', [])}
                    output_val = caso.get(output_key, 0)
                    casos_dict.append({
                        'inputs': inputs,
                        'output_esperado': {'valor': output_val},
                    })

                resultado = avaliador.avaliar_submissao(funcao_dict, casos_dict, codigo)
                resultados.append(resultado)

            return jsonify({
                'sucesso': all(r['casos_passados'] == r['total_casos'] for r in resultados),
                'resultados': resultados,
            }), 200

        except Exception as e:
            logger.error("Erro no endpoint legado: %s", e, exc_info=True)
            return jsonify({'erro': str(e)}), 500

    @app.route('/api/exercicios/exemplo', methods=['GET'])
    def exercicio_exemplo():
        """Retorna exemplo para testar."""
        exemplo = {
            'funcao': {
                'nome_funcao': 'fatorial',
                'parametros': [{'nome': 'n', 'tipo': 'int'}],
                'retorno': {'tipo': 'int'},
                'pontos': 10,
            },
            'casos_teste': [
                {'inputs': {'n': 0}, 'output_esperado': {'valor': 1}, 'descricao': '0! = 1'},
                {'inputs': {'n': 1}, 'output_esperado': {'valor': 1}, 'descricao': '1! = 1'},
                {'inputs': {'n': 5}, 'output_esperado': {'valor': 120}, 'descricao': '5! = 120'},
                {'inputs': {'n': 10}, 'output_esperado': {'valor': 3628800}, 'descricao': '10! = 3628800'},
            ],
            'codigo_exemplo': 'int fatorial(int n) {\n    if (n <= 1) return 1;\n    return n * fatorial(n - 1);\n}',
        }
        return jsonify(exemplo), 200

    return app


# ---- Entrypoint ----

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

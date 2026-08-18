"""
Modelos SQLAlchemy para o sistema de avaliação automática.

Tabelas:
    - funcoes: definição de funções C a serem implementadas pelos alunos
    - casos_teste: casos de teste vinculados a uma função
    - submissoes: submissões de código com resultado da avaliação
"""

import uuid
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _uuid():
    return str(uuid.uuid4())


class Funcao(db.Model):
    """Representa uma função C que o aluno deve implementar."""
    __tablename__ = 'funcoes'

    uuid = db.Column(db.String(36), primary_key=True, default=_uuid)
    nome_funcao = db.Column(db.String(128), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    parametros = db.Column(db.JSON, nullable=False, default=list)
    retorno = db.Column(db.JSON, nullable=False, default=dict)
    pontos = db.Column(db.Integer, nullable=False, default=10)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # Relacionamentos
    casos_teste = db.relationship(
        'CasoTeste',
        backref='funcao',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    submissoes = db.relationship(
        'Submissao',
        backref='funcao',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def to_dict(self, include_casos=False):
        data = {
            'uuid': self.uuid,
            'nome_funcao': self.nome_funcao,
            'descricao': self.descricao,
            'parametros': self.parametros,
            'retorno': self.retorno,
            'pontos': self.pontos,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_casos:
            data['casos_teste'] = [c.to_dict() for c in self.casos_teste.all()]
        return data

    def __repr__(self):
        return f'<Funcao {self.nome_funcao}>'


class CasoTeste(db.Model):
    """Caso de teste vinculado a uma função."""
    __tablename__ = 'casos_teste'

    uuid = db.Column(db.String(36), primary_key=True, default=_uuid)
    funcao_uuid = db.Column(
        db.String(36),
        db.ForeignKey('funcoes.uuid', ondelete='CASCADE'),
        nullable=False
    )
    inputs = db.Column(db.JSON, nullable=False, default=dict)
    output_esperado = db.Column(db.JSON, nullable=False, default=dict)
    descricao = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self):
        return {
            'uuid': self.uuid,
            'funcao_uuid': self.funcao_uuid,
            'inputs': self.inputs,
            'output_esperado': self.output_esperado,
            'descricao': self.descricao,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<CasoTeste {self.uuid[:8]}>'


class Submissao(db.Model):
    """Submissão de código de um aluno com resultado da avaliação."""
    __tablename__ = 'submissoes'

    uuid = db.Column(db.String(36), primary_key=True, default=_uuid)
    funcao_uuid = db.Column(
        db.String(36),
        db.ForeignKey('funcoes.uuid'),
        nullable=False
    )
    codigo_submetido = db.Column(db.Text, nullable=False)
    data_submissao = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    status = db.Column(db.String(32), nullable=False, default='avaliando')
    nota = db.Column(db.Float, nullable=True)
    resultado_json = db.Column(db.JSON, nullable=True)

    def to_dict(self):
        return {
            'uuid': self.uuid,
            'funcao_uuid': self.funcao_uuid,
            'codigo_submetido': self.codigo_submetido,
            'data_submissao': self.data_submissao.isoformat() if self.data_submissao else None,
            'status': self.status,
            'nota': self.nota,
            'resultado_json': self.resultado_json,
        }

    def __repr__(self):
        return f'<Submissao {self.uuid[:8]} status={self.status}>'

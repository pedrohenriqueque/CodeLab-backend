
import os
from app import create_app
from models import db, Funcao, Submissao

app = create_app()
with app.app_context():
    print(f"Funcoes: {Funcao.query.count()}")
    print(f"Submissoes: {Submissao.query.count()}")

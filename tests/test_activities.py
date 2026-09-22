import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4
from backend_v2.app.core.exceptions import CodelabException
from backend_v2.app.models.usuario import PerfilUsuario
from backend_v2.app.schemas.atividade import CriarAtividadeRequest
from backend_v2.app.services.activity_service import criar_atividade

class ActivityTests(unittest.TestCase):
 def test_only_owner_professor_creates_draft(self):
  professor=SimpleNamespace(uuid=uuid4(),perfil=PerfilUsuario.PROFESSOR)
  turma=SimpleNamespace(professor_uuid=professor.uuid)
  now=datetime.now(timezone.utc); db=Mock(); db.get=AsyncMock(return_value=turma); db.commit=AsyncMock(); db.refresh=AsyncMock()
  activity=asyncio.run(criar_atividade(CriarAtividadeRequest(turmaUuid=uuid4(),titulo="Lista",inicioEm=now,fimEm=now+timedelta(days=1)),professor,db))
  self.assertEqual(activity.status,"RASCUNHO"); db.commit.assert_awaited_once()
 def test_rejects_invalid_dates(self):
  now=datetime.now(timezone.utc)
  with self.assertRaises(Exception): CriarAtividadeRequest(turmaUuid=uuid4(),titulo="Lista",inicioEm=now,fimEm=now)
 def test_other_professor_cannot_create(self):
  professor=SimpleNamespace(uuid=uuid4(),perfil=PerfilUsuario.PROFESSOR); db=Mock(); db.get=AsyncMock(return_value=SimpleNamespace(professor_uuid=uuid4()))
  now=datetime.now(timezone.utc)
  with self.assertRaisesRegex(CodelabException,"não gerencia"): asyncio.run(criar_atividade(CriarAtividadeRequest(turmaUuid=uuid4(),titulo="Lista",inicioEm=now,fimEm=now+timedelta(days=1)),professor,db))

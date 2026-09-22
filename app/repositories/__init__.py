"""Repositórios de acesso aos dados da aplicação."""

from .user_repository import UserRepository
from .class_repository import ClassRepository
from .enrollment_repository import EnrollmentRepository
from .function_repository import FunctionRepository
from .test_case_repository import TestCaseRepository
from .activity_repository import ActivityRepository

__all__ = ["UserRepository", "ClassRepository", "EnrollmentRepository", "FunctionRepository", "TestCaseRepository", "ActivityRepository"]

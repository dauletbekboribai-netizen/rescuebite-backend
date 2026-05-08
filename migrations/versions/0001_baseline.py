"""baseline schema

Revision ID: 0001_baseline
Revises:
Create Date: 2026-04-13
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from alembic import op
from sqlmodel import SQLModel
from app.models import domain  # noqa: F401

revision = '0001_baseline'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.drop_all(bind)

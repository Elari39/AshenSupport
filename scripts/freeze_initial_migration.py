"""Only for initial development. Never regenerate after a release."""
import sys
from pathlib import Path
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import postgresql, sqlite

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.db import Base

ddl={}
for name,dialect in [('sqlite',sqlite.dialect()),('postgresql',postgresql.dialect())]:
    commands=[]
    if name=='postgresql':
        commands.append('CREATE EXTENSION IF NOT EXISTS vector')
    for table in Base.metadata.sorted_tables:
        commands.append(str(CreateTable(table).compile(dialect=dialect)))
        commands.extend(str(CreateIndex(index).compile(dialect=dialect)) for index in sorted(table.indexes,key=lambda i:i.name))
    ddl[name]=commands
tables=[table.name for table in reversed(Base.metadata.sorted_tables)]
source='''"""Frozen initial DDL. Future changes require new numbered migrations."""
from alembic import op
revision = "0001"
down_revision = None
DDL = '''+repr(ddl)+'''
TABLES = '''+repr(tables)+'''

def upgrade():
    for statement in DDL[op.get_bind().dialect.name]:
        op.execute(statement)

def downgrade():
    for table in TABLES:
        op.drop_table(table)
'''
(ROOT/'backend/alembic/versions/0001_initial.py').write_text(source,encoding='utf-8')

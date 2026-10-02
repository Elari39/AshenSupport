"""Frozen initial DDL. Future changes require new numbered migrations."""

from alembic import op

revision = "0001"
down_revision = None
DDL = {
    "sqlite": [
        "\nCREATE TABLE projects (\n\tid VARCHAR NOT NULL, \n\tname VARCHAR(100) NOT NULL, \n\tdescription TEXT NOT NULL, \n\tPRIMARY KEY (id)\n)\n\n",
        '\nCREATE TABLE quota_counters (\n\t"key" VARCHAR(200) NOT NULL, \n\tcount INTEGER NOT NULL, \n\tPRIMARY KEY ("key")\n)\n\n',
        "\nCREATE TABLE usage_records (\n\tid VARCHAR NOT NULL, \n\ttask_id VARCHAR(32), \n\tkind VARCHAR(30) NOT NULL, \n\tmodel VARCHAR(200) NOT NULL, \n\tsuccess BOOLEAN NOT NULL, \n\tinput_tokens INTEGER, \n\toutput_tokens INTEGER, \n\telapsed_ms INTEGER NOT NULL, \n\tcost FLOAT, \n\tcreated_at DATETIME NOT NULL, \n\tPRIMARY KEY (id)\n)\n\n",
        "\nCREATE TABLE users (\n\tid VARCHAR NOT NULL, \n\tusername VARCHAR(80) NOT NULL, \n\tpassword_hash TEXT NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (username)\n)\n\n",
        "\nCREATE TABLE documents (\n\tid VARCHAR NOT NULL, \n\tproject_id VARCHAR NOT NULL, \n\tlogical_key VARCHAR(200) NOT NULL, \n\tactive_version VARCHAR(32), \n\tenabled BOOLEAN NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (project_id, logical_key), \n\tFOREIGN KEY(project_id) REFERENCES projects (id)\n)\n\n",
        "\nCREATE TABLE sessions (\n\tid VARCHAR NOT NULL, \n\ttoken_hash VARCHAR(64) NOT NULL, \n\tcsrf VARCHAR(80) NOT NULL, \n\tuser_id VARCHAR, \n\texpires_at DATETIME NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (token_hash), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)\n\n",
        "\nCREATE TABLE document_versions (\n\tid VARCHAR NOT NULL, \n\tdocument_id VARCHAR NOT NULL, \n\tlabel VARCHAR(200) NOT NULL, \n\tsource TEXT NOT NULL, \n\tcontent TEXT NOT NULL, \n\tcontent_hash VARCHAR(64) NOT NULL, \n\tembedding_id VARCHAR(200) NOT NULL, \n\tconfig JSON NOT NULL, \n\tstatus VARCHAR(30) NOT NULL, \n\terror TEXT, \n\tcreated_at DATETIME NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (document_id, content_hash, embedding_id), \n\tFOREIGN KEY(document_id) REFERENCES documents (id)\n)\n\n",
        "\nCREATE TABLE tasks (\n\tid VARCHAR NOT NULL, \n\tsession_id VARCHAR NOT NULL, \n\tproject_id VARCHAR NOT NULL, \n\ttitle VARCHAR(120) NOT NULL, \n\tmode VARCHAR(20) NOT NULL, \n\tscenario VARCHAR(60) NOT NULL, \n\ttarget_id VARCHAR(100), \n\tstatus VARCHAR(30) NOT NULL, \n\tclarification_count INTEGER NOT NULL, \n\tresult JSON, \n\tcreated_at DATETIME NOT NULL, \n\tupdated_at DATETIME NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(session_id) REFERENCES sessions (id), \n\tFOREIGN KEY(project_id) REFERENCES projects (id)\n)\n\n",
        "CREATE INDEX ix_tasks_session_id ON tasks (session_id)",
        "CREATE INDEX ix_tasks_status ON tasks (status)",
        "\nCREATE TABLE chunks (\n\tid VARCHAR NOT NULL, \n\tversion_id VARCHAR NOT NULL, \n\tcontent TEXT NOT NULL, \n\theading TEXT NOT NULL, \n\tline_start INTEGER NOT NULL, \n\tline_end INTEGER NOT NULL, \n\tvector JSON NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(version_id) REFERENCES document_versions (id)\n)\n\n",
        "CREATE INDEX ix_chunks_version_id ON chunks (version_id)",
        "\nCREATE TABLE citations (\n\tid VARCHAR NOT NULL, \n\ttask_id VARCHAR NOT NULL, \n\tchunk_id VARCHAR(32) NOT NULL, \n\tsnapshot JSON NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(task_id) REFERENCES tasks (id)\n)\n\n",
        "CREATE INDEX ix_citations_task_id ON citations (task_id)",
        "\nCREATE TABLE messages (\n\tid VARCHAR NOT NULL, \n\ttask_id VARCHAR NOT NULL, \n\trole VARCHAR(20) NOT NULL, \n\tcontent TEXT NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(task_id) REFERENCES tasks (id)\n)\n\n",
        "CREATE INDEX ix_messages_task_id ON messages (task_id)",
        "\nCREATE TABLE task_events (\n\tid INTEGER NOT NULL, \n\ttask_id VARCHAR NOT NULL, \n\tkind VARCHAR(60) NOT NULL, \n\tpayload JSON NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(task_id) REFERENCES tasks (id)\n)\n\n",
        "CREATE INDEX ix_task_events_task_id ON task_events (task_id)",
        "\nCREATE TABLE task_runs (\n\tid VARCHAR NOT NULL, \n\ttask_id VARCHAR NOT NULL, \n\tstatus VARCHAR(30) NOT NULL, \n\towner VARCHAR(32), \n\tlease_until DATETIME, \n\tattempts INTEGER NOT NULL, \n\terror TEXT, \n\tretryable BOOLEAN NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tstarted_at DATETIME, \n\tfinished_at DATETIME, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(task_id) REFERENCES tasks (id)\n)\n\n",
        "CREATE INDEX ix_task_runs_status ON task_runs (status)",
        "CREATE INDEX ix_task_runs_task_id ON task_runs (task_id)",
        "\nCREATE TABLE ticket_drafts (\n\tid VARCHAR NOT NULL, \n\ttask_id VARCHAR NOT NULL, \n\tversion INTEGER NOT NULL, \n\ttitle VARCHAR(120) NOT NULL, \n\tdescription TEXT NOT NULL, \n\tevidence JSON NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (task_id), \n\tFOREIGN KEY(task_id) REFERENCES tasks (id)\n)\n\n",
        "\nCREATE TABLE approvals (\n\tid VARCHAR NOT NULL, \n\tdraft_id VARCHAR NOT NULL, \n\tversion INTEGER NOT NULL, \n\tdecision VARCHAR(20) NOT NULL, \n\tsession_id VARCHAR(32) NOT NULL, \n\tidempotency_key VARCHAR(100) NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (draft_id, version), \n\tFOREIGN KEY(draft_id) REFERENCES ticket_drafts (id)\n)\n\n",
        '\nCREATE TABLE steps (\n\tid VARCHAR NOT NULL, \n\trun_id VARCHAR NOT NULL, \n\t"key" VARCHAR(80) NOT NULL, \n\tresult JSON NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (run_id, "key"), \n\tFOREIGN KEY(run_id) REFERENCES task_runs (id)\n)\n\n',
        "\nCREATE TABLE tickets (\n\tid VARCHAR NOT NULL, \n\tdraft_id VARCHAR NOT NULL, \n\ttask_id VARCHAR NOT NULL, \n\tsession_id VARCHAR NOT NULL, \n\tproject_id VARCHAR(50) NOT NULL, \n\ttitle VARCHAR(120) NOT NULL, \n\tdescription TEXT NOT NULL, \n\tevidence JSON NOT NULL, \n\tsandbox BOOLEAN NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (draft_id), \n\tFOREIGN KEY(draft_id) REFERENCES ticket_drafts (id), \n\tFOREIGN KEY(task_id) REFERENCES tasks (id), \n\tFOREIGN KEY(session_id) REFERENCES sessions (id)\n)\n\n",
    ],
    "postgresql": [
        "CREATE EXTENSION IF NOT EXISTS vector",
        "\nCREATE TABLE projects (\n\tid VARCHAR NOT NULL, \n\tname VARCHAR(100) NOT NULL, \n\tdescription TEXT NOT NULL, \n\tPRIMARY KEY (id)\n)\n\n",
        "\nCREATE TABLE quota_counters (\n\tkey VARCHAR(200) NOT NULL, \n\tcount INTEGER NOT NULL, \n\tPRIMARY KEY (key)\n)\n\n",
        "\nCREATE TABLE usage_records (\n\tid VARCHAR NOT NULL, \n\ttask_id VARCHAR(32), \n\tkind VARCHAR(30) NOT NULL, \n\tmodel VARCHAR(200) NOT NULL, \n\tsuccess BOOLEAN NOT NULL, \n\tinput_tokens INTEGER, \n\toutput_tokens INTEGER, \n\telapsed_ms INTEGER NOT NULL, \n\tcost FLOAT, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id)\n)\n\n",
        "\nCREATE TABLE users (\n\tid VARCHAR NOT NULL, \n\tusername VARCHAR(80) NOT NULL, \n\tpassword_hash TEXT NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (username)\n)\n\n",
        "\nCREATE TABLE documents (\n\tid VARCHAR NOT NULL, \n\tproject_id VARCHAR NOT NULL, \n\tlogical_key VARCHAR(200) NOT NULL, \n\tactive_version VARCHAR(32), \n\tenabled BOOLEAN NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (project_id, logical_key), \n\tFOREIGN KEY(project_id) REFERENCES projects (id)\n)\n\n",
        "\nCREATE TABLE sessions (\n\tid VARCHAR NOT NULL, \n\ttoken_hash VARCHAR(64) NOT NULL, \n\tcsrf VARCHAR(80) NOT NULL, \n\tuser_id VARCHAR, \n\texpires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (token_hash), \n\tFOREIGN KEY(user_id) REFERENCES users (id)\n)\n\n",
        "\nCREATE TABLE document_versions (\n\tid VARCHAR NOT NULL, \n\tdocument_id VARCHAR NOT NULL, \n\tlabel VARCHAR(200) NOT NULL, \n\tsource TEXT NOT NULL, \n\tcontent TEXT NOT NULL, \n\tcontent_hash VARCHAR(64) NOT NULL, \n\tembedding_id VARCHAR(200) NOT NULL, \n\tconfig JSON NOT NULL, \n\tstatus VARCHAR(30) NOT NULL, \n\terror TEXT, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (document_id, content_hash, embedding_id), \n\tFOREIGN KEY(document_id) REFERENCES documents (id)\n)\n\n",
        "\nCREATE TABLE tasks (\n\tid VARCHAR NOT NULL, \n\tsession_id VARCHAR NOT NULL, \n\tproject_id VARCHAR NOT NULL, \n\ttitle VARCHAR(120) NOT NULL, \n\tmode VARCHAR(20) NOT NULL, \n\tscenario VARCHAR(60) NOT NULL, \n\ttarget_id VARCHAR(100), \n\tstatus VARCHAR(30) NOT NULL, \n\tclarification_count INTEGER NOT NULL, \n\tresult JSON, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(session_id) REFERENCES sessions (id), \n\tFOREIGN KEY(project_id) REFERENCES projects (id)\n)\n\n",
        "CREATE INDEX ix_tasks_session_id ON tasks (session_id)",
        "CREATE INDEX ix_tasks_status ON tasks (status)",
        "\nCREATE TABLE chunks (\n\tid VARCHAR NOT NULL, \n\tversion_id VARCHAR NOT NULL, \n\tcontent TEXT NOT NULL, \n\theading TEXT NOT NULL, \n\tline_start INTEGER NOT NULL, \n\tline_end INTEGER NOT NULL, \n\tvector VECTOR NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(version_id) REFERENCES document_versions (id)\n)\n\n",
        "CREATE INDEX ix_chunks_version_id ON chunks (version_id)",
        "\nCREATE TABLE citations (\n\tid VARCHAR NOT NULL, \n\ttask_id VARCHAR NOT NULL, \n\tchunk_id VARCHAR(32) NOT NULL, \n\tsnapshot JSON NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(task_id) REFERENCES tasks (id)\n)\n\n",
        "CREATE INDEX ix_citations_task_id ON citations (task_id)",
        "\nCREATE TABLE messages (\n\tid VARCHAR NOT NULL, \n\ttask_id VARCHAR NOT NULL, \n\trole VARCHAR(20) NOT NULL, \n\tcontent TEXT NOT NULL, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(task_id) REFERENCES tasks (id)\n)\n\n",
        "CREATE INDEX ix_messages_task_id ON messages (task_id)",
        "\nCREATE TABLE task_events (\n\tid SERIAL NOT NULL, \n\ttask_id VARCHAR NOT NULL, \n\tkind VARCHAR(60) NOT NULL, \n\tpayload JSON NOT NULL, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(task_id) REFERENCES tasks (id)\n)\n\n",
        "CREATE INDEX ix_task_events_task_id ON task_events (task_id)",
        "\nCREATE TABLE task_runs (\n\tid VARCHAR NOT NULL, \n\ttask_id VARCHAR NOT NULL, \n\tstatus VARCHAR(30) NOT NULL, \n\towner VARCHAR(32), \n\tlease_until TIMESTAMP WITHOUT TIME ZONE, \n\tattempts INTEGER NOT NULL, \n\terror TEXT, \n\tretryable BOOLEAN NOT NULL, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tstarted_at TIMESTAMP WITHOUT TIME ZONE, \n\tfinished_at TIMESTAMP WITHOUT TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(task_id) REFERENCES tasks (id)\n)\n\n",
        "CREATE INDEX ix_task_runs_status ON task_runs (status)",
        "CREATE INDEX ix_task_runs_task_id ON task_runs (task_id)",
        "\nCREATE TABLE ticket_drafts (\n\tid VARCHAR NOT NULL, \n\ttask_id VARCHAR NOT NULL, \n\tversion INTEGER NOT NULL, \n\ttitle VARCHAR(120) NOT NULL, \n\tdescription TEXT NOT NULL, \n\tevidence JSON NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (task_id), \n\tFOREIGN KEY(task_id) REFERENCES tasks (id)\n)\n\n",
        "\nCREATE TABLE approvals (\n\tid VARCHAR NOT NULL, \n\tdraft_id VARCHAR NOT NULL, \n\tversion INTEGER NOT NULL, \n\tdecision VARCHAR(20) NOT NULL, \n\tsession_id VARCHAR(32) NOT NULL, \n\tidempotency_key VARCHAR(100) NOT NULL, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (draft_id, version), \n\tFOREIGN KEY(draft_id) REFERENCES ticket_drafts (id)\n)\n\n",
        "\nCREATE TABLE steps (\n\tid VARCHAR NOT NULL, \n\trun_id VARCHAR NOT NULL, \n\tkey VARCHAR(80) NOT NULL, \n\tresult JSON NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (run_id, key), \n\tFOREIGN KEY(run_id) REFERENCES task_runs (id)\n)\n\n",
        "\nCREATE TABLE tickets (\n\tid VARCHAR NOT NULL, \n\tdraft_id VARCHAR NOT NULL, \n\ttask_id VARCHAR NOT NULL, \n\tsession_id VARCHAR NOT NULL, \n\tproject_id VARCHAR(50) NOT NULL, \n\ttitle VARCHAR(120) NOT NULL, \n\tdescription TEXT NOT NULL, \n\tevidence JSON NOT NULL, \n\tsandbox BOOLEAN NOT NULL, \n\tstatus VARCHAR(20) NOT NULL, \n\tcreated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (draft_id), \n\tFOREIGN KEY(draft_id) REFERENCES ticket_drafts (id), \n\tFOREIGN KEY(task_id) REFERENCES tasks (id), \n\tFOREIGN KEY(session_id) REFERENCES sessions (id)\n)\n\n",
    ],
}
TABLES = [
    "tickets",
    "steps",
    "approvals",
    "ticket_drafts",
    "task_runs",
    "task_events",
    "messages",
    "citations",
    "chunks",
    "tasks",
    "document_versions",
    "sessions",
    "documents",
    "users",
    "usage_records",
    "quota_counters",
    "projects",
]


def upgrade():
    for statement in DDL[op.get_bind().dialect.name]:
        op.execute(statement)


def downgrade():
    for table in TABLES:
        op.drop_table(table)

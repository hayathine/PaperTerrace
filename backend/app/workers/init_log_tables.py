"""
ログ用 PostgreSQL テーブル初期化スクリプト（vostro ポッド）。
BigQuery の init_bigquery_tables.py を置き換える。

Usage:
    python -m app.workers.init_log_tables [--env prod|staging|local]
"""

import argparse
import sys

from sqlalchemy import create_engine, text

from app.core.config import get_app_env, get_log_database_url, get_log_schema

DDL_TEMPLATE = """
CREATE SCHEMA IF NOT EXISTS {schema};

CREATE TABLE IF NOT EXISTS {schema}.dspy_traces (
    trace_id        TEXT PRIMARY KEY,
    module_name     TEXT NOT NULL,
    signature       TEXT NOT NULL,
    inputs          TEXT,
    outputs         TEXT,
    user_id         TEXT,
    session_id      TEXT,
    paper_id        TEXT,
    model_name      TEXT,
    latency_ms      INTEGER,
    is_success      BOOLEAN,
    is_copied       BOOLEAN DEFAULT FALSE,
    error_msg       TEXT,
    comment         TEXT,
    prompt          TEXT,
    answer          TEXT,
    candidate_index INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_dspy_traces_session
    ON {schema}.dspy_traces (session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dspy_traces_module
    ON {schema}.dspy_traces (module_name, created_at DESC);

CREATE TABLE IF NOT EXISTS {schema}.trajectories (
    session_id           TEXT PRIMARY KEY,
    user_id              TEXT NOT NULL,
    paper_id             TEXT,
    paper_title          TEXT,
    paper_abstract       TEXT,
    paper_keywords       TEXT,
    paper_difficulty     TEXT,
    conversation_history TEXT,
    word_clicks          TEXT,
    copy_events          TEXT,
    session_duration     INTEGER,
    followed_up_query    TEXT,
    knowledge_level      TEXT,
    interests            TEXT,
    unknown_concepts     TEXT,
    preferred_direction  TEXT,
    clicked_papers       TEXT,
    recommended_papers   TEXT,
    timestamp            TIMESTAMPTZ,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_trajectories_user
    ON {schema}.trajectories (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS {schema}.feedback (
    feedback_id  TEXT PRIMARY KEY,
    session_id   TEXT,
    user_id      TEXT NOT NULL,
    target_type  TEXT NOT NULL,
    target_id    TEXT,
    trace_id     TEXT,
    user_score   INTEGER,
    user_comment TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_feedback_trace
    ON {schema}.feedback (trace_id);

CREATE TABLE IF NOT EXISTS {schema}.client_error_logs (
    error_id   TEXT PRIMARY KEY,
    message    TEXT NOT NULL,
    component  TEXT NOT NULL,
    operation  TEXT NOT NULL,
    user_id    TEXT,
    error_name TEXT,
    stack      TEXT,
    context    TEXT,
    url        TEXT,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS {schema}.user_engagements (
    user_pseudo_id             TEXT NOT NULL,
    firebase_uid               TEXT,
    event_date                 DATE NOT NULL,
    total_engagement_seconds   FLOAT DEFAULT 0,
    page_views                 INTEGER DEFAULT 0,
    session_count              INTEGER DEFAULT 0,
    max_scroll_depth           INTEGER,
    synced_at                  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_pseudo_id, event_date)
);

CREATE TABLE IF NOT EXISTS {schema}.page_view_logs (
    user_pseudo_id           TEXT NOT NULL,
    firebase_uid             TEXT,
    ga_session_id            TEXT,
    event_timestamp          TIMESTAMPTZ NOT NULL,
    page_location            TEXT,
    page_title               TEXT,
    page_referrer            TEXT,
    engagement_time_seconds  FLOAT DEFAULT 0,
    is_entrance              INTEGER,
    event_date               DATE NOT NULL,
    synced_at                TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_page_view_logs_date
    ON {schema}.page_view_logs (event_date DESC);

CREATE TABLE IF NOT EXISTS {schema}.paper_likes (
    event_id   TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    paper_id   TEXT NOT NULL,
    action     TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_paper_likes_paper
    ON {schema}.paper_likes (paper_id, created_at DESC);

CREATE TABLE IF NOT EXISTS {schema}.prompt_candidates (
    optimization_id TEXT NOT NULL,
    program_name    TEXT NOT NULL,
    candidate_index INTEGER NOT NULL,
    module_state    TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (optimization_id, candidate_index)
);
CREATE INDEX IF NOT EXISTS idx_prompt_candidates_lookup
    ON {schema}.prompt_candidates (program_name, created_at DESC);
"""


def main():
    parser = argparse.ArgumentParser(
        description="ログ用 PostgreSQL テーブルを初期化する"
    )
    parser.add_argument(
        "--env",
        choices=["prod", "staging", "local"],
        default=None,
        help="環境を明示する場合に指定（省略時は APP_ENV 設定値を使用）",
    )
    args = parser.parse_args()

    if args.env:
        import os
        os.environ["APP_ENV"] = args.env

    env = get_app_env()
    try:
        url = get_log_database_url()
    except RuntimeError as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(1)

    schema = get_log_schema()
    ddl = DDL_TEMPLATE.format(schema=schema)

    print(f"Initializing log tables (env={env}, schema={schema})")
    print(f"  URL: {url[:url.index('@') + 1]}***")  # パスワードを隠す

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            for statement in ddl.strip().split(";"):
                stmt = statement.strip()
                if stmt:
                    conn.execute(text(stmt))
            conn.commit()
        print("✓ All log tables initialized successfully")
    except Exception as e:
        print(f"✗ Failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

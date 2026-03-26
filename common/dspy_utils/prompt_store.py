"""
PostgreSQL ベースの DSPy プロンプト候補ストア。

GEPA が生成した Pareto フロント候補群を PostgreSQL の logs.prompt_candidates テーブルで管理し、
推論時には最新の最適化ランから候補をロードしてランダムに選択できるようにする。

テーブルスキーマ (DDL):
    CREATE TABLE logs.prompt_candidates (
        optimization_id TEXT NOT NULL,
        program_name    TEXT NOT NULL,
        candidate_index INTEGER NOT NULL,
        module_state    TEXT NOT NULL,
        created_at      TIMESTAMPTZ DEFAULT NOW(),
        PRIMARY KEY (optimization_id, candidate_index)
    );
    CREATE INDEX ON logs.prompt_candidates (program_name, created_at DESC);
"""

from __future__ import annotations

import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

import dspy
from common.logger import get_logger

log = get_logger(__name__)

if TYPE_CHECKING:
    pass

_TABLE = "prompt_candidates"


# ---------------------------------------------------------------------------
# PostgreSQL クライアント取得（backend / prompt_optimization 両対応）
# ---------------------------------------------------------------------------


class _StandalonePgClient:
    """psycopg2 ベースの軽量 PostgreSQL クライアント。

    prompt_optimization など backend 外で動作する文脈向け。
    backend 内では PgLogClient シングルトンを使う。
    """

    def __init__(self) -> None:
        import psycopg2  # type: ignore[import]

        self._url = os.getenv("LOG_DATABASE_URL")
        if not self._url:
            raise RuntimeError("LOG_DATABASE_URL が設定されていません")
        # 接続確認
        conn = psycopg2.connect(self._url)
        conn.close()

    def _connect(self):
        import psycopg2
        from psycopg2.extras import RealDictCursor  # type: ignore[import]

        return psycopg2.connect(self._url, cursor_factory=RealDictCursor)

    @staticmethod
    def _convert_params(sql: str, params: dict | None) -> tuple[str, dict]:
        """:name 形式を %(name)s 形式に変換する（psycopg2 向け）。"""
        if not params:
            return sql, {}
        new_sql = re.sub(r":(\w+)", r"%(\1)s", sql)
        return new_sql, params

    def insert(self, table: str, rows: list[dict]) -> None:
        if not rows:
            return
        cols = list(rows[0].keys())
        col_str = ", ".join(cols)
        placeholders = ", ".join(f"%({c})s" for c in cols)
        sql = f"INSERT INTO logs.{table} ({col_str}) VALUES ({placeholders})"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, rows)
            conn.commit()

    def query(self, sql: str, params: dict | None = None) -> list[dict]:
        pg_sql, pg_params = self._convert_params(sql, params)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(pg_sql, pg_params or {})
                return [dict(row) for row in cur.fetchall()]

    def query_one(self, sql: str, params: dict | None = None) -> dict | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None


def _get_pg_client():
    """backend では PgLogClient シングルトン、それ以外は _StandalonePgClient を返す。"""
    try:
        from app.providers.pg_log import PgLogClient  # type: ignore[import]

        return PgLogClient.get_instance()
    except ImportError:
        return _StandalonePgClient()


# ---------------------------------------------------------------------------
# モジュールのシリアライズ / デシリアライズ
# ---------------------------------------------------------------------------


def _serialize_module(module: dspy.Module) -> str:
    """dspy.Module を JSON 文字列にシリアライズする（tempfile 経由）。"""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = f.name
    try:
        module.save(tmp_path)
        with open(tmp_path, encoding="utf-8") as f:
            return f.read()
    finally:
        os.unlink(tmp_path)


def _deserialize_module(module: dspy.Module, state_json: str) -> dspy.Module:
    """JSON 文字列から dspy.Module の状態を復元する（tempfile 経由）。"""
    with tempfile.NamedTemporaryFile(
        suffix=".json", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(state_json)
        tmp_path = f.name
    try:
        module.load(tmp_path)
    finally:
        os.unlink(tmp_path)
    return module


# ---------------------------------------------------------------------------
# パブリック API
# ---------------------------------------------------------------------------


def save_candidates_to_bigquery(
    program_name: str,
    candidates: list[dspy.Module],
) -> str:
    """Pareto 候補群を logs.prompt_candidates テーブルに保存する。

    Args:
        program_name: モジュール識別子（例: 'paper_summary'）。
        candidates: GEPA Pareto フロントから抽出した dspy.Module のリスト。

    Returns:
        今回の最適化ランを表す optimization_id（UUID）。
    """
    pg = _get_pg_client()
    optimization_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    rows = [
        {
            "optimization_id": optimization_id,
            "program_name": program_name,
            "candidate_index": i,
            "module_state": _serialize_module(candidate),
            "created_at": created_at,
        }
        for i, candidate in enumerate(candidates)
    ]

    pg.insert(_TABLE, rows)
    log.info(
        "save_candidates",
        "Saved candidates to PostgreSQL",
        program_name=program_name,
        count=len(rows),
        optimization_id=optimization_id,
    )
    return optimization_id


def load_candidates_from_bigquery(
    module_factory: Callable[[], dspy.Module],
    program_name: str,
) -> list[dspy.Module]:
    """logs.prompt_candidates から最新の Pareto 候補群をロードして返す。

    最新の optimization_id（created_at 降順の先頭）に紐づく全候補を取得し、
    それぞれを dspy.Module としてデシリアライズして返す。
    候補が存在しない・全てのデシリアライズに失敗した場合は
    module_factory() によるデフォルトモジュールを返す。

    Args:
        module_factory: 新規モジュールインスタンスを生成する callable。
        program_name: モジュール識別子（例: 'paper_summary'）。

    Returns:
        ロード済みの dspy.Module のリスト（最低1件）。
    """
    pg = _get_pg_client()

    # 最新の optimization_id を取得
    row = pg.query_one(
        "SELECT optimization_id FROM logs.prompt_candidates "
        "WHERE program_name = :program_name "
        "ORDER BY created_at DESC LIMIT 1",
        {"program_name": program_name},
    )

    if not row:
        log.warning(
            "load_candidates",
            "No candidates found, using default module",
            program_name=program_name,
        )
        return [module_factory()]

    optimization_id: str = row["optimization_id"]

    rows = pg.query(
        "SELECT candidate_index, module_state FROM logs.prompt_candidates "
        "WHERE program_name = :program_name AND optimization_id = :optimization_id "
        "ORDER BY candidate_index ASC",
        {"program_name": program_name, "optimization_id": optimization_id},
    )

    modules: list[dspy.Module] = []
    for r in rows:
        try:
            mod = _deserialize_module(module_factory(), r["module_state"])
            modules.append(mod)
        except Exception as e:
            log.warning(
                "load_candidates",
                "Failed to deserialize candidate",
                program_name=program_name,
                candidate_index=r["candidate_index"],
                error=str(e),
            )

    if not modules:
        log.warning(
            "load_candidates",
            "All candidates failed to deserialize, using default module",
            program_name=program_name,
        )
        return [module_factory()]

    log.info(
        "load_candidates",
        "Loaded candidates",
        program_name=program_name,
        count=len(modules),
        optimization_id=optimization_id,
    )
    return modules

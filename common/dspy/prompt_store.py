"""
BigQuery ベースの DSPy プロンプト候補ストア。

GEPA が生成した Pareto フロント候補群を BigQuery の prompt_candidates テーブルで管理し、
推論時には最新の最適化ランから候補をロードしてランダムに選択できるようにする。

テーブルスキーマ (DDL):
    CREATE TABLE `{project}.{dataset}.prompt_candidates` (
        optimization_id STRING NOT NULL,  -- 最適化ラン単位の UUID
        program_name    STRING NOT NULL,  -- モジュール識別子 (例: 'user_persona')
        candidate_index INT64  NOT NULL,  -- Pareto フロント内の順序 (0-based)
        module_state    STRING NOT NULL,  -- dspy.Module をシリアライズした JSON
        created_at      TIMESTAMP NOT NULL
    )
    PARTITION BY DATE(created_at)
    CLUSTER BY program_name, optimization_id;
"""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

import dspy

if TYPE_CHECKING:
    pass

_BQ_TABLE = "prompt_candidates"


# ---------------------------------------------------------------------------
# BigQuery クライアント取得（backend / prompt_optimization 両対応）
# ---------------------------------------------------------------------------

def _get_dataset_id() -> str:
    """APP_ENV に応じた BigQuery データセット名を返す。"""
    env = os.getenv("APP_ENV", "local").lower()
    if env in ("prod", "production"):
        return os.getenv("BQ_LOG_DATASET", "paperterrace_logs")
    if env == "staging":
        return os.getenv("BQ_LOG_DATASET_STAGING", "paperterrace_logs_staging")
    return os.getenv("BQ_LOG_DATASET_LOCAL", "paperterrace_logs_local")


class _StandaloneClient:
    """BigQueryLogClient と同インタフェースの軽量クライアント。

    prompt_optimization など backend 外で動作する文脈向け。
    """

    def __init__(self) -> None:
        from google.cloud import bigquery  # type: ignore[import-untyped]

        self.project_id = os.getenv("GCP_PROJECT_ID", "gen-lang-client-0800253336")
        self.dataset_id = _get_dataset_id()
        self._bq = bigquery.Client(project=self.project_id)

    def table_ref(self, table_name: str) -> str:
        return f"{self.project_id}.{self.dataset_id}.{table_name}"

    def streaming_insert(self, table_name: str, rows: list[dict]) -> None:
        errors = self._bq.insert_rows_json(self.table_ref(table_name), rows)
        if errors:
            raise RuntimeError(f"BigQuery streaming insert errors: {errors}")

    def query(self, sql: str, params: list | None = None):
        from google.cloud import bigquery  # type: ignore[import-untyped]

        job_config = bigquery.QueryJobConfig(query_parameters=params or [])
        return self._bq.query(sql, job_config=job_config).result()

    def query_one(self, sql: str, params: list | None = None):
        return next(iter(self.query(sql, params)), None)


def _get_bq_client():
    """backend では BigQueryLogClient シングルトン、それ以外は _StandaloneClient を返す。"""
    try:
        from app.providers.bigquery_log import BigQueryLogClient  # type: ignore[import]

        return BigQueryLogClient.get_instance()
    except ImportError:
        return _StandaloneClient()


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
    """Pareto 候補群を BigQuery prompt_candidates テーブルに保存する。

    同一最適化ランの候補は共通の optimization_id で紐づけられる。

    Args:
        program_name: モジュール識別子（例: 'paper_summary'）。
        candidates: GEPA Pareto フロントから抽出した dspy.Module のリスト。

    Returns:
        今回の最適化ランを表す optimization_id（UUID）。
    """
    bq = _get_bq_client()
    optimization_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    rows = []
    for i, candidate in enumerate(candidates):
        rows.append(
            {
                "optimization_id": optimization_id,
                "program_name": program_name,
                "candidate_index": i,
                "module_state": _serialize_module(candidate),
                "created_at": created_at,
            }
        )

    bq.streaming_insert(_BQ_TABLE, rows)
    print(
        f"✅ Saved {len(rows)} candidates for '{program_name}' "
        f"to BigQuery (optimization_id={optimization_id})"
    )
    return optimization_id


def load_candidates_from_bigquery(
    module_factory: Callable[[], dspy.Module],
    program_name: str,
) -> list[dspy.Module]:
    """BigQuery から最新の Pareto 候補群をロードして返す。

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
    from google.cloud import bigquery as bq_types  # type: ignore[import-untyped]

    bq = _get_bq_client()
    table = bq.table_ref(_BQ_TABLE)

    # 最新の optimization_id を取得
    sql_latest = f"""
        SELECT optimization_id
        FROM `{table}`
        WHERE program_name = @program_name
        ORDER BY created_at DESC
        LIMIT 1
    """
    row = bq.query_one(
        sql_latest,
        [bq_types.ScalarQueryParameter("program_name", "STRING", program_name)],
    )

    if not row:
        print(f"⚠️ No candidates found in BigQuery for '{program_name}'. Using default module.")
        return [module_factory()]

    optimization_id: str = row["optimization_id"]

    # その optimization_id に属する全候補を取得
    sql_candidates = f"""
        SELECT candidate_index, module_state
        FROM `{table}`
        WHERE program_name = @program_name
          AND optimization_id = @optimization_id
        ORDER BY candidate_index ASC
    """
    rows = bq.query(
        sql_candidates,
        [
            bq_types.ScalarQueryParameter("program_name", "STRING", program_name),
            bq_types.ScalarQueryParameter("optimization_id", "STRING", optimization_id),
        ],
    )

    modules: list[dspy.Module] = []
    for r in rows:
        try:
            mod = _deserialize_module(module_factory(), r["module_state"])
            modules.append(mod)
        except Exception as e:
            print(f"⚠️ Failed to deserialize candidate {r['candidate_index']} for '{program_name}': {e}")

    if not modules:
        print(f"⚠️ All candidates failed to deserialize for '{program_name}'. Using default module.")
        return [module_factory()]

    print(
        f"✅ Loaded {len(modules)} candidates for '{program_name}' "
        f"(optimization_id={optimization_id})"
    )
    return modules

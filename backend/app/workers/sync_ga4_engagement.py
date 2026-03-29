"""
GA4 BigQuery → PostgreSQL Sync Job

GA4 のエクスポートデータから日次エンゲージメント・ページビューを集計し、
logs PostgreSQL（vostro ポッド）に書き込む。
Kubernetes CronJob として実行されることを想定。

Usage:
    python -m app.workers.sync_ga4_engagement [--date YYYYMMDD] [--days N]
"""

import argparse

import sys
from datetime import date, datetime, timedelta

import structlog
from google.cloud import bigquery

from app.models.log_schemas.schemas import PageViewLogData, UserEngagementData
from app.providers.pg_log import PgLogClient
from common.config import settings

log = structlog.get_logger("GA4Sync")

# ============================================================================
# Configuration
# ============================================================================

GCP_PROJECT_ID = settings.get("GCP_PROJECT_ID", "gen-lang-client-0800253336")
GA4_DATASET_ID = settings.get("GA4_DATASET_ID", "")
BQ_LOCATION_ANALYTICS = settings.get("BQ_LOCATION_ANALYTICS", "asia-northeast2")


# ============================================================================
# BigQuery Queries (GA4 → 集計)
# ============================================================================


def build_engagement_query(dataset: str, target_date: str) -> str:
    """日次エンゲージメント集計クエリ（エンゲージメント時間・PV・セッション・スクロール深度を一括取得）。"""
    return f"""
    SELECT
        user_pseudo_id,
        (SELECT value.string_value
         FROM UNNEST(event_params)
         WHERE key = 'user_id'
         LIMIT 1) AS firebase_uid,
        event_date,
        SUM(
            IFNULL(
                (SELECT value.int_value
                 FROM UNNEST(event_params)
                 WHERE key = 'engagement_time_msec'
                 LIMIT 1),
                0
            )
        ) / 1000.0 AS total_engagement_seconds,
        COUNTIF(event_name = 'page_view') AS page_views,
        COUNT(DISTINCT
            (SELECT value.int_value
             FROM UNNEST(event_params)
             WHERE key = 'ga_session_id'
             LIMIT 1)
        ) AS session_count,
        MAX(
            CASE WHEN event_name = 'scroll_depth' THEN
                CAST(
                    (SELECT value.int_value
                     FROM UNNEST(event_params)
                     WHERE key = 'threshold_percent'
                     LIMIT 1) AS INT64
                )
            END
        ) AS max_scroll_depth
    FROM
        `{dataset}.events_{target_date}`
    GROUP BY
        user_pseudo_id, firebase_uid, event_date
    HAVING
        total_engagement_seconds > 0 OR page_views > 0
    """


def build_page_views_query(dataset: str, target_date: str) -> str:
    """個別ページビューイベント取得クエリ。"""
    return f"""
    SELECT
        user_pseudo_id,
        (SELECT value.string_value
         FROM UNNEST(event_params)
         WHERE key = 'user_id'
         LIMIT 1) AS firebase_uid,
        CAST(
            (SELECT value.int_value
             FROM UNNEST(event_params)
             WHERE key = 'ga_session_id'
             LIMIT 1) AS STRING
        ) AS ga_session_id,
        TIMESTAMP_MICROS(event_timestamp) AS event_timestamp,
        (SELECT value.string_value
         FROM UNNEST(event_params)
         WHERE key = 'page_location'
         LIMIT 1) AS page_location,
        (SELECT value.string_value
         FROM UNNEST(event_params)
         WHERE key = 'page_title'
         LIMIT 1) AS page_title,
        (SELECT value.string_value
         FROM UNNEST(event_params)
         WHERE key = 'page_referrer'
         LIMIT 1) AS page_referrer,
        IFNULL(
            (SELECT value.int_value
             FROM UNNEST(event_params)
             WHERE key = 'engagement_time_msec'
             LIMIT 1),
            0
        ) / 1000.0 AS engagement_time_seconds,
        (SELECT value.int_value
         FROM UNNEST(event_params)
         WHERE key = 'entrances'
         LIMIT 1) AS is_entrance,
        event_date
    FROM
        `{dataset}.events_{target_date}`
    WHERE
        event_name = 'page_view'
    ORDER BY
        event_timestamp
    """


# ============================================================================
# Sync Functions
# ============================================================================


def sync_engagement(
    ga4_client: bigquery.Client,
    pg_log: PgLogClient,
    dataset: str,
    target_date: str,
) -> int:
    """GA4 から日次エンゲージメントを集計して PostgreSQL に書き込む。

    Args:
        ga4_client: GA4 データセット用 BigQuery クライアント（asia-northeast2）。
        pg_log: ログ用 PgLogClient（vostro）。
        dataset: GA4 データセットパス（project.dataset）。
        target_date: YYYYMMDD 形式の日付文字列。

    Returns:
        書き込んだ行数。
    """
    query = build_engagement_query(dataset, target_date)
    log.info("engagement_query", msg="Fetching engagement data", date=target_date)

    try:
        results = ga4_client.query(query).result()
    except Exception as e:
        log.error("engagement_query_failed", msg=str(e), date=target_date)
        return 0

    rows = list(results)
    if not rows:
        log.info("engagement_empty", msg="No engagement data", date=target_date)
        return 0

    iso_date = f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:]}"

    # 既存データを削除してから再挿入（冪等性確保）
    pg_log.execute_dml(
        "DELETE FROM logs.user_engagements WHERE event_date = :event_date",
        {"event_date": iso_date},
    )

    records = [
        UserEngagementData(
            user_pseudo_id=row.user_pseudo_id,
            firebase_uid=row.firebase_uid,
            event_date=iso_date,
            total_engagement_seconds=float(row.total_engagement_seconds or 0),
            page_views=int(row.page_views or 0),
            session_count=int(row.session_count or 0),
            max_scroll_depth=int(row.max_scroll_depth) if row.max_scroll_depth is not None else None,
        ).to_pg_row()
        for row in rows
    ]

    try:
        pg_log.insert("user_engagements", records)
    except Exception as e:
        log.error("engagement_insert_failed", msg=str(e), date=target_date)
        return 0

    log.info("engagement_synced", msg=f"Synced {len(records)} engagement records", date=target_date)
    return len(records)


def sync_page_views(
    ga4_client: bigquery.Client,
    pg_log: PgLogClient,
    dataset: str,
    target_date: str,
) -> int:
    """GA4 からページビューイベントを取得して PostgreSQL に書き込む。

    Args:
        ga4_client: GA4 データセット用 BigQuery クライアント（asia-northeast2）。
        pg_log: ログ用 PgLogClient（vostro）。
        dataset: GA4 データセットパス（project.dataset）。
        target_date: YYYYMMDD 形式の日付文字列。

    Returns:
        書き込んだ行数。
    """
    query = build_page_views_query(dataset, target_date)
    log.info("page_views_query", msg="Fetching page view data", date=target_date)

    try:
        results = ga4_client.query(query).result()
    except Exception as e:
        log.error("page_views_query_failed", msg=str(e), date=target_date)
        return 0

    rows = list(results)
    if not rows:
        log.info("page_views_empty", msg="No page view data", date=target_date)
        return 0

    iso_date = f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:]}"

    # 既存データを削除してから再挿入（冪等性確保）
    pg_log.execute_dml(
        "DELETE FROM logs.page_view_logs WHERE event_date = :event_date",
        {"event_date": iso_date},
    )

    records = [
        PageViewLogData(
            user_pseudo_id=row.user_pseudo_id,
            firebase_uid=row.firebase_uid,
            ga_session_id=row.ga_session_id,
            event_timestamp=row.event_timestamp.isoformat() if row.event_timestamp else None,
            page_location=row.page_location,
            page_title=row.page_title,
            page_referrer=row.page_referrer,
            engagement_time_seconds=float(row.engagement_time_seconds or 0),
            is_entrance=row.is_entrance,
            event_date=iso_date,
        ).to_pg_row()
        for row in rows
    ]

    try:
        pg_log.insert("page_view_logs", records)
    except Exception as e:
        log.error("page_views_insert_failed", msg=str(e), date=target_date)
        return 0

    log.info("page_views_synced", msg=f"Synced {len(records)} page view records", date=target_date)
    return len(records)


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Sync GA4 data from BigQuery (analytics) to PostgreSQL (logs)"
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Target date in YYYYMMDD format (default: yesterday)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of days to sync (counting back from --date, default: 1)",
    )
    args = parser.parse_args()

    if not GA4_DATASET_ID:
        log.error(
            "config",
            msg="GA4_DATASET_ID not set. Set it to your BigQuery dataset (e.g., 'analytics_521765405').",
        )
        sys.exit(1)

    dataset = f"{GCP_PROJECT_ID}.{GA4_DATASET_ID}"

    if args.date:
        base_date = datetime.strptime(args.date, "%Y%m%d").date()
    else:
        base_date = date.today() - timedelta(days=1)

    dates = [
        (base_date - timedelta(days=i)).strftime("%Y%m%d") for i in range(args.days)
    ]

    log.info(
        "start",
        msg="Starting GA4 → PostgreSQL sync",
        dataset=dataset,
        dates=dates,
    )

    # GA4 読み取り用クライアント（BigQuery, asia-northeast2）
    ga4_client = bigquery.Client(project=GCP_PROJECT_ID, location=BQ_LOCATION_ANALYTICS)
    # ログ書き込み用クライアント（PostgreSQL, vostro）
    pg_log = PgLogClient.get_instance()

    total_engagements = 0
    total_page_views = 0

    for target_date in dates:
        log.info("sync_date", msg=f"Processing date: {target_date}")
        try:
            eng_count = sync_engagement(ga4_client, pg_log, dataset, target_date)
            pv_count = sync_page_views(ga4_client, pg_log, dataset, target_date)
            total_engagements += eng_count
            total_page_views += pv_count
        except Exception as e:
            log.error("sync_failed", msg=str(e), date=target_date)

    log.info(
        "complete",
        msg="GA4 sync completed",
        total_engagements=total_engagements,
        total_page_views=total_page_views,
        dates_processed=len(dates),
    )


if __name__ == "__main__":
    main()

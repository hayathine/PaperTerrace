"""
GA4 Data API → PostgreSQL Sync Job

GA4 の Data API から日次エンゲージメント・ページビューを集計し、
logs PostgreSQL（vostro ポッド）に書き込む。
Kubernetes CronJob として実行されることを想定。

Usage:
    python -m app.workers.sync_ga4_engagement [--date YYYYMMDD] [--days N]
"""

import argparse
import sys
from datetime import date, datetime, timedelta, timezone

import structlog
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)

from app.models.log_schemas.schemas import PageViewLogData, UserEngagementData
from app.providers.pg_log import PgLogClient
from common.config import settings

log = structlog.get_logger("GA4Sync")

# ============================================================================
# Configuration
# ============================================================================

GCP_PROJECT_ID = settings.get("GCP_PROJECT_ID", "gen-lang-client-0800253336")
GA4_PROPERTY_ID = settings.get("GA4_PROPERTY_ID", "")

# GA4 User-ID 機能または カスタムディメンションの API 名。
# User-ID 機能を使う場合は "userId"、カスタムディメンションの場合は "customUser:user_id" 等。
GA4_USER_ID_DIMENSION = settings.get("GA4_USER_ID_DIMENSION", "")

# 1リクエストで取得する最大行数（GA4 Data API の上限は 250,000）
_ROW_LIMIT = 100_000


# ============================================================================
# Helper
# ============================================================================


def _to_iso(yyyymmdd: str) -> str:
    """YYYYMMDD → YYYY-MM-DD に変換する。"""
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"


def _fetch_all_rows(client: BetaAnalyticsDataClient, request: RunReportRequest) -> list:
    """ページネーションを処理してすべての行を返す。"""
    all_rows = []
    offset = 0
    request.limit = _ROW_LIMIT

    while True:
        request.offset = offset
        try:
            response = client.run_report(request)
        except Exception as e:
            log.error("ga4_api_error", msg=str(e))
            break

        all_rows.extend(response.rows)

        if len(response.rows) < _ROW_LIMIT:
            break
        offset += _ROW_LIMIT
        log.info("ga4_pagination", msg=f"Fetching next page (offset={offset})")

    return all_rows


# ============================================================================
# Sync Functions
# ============================================================================


def sync_engagement(
    client: BetaAnalyticsDataClient,
    pg_log: PgLogClient,
    property_id: str,
    target_date: str,
) -> int:
    """GA4 Data API から日次エンゲージメントを集計して PostgreSQL に書き込む。

    Args:
        client: GA4 Data API クライアント。
        pg_log: ログ用 PgLogClient。
        property_id: GA4 プロパティ ID（数値部分のみ）。
        target_date: YYYYMMDD 形式の日付文字列。

    Returns:
        書き込んだ行数。
    """
    iso_date = _to_iso(target_date)
    log.info("engagement_query", msg="Fetching engagement data", date=target_date)

    # GA4 Data API は userPseudoId/sessionId を runReport で受け付けない。
    # User-ID 機能 ("userId") または カスタムディメンションで識別する。
    dimensions = [Dimension(name=GA4_USER_ID_DIMENSION)]

    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=iso_date, end_date=iso_date)],
        dimensions=dimensions,
        metrics=[
            Metric(name="sessions"),
            Metric(name="screenPageViews"),
            Metric(name="userEngagementDuration"),  # 秒単位
        ],
    )

    rows = _fetch_all_rows(client, request)
    if not rows:
        log.info("engagement_empty", msg="No engagement data", date=target_date)
        return 0

    # 既存データを削除してから再挿入（冪等性確保）
    pg_log.execute_dml(
        f"DELETE FROM {pg_log.table_ref('user_engagements')} WHERE event_date = :event_date",
        {"event_date": iso_date},
    )

    records = []
    for row in rows:
        firebase_uid_raw = row.dimension_values[0].value
        firebase_uid = (
            firebase_uid_raw if firebase_uid_raw not in ("(not set)", "") else None
        )
        # 未ログインユーザーは scoring 対象外のためスキップ
        if firebase_uid is None:
            continue

        session_count = int(row.metric_values[0].value or 0)
        page_views = int(row.metric_values[1].value or 0)
        engagement_seconds = float(row.metric_values[2].value or 0)

        if session_count == 0 and page_views == 0:
            continue

        records.append(
            UserEngagementData(
                user_pseudo_id=firebase_uid,
                firebase_uid=firebase_uid,
                event_date=iso_date,
                total_engagement_seconds=engagement_seconds,
                page_views=page_views,
                session_count=session_count,
                max_scroll_depth=None,  # Data API では取得不可
            ).to_pg_row()
        )

    if not records:
        return 0

    try:
        pg_log.insert("user_engagements", records)
    except Exception as e:
        log.error("engagement_insert_failed", msg=str(e), date=target_date)
        return 0

    log.info("engagement_synced", msg=f"Synced {len(records)} engagement records", date=target_date)
    return len(records)


def sync_page_views(
    client: BetaAnalyticsDataClient,
    pg_log: PgLogClient,
    property_id: str,
    target_date: str,
) -> int:
    """GA4 Data API からページビューを取得して PostgreSQL に書き込む。

    Data API はイベント単位ではなく (ユーザー×セッション×ページ) の集計単位でデータを返す。
    event_timestamp には当日 00:00 UTC を使用する（近似値）。

    Args:
        client: GA4 Data API クライアント。
        pg_log: ログ用 PgLogClient。
        property_id: GA4 プロパティ ID（数値部分のみ）。
        target_date: YYYYMMDD 形式の日付文字列。

    Returns:
        書き込んだ行数。
    """
    iso_date = _to_iso(target_date)
    log.info("page_views_query", msg="Fetching page view data", date=target_date)

    # GA4 Data API は userPseudoId/sessionId を runReport で受け付けないため、
    # ユーザー識別子 + ページ単位の集計とする（セッション単位は諦める）。
    dimensions = [
        Dimension(name=GA4_USER_ID_DIMENSION),
        Dimension(name="pagePathPlusQueryString"),
        Dimension(name="pageTitle"),
        Dimension(name="pageReferrer"),
    ]

    request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=iso_date, end_date=iso_date)],
        dimensions=dimensions,
        metrics=[
            Metric(name="screenPageViews"),
            Metric(name="userEngagementDuration"),  # 秒単位
            Metric(name="entrances"),
        ],
    )

    rows = _fetch_all_rows(client, request)
    if not rows:
        log.info("page_views_empty", msg="No page view data", date=target_date)
        return 0

    # 既存データを削除してから再挿入（冪等性確保）
    pg_log.execute_dml(
        f"DELETE FROM {pg_log.table_ref('page_view_logs')} WHERE event_date = :event_date",
        {"event_date": iso_date},
    )

    # event_timestamp の近似値: 当日 00:00 UTC
    approx_ts = datetime(
        int(target_date[:4]), int(target_date[4:6]), int(target_date[6:]),
        tzinfo=timezone.utc,
    ).isoformat()

    records = []
    for row in rows:
        firebase_uid_raw = row.dimension_values[0].value
        firebase_uid = (
            firebase_uid_raw if firebase_uid_raw not in ("(not set)", "") else None
        )
        # 未ログインユーザーは scoring 対象外のためスキップ
        if firebase_uid is None:
            continue

        page_location = row.dimension_values[1].value or None
        page_title = row.dimension_values[2].value or None
        page_referrer = row.dimension_values[3].value or None
        if page_referrer in ("(not set)", ""):
            page_referrer = None

        engagement_seconds = float(row.metric_values[1].value or 0)
        is_entrance = int(row.metric_values[2].value or 0)

        records.append(
            PageViewLogData(
                user_pseudo_id=firebase_uid,
                firebase_uid=firebase_uid,
                ga_session_id=None,  # Data API では取得不可
                event_timestamp=approx_ts,
                page_location=page_location,
                page_title=page_title,
                page_referrer=page_referrer,
                engagement_time_seconds=engagement_seconds,
                is_entrance=is_entrance if is_entrance > 0 else None,
                event_date=iso_date,
            ).to_pg_row()
        )

    if not records:
        return 0

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
        description="Sync GA4 data from Data API to PostgreSQL (logs)"
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

    if not GA4_PROPERTY_ID:
        log.error(
            "config",
            msg="GA4_PROPERTY_ID not set. Set it to your GA4 property numeric ID (e.g., '123456789').",
        )
        sys.exit(1)

    if not GA4_USER_ID_DIMENSION:
        log.error(
            "config",
            msg="GA4_USER_ID_DIMENSION not set. Use 'userId' for GA4 User-ID feature or 'customUser:<name>' for custom dimensions.",
        )
        sys.exit(1)

    if args.date:
        base_date = datetime.strptime(args.date, "%Y%m%d").date()
    else:
        base_date = date.today() - timedelta(days=1)

    dates = [
        (base_date - timedelta(days=i)).strftime("%Y%m%d") for i in range(args.days)
    ]

    log.info(
        "start",
        msg="Starting GA4 Data API → PostgreSQL sync",
        property_id=GA4_PROPERTY_ID,
        dates=dates,
    )

    client = BetaAnalyticsDataClient()
    pg_log = PgLogClient.get_instance()

    total_engagements = 0
    total_page_views = 0

    for target_date in dates:
        log.info("sync_date", msg=f"Processing date: {target_date}")
        try:
            eng_count = sync_engagement(client, pg_log, GA4_PROPERTY_ID, target_date)
            pv_count = sync_page_views(client, pg_log, GA4_PROPERTY_ID, target_date)
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

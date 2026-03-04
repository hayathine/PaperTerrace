"""
GA4 BigQuery → CloudSQL Sync Job

Fetches user engagement and page view data from GA4's BigQuery export
and syncs it to CloudSQL. Designed to run as a Kubernetes CronJob.

Usage:
    python -m app.workers.sync_ga4_engagement [--date YYYYMMDD] [--days N]
"""

import argparse
import os
import sys
from datetime import date, datetime, timedelta

import structlog
from dotenv import load_dotenv
from google.cloud import bigquery
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load env for local dev
load_dotenv("../local-files/secrets/.env")

log = structlog.get_logger("GA4Sync")

# ============================================================================
# Configuration
# ============================================================================

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "gen-lang-client-0800253336")
GA4_DATASET_ID = os.getenv("GA4_DATASET_ID", "")  # e.g., "analytics_123456789"
DATABASE_URL = os.getenv("DATABASE_URL", "")


def get_engine():
    """Create SQLAlchemy engine from DATABASE_URL."""
    url = DATABASE_URL
    if not url:
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        host = os.getenv("DB_HOST")
        dbname = os.getenv("DB_NAME")
        if all([user, password, host, dbname]):
            url = f"postgresql://{user}:{password}@{host}/{dbname}"
        else:
            log.error("config", msg="DATABASE_URL not configured")
            sys.exit(1)

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    return create_engine(url)


# ============================================================================
# BigQuery Queries
# ============================================================================


def build_engagement_query(dataset: str, target_date: str) -> str:
    """Build BigQuery SQL for daily user engagement aggregation.

    Args:
        dataset: Full BigQuery dataset path (e.g., project.dataset)
        target_date: Date string in YYYYMMDD format
    """
    return f"""
    SELECT
        user_pseudo_id,
        (SELECT value.string_value
         FROM UNNEST(event_params)
         WHERE key = 'user_id'
         LIMIT 1) AS firebase_uid,
        event_date,
        -- Total engagement time (ms → seconds)
        SUM(
            IFNULL(
                (SELECT value.int_value
                 FROM UNNEST(event_params)
                 WHERE key = 'engagement_time_msec'
                 LIMIT 1),
                0
            )
        ) / 1000.0 AS total_engagement_seconds,
        -- Page view count
        COUNTIF(event_name = 'page_view') AS page_views,
        -- Distinct session count
        COUNT(DISTINCT
            (SELECT value.int_value
             FROM UNNEST(event_params)
             WHERE key = 'ga_session_id'
             LIMIT 1)
        ) AS session_count
    FROM
        `{dataset}.events_{target_date}`
    GROUP BY
        user_pseudo_id, firebase_uid, event_date
    HAVING
        total_engagement_seconds > 0 OR page_views > 0
    """


def build_page_views_query(dataset: str, target_date: str) -> str:
    """Build BigQuery SQL for individual page view events.

    Args:
        dataset: Full BigQuery dataset path (e.g., project.dataset)
        target_date: Date string in YYYYMMDD format
    """
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
        -- Convert event_timestamp (microseconds) to datetime
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
        -- Engagement time on this page view (ms → seconds)
        IFNULL(
            (SELECT value.int_value
             FROM UNNEST(event_params)
             WHERE key = 'engagement_time_msec'
             LIMIT 1),
            0
        ) / 1000.0 AS engagement_time_seconds,
        -- Whether this is a landing page
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
    bq_client: bigquery.Client,
    db_session,
    dataset: str,
    target_date: str,
) -> int:
    """Sync daily engagement data from BigQuery to CloudSQL.

    Returns:
        Number of rows upserted.
    """
    query = build_engagement_query(dataset, target_date)
    log.info("engagement_query", msg="Fetching engagement data", date=target_date)

    try:
        results = bq_client.query(query).result()
    except Exception as e:
        log.error("engagement_query_failed", msg=str(e), date=target_date)
        return 0

    count = 0
    for row in results:
        db_session.execute(
            text("""
                INSERT INTO user_engagements
                    (user_pseudo_id, firebase_uid, event_date,
                     total_engagement_seconds, page_views, session_count, synced_at)
                VALUES
                    (:pseudo_id, :uid, :event_date,
                     :seconds, :views, :sessions, NOW())
                ON CONFLICT ON CONSTRAINT uq_user_engagement_pseudo_date
                DO UPDATE SET
                    firebase_uid = COALESCE(EXCLUDED.firebase_uid, user_engagements.firebase_uid),
                    total_engagement_seconds = EXCLUDED.total_engagement_seconds,
                    page_views = EXCLUDED.page_views,
                    session_count = EXCLUDED.session_count,
                    synced_at = NOW()
            """),
            {
                "pseudo_id": row.user_pseudo_id,
                "uid": row.firebase_uid,
                "event_date": datetime.strptime(row.event_date, "%Y%m%d").date()
                if isinstance(row.event_date, str)
                else row.event_date,
                "seconds": float(row.total_engagement_seconds or 0),
                "views": int(row.page_views or 0),
                "sessions": int(row.session_count or 0),
            },
        )
        count += 1

    db_session.commit()
    log.info(
        "engagement_synced", msg=f"Synced {count} engagement records", date=target_date
    )
    return count


def sync_page_views(
    bq_client: bigquery.Client,
    db_session,
    dataset: str,
    target_date: str,
) -> int:
    """Sync page view events from BigQuery to CloudSQL.

    Returns:
        Number of rows inserted.
    """
    query = build_page_views_query(dataset, target_date)
    log.info("page_views_query", msg="Fetching page view data", date=target_date)

    try:
        results = bq_client.query(query).result()
    except Exception as e:
        log.error("page_views_query_failed", msg=str(e), date=target_date)
        return 0

    # Delete existing page views for this date to avoid duplicates
    db_session.execute(
        text("DELETE FROM page_view_logs WHERE event_date = :event_date"),
        {"event_date": target_date},
    )

    count = 0
    for row in results:
        db_session.execute(
            text("""
                INSERT INTO page_view_logs
                    (user_pseudo_id, firebase_uid, ga_session_id,
                     event_timestamp, page_location, page_title,
                     page_referrer, engagement_time_seconds,
                     is_entrance, event_date, synced_at)
                VALUES
                    (:pseudo_id, :uid, :session_id,
                     :timestamp, :location, :title,
                     :referrer, :engagement,
                     :entrance, :event_date, NOW())
            """),
            {
                "pseudo_id": row.user_pseudo_id,
                "uid": row.firebase_uid,
                "session_id": row.ga_session_id,
                "timestamp": row.event_timestamp,
                "location": row.page_location,
                "title": row.page_title,
                "referrer": row.page_referrer,
                "engagement": float(row.engagement_time_seconds or 0),
                "entrance": row.is_entrance,
                "event_date": row.event_date,
            },
        )
        count += 1

    db_session.commit()
    log.info(
        "page_views_synced", msg=f"Synced {count} page view records", date=target_date
    )
    return count


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Sync GA4 data from BigQuery to CloudSQL"
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

    # Validate configuration
    if not GA4_DATASET_ID:
        log.error(
            "config",
            msg="GA4_DATASET_ID not set. "
            "Set it to your BigQuery dataset (e.g., 'analytics_123456789'). "
            "Enable GA4 → BigQuery linking in GA4 Admin first.",
        )
        sys.exit(1)

    dataset = f"{GCP_PROJECT_ID}.{GA4_DATASET_ID}"

    # Determine target date(s)
    if args.date:
        base_date = datetime.strptime(args.date, "%Y%m%d").date()
    else:
        # Default: yesterday (GA4 daily export is available the next day)
        base_date = date.today() - timedelta(days=1)

    dates = [
        (base_date - timedelta(days=i)).strftime("%Y%m%d") for i in range(args.days)
    ]

    log.info(
        "start",
        msg="Starting GA4 → CloudSQL sync",
        dataset=dataset,
        dates=dates,
    )

    # Initialize clients
    bq_client = bigquery.Client(project=GCP_PROJECT_ID)
    engine = get_engine()
    Session = sessionmaker(bind=engine)

    total_engagements = 0
    total_page_views = 0

    for target_date in dates:
        log.info("sync_date", msg=f"Processing date: {target_date}")
        session = Session()
        try:
            eng_count = sync_engagement(bq_client, session, dataset, target_date)
            pv_count = sync_page_views(bq_client, session, dataset, target_date)
            total_engagements += eng_count
            total_page_views += pv_count
        except Exception as e:
            session.rollback()
            log.error("sync_failed", msg=str(e), date=target_date)
        finally:
            session.close()

    log.info(
        "complete",
        msg="GA4 sync completed",
        total_engagements=total_engagements,
        total_page_views=total_page_views,
        dates_processed=len(dates),
    )


if __name__ == "__main__":
    main()

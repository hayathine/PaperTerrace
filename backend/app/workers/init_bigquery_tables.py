"""
BigQuery table initialization script.
Creates datasets and tables for behavioral logs.

Usage:
    python -m app.workers.init_bigquery_tables [--env prod|dev]
"""

import argparse
import os
import sys

from google.cloud import bigquery

from app.models.bigquery.schemas import TABLE_SCHEMAS


def create_dataset_and_tables(project_id: str, dataset_id: str):
    """Create BigQuery dataset (if not exists) and all behavioral log tables."""
    client = bigquery.Client(project=project_id)

    # Create dataset
    dataset_ref = f"{project_id}.{dataset_id}"
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = os.getenv("BQ_LOCATION_LOGS", "asia-northeast1")
    dataset.description = "PaperTerrace behavioral logs"

    try:
        client.create_dataset(dataset, exists_ok=True)
        print(f"✓ Dataset ready: {dataset_ref}")
    except Exception as e:
        print(f"✗ Failed to create dataset: {e}")
        sys.exit(1)

    # Create tables
    for table_name, schema in TABLE_SCHEMAS.items():
        table_ref = f"{dataset_ref}.{table_name}"
        table = bigquery.Table(table_ref, schema=schema)

        # Set partitioning by day on created_at/timestamp for efficient querying
        if table_name == "dspy_traces":
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="created_at",
            )
        elif table_name == "trajectories":
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="created_at",
            )
        elif table_name == "feedback":
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="created_at",
            )
        elif table_name == "user_engagements":
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="event_date",
            )
        elif table_name == "page_view_logs":
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="event_date",
            )

        try:
            client.create_table(table, exists_ok=True)
            print(f"  ✓ Table ready: {table_name}")
        except Exception as e:
            print(f"  ✗ Failed to create table {table_name}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Initialize BigQuery tables for behavioral logs"
    )
    parser.add_argument(
        "--env",
        choices=["prod", "dev"],
        default="dev",
        help="Environment (determines dataset name)",
    )
    args = parser.parse_args()

    project_id = os.getenv("GCP_PROJECT_ID", "gen-lang-client-0800253336")

    if args.env == "prod":
        dataset_id = os.getenv("BQ_LOG_DATASET", "paperterrace_logs")
    else:
        dataset_id = os.getenv("BQ_LOG_DATASET_DEV", "paperterrace_logs_dev")

    print(f"Initializing BigQuery tables for {args.env} environment")
    print(f"  Project: {project_id}")
    print(f"  Dataset: {dataset_id}")
    print()

    create_dataset_and_tables(project_id, dataset_id)
    print("\nDone!")


if __name__ == "__main__":
    main()

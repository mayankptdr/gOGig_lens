
"""add processing metadata and storage key

Revision ID: 77f2d8a19338
Revises: a11bcef6d11c
"""

from pathlib import PureWindowsPath
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "77f2d8a19338"
down_revision: Union[str, None] = "a11bcef6d11c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ALLOWED_STATUSES = (
    "pending",
    "processing",
    "completed",
    "failed",
)


def upgrade() -> None:
    connection = op.get_bind()

    # 1. Validate existing statuses before changing the schema.
    existing_statuses = connection.execute(
        sa.text("SELECT DISTINCT status FROM image_records")
    ).scalars().all()

    invalid_statuses = set(existing_statuses) - set(ALLOWED_STATUSES)

    if invalid_statuses:
        raise RuntimeError(
            f"Migration aborted: unsupported statuses: {sorted(invalid_statuses)}"
        )

    # 2. Add new columns.
    op.add_column(
        "image_records",
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.add_column(
        "image_records",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "image_records",
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "image_records",
        sa.Column("error_code", sa.String(length=50), nullable=True),
    )

    op.add_column(
        "image_records",
        sa.Column("storage_key", sa.String(length=255), nullable=True),
    )

    # 3. Backfill storage_key using only the filename.
    rows = connection.execute(
        sa.text("SELECT id, file_path FROM image_records")
    ).all()

    for row in rows:
        storage_key = PureWindowsPath(row.file_path or "").name

        if not storage_key:
            raise RuntimeError(
                f"Migration aborted: empty storage key for image {row.id}"
            )

        if len(storage_key) > 255:
            raise RuntimeError(
                f"Migration aborted: storage key exceeds 255 characters for image {row.id}"
            )

        connection.execute(
            sa.text(
                "UPDATE image_records "
                "SET storage_key = :storage_key WHERE id = :image_id"
            ),
            {"storage_key": storage_key, "image_id": row.id},
        )

    # 4. Backfill attempts and completion timestamps.
    connection.execute(
        sa.text("""
            UPDATE image_records
            SET attempts = CASE
                WHEN status = 'pending' THEN 0
                ELSE 1
            END
        """)
    )

    connection.execute(
        sa.text("""
            UPDATE image_records
            SET finished_at = updated_at
            WHERE status IN ('completed', 'failed')
        """)
    )

    # 5. Enforce storage_key and remove the old path column.
    op.alter_column(
        "image_records",
        "storage_key",
        existing_type=sa.String(length=255),
        nullable=False,
    )

    op.drop_column("image_records", "file_path")

    # 6. Add the allowed-status constraint.
    op.create_check_constraint(
        "valid_status",
        "image_records",
        "status IN ('pending', 'processing', 'completed', 'failed')",
    )


def downgrade() -> None:
    # Restore the old column from the filename only.
    # Original absolute paths cannot be recovered.
    op.drop_constraint(
        "ck_image_records_valid_status",
        "image_records",
        type_="check",
    )

    op.add_column(
        "image_records",
        sa.Column("file_path", sa.Text(), nullable=True),
    )

    connection = op.get_bind()

    connection.execute(
        sa.text("""
            UPDATE image_records
            SET file_path = storage_key
        """)
    )

    op.alter_column(
        "image_records",
        "file_path",
        existing_type=sa.Text(),
        nullable=False,
    )

    op.drop_column("image_records", "storage_key")
    op.drop_column("image_records", "error_code")
    op.drop_column("image_records", "finished_at")
    op.drop_column("image_records", "started_at")
    op.drop_column("image_records", "attempts")

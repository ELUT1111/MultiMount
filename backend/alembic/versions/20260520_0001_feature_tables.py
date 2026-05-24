"""add feature tables and columns

Revision ID: 20260520_0001
Revises:
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa


revision = "20260520_0001"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    if not _has_table(inspector, table_name):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "share_links"):
        op.create_table(
            "share_links",
            sa.Column("mount_id", sa.Integer(), sa.ForeignKey("mounts.id"), nullable=False),
            sa.Column("file_path", sa.Text(), nullable=False),
            sa.Column("file_name", sa.String(length=512), nullable=True),
            sa.Column("is_dir", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("file_size", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("mime_type", sa.String(length=255), nullable=True),
            sa.Column("snapshot_path", sa.Text(), nullable=True),
            sa.Column("snapshot_size", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("token", sa.String(length=64), nullable=False),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("max_views", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("access_code", sa.String(length=128), nullable=True),
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_share_links_mount_id", "share_links", ["mount_id"])
        op.create_index("ix_share_links_token", "share_links", ["token"], unique=True)
    else:
        share_columns = [
            ("file_name", sa.Column("file_name", sa.String(length=512), nullable=True)),
            ("is_dir", sa.Column("is_dir", sa.Boolean(), nullable=False, server_default=sa.false())),
            ("file_size", sa.Column("file_size", sa.BigInteger(), nullable=False, server_default="0")),
            ("mime_type", sa.Column("mime_type", sa.String(length=255), nullable=True)),
            ("snapshot_path", sa.Column("snapshot_path", sa.Text(), nullable=True)),
            ("snapshot_size", sa.Column("snapshot_size", sa.BigInteger(), nullable=False, server_default="0")),
        ]
        for column_name, column in share_columns:
            if not _has_column(inspector, "share_links", column_name):
                op.add_column("share_links", column)

    if not _has_table(inspector, "trash_items"):
        op.create_table(
            "trash_items",
            sa.Column("mount_id", sa.Integer(), sa.ForeignKey("mounts.id"), nullable=False),
            sa.Column("original_path", sa.Text(), nullable=False),
            sa.Column("trash_path", sa.Text(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("is_dir", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("size", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("deleted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("deleted_by_name", sa.String(length=64), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_trash_items_mount_id", "trash_items", ["mount_id"])
        op.create_index("ix_trash_items_deleted_by", "trash_items", ["deleted_by"])
        op.create_index("ix_trash_items_deleted_at", "trash_items", ["deleted_at"])

    if not _has_table(inspector, "notifications"):
        op.create_table(
            "notifications",
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("type", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=256), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("related_id", sa.Integer(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
    elif not _has_column(inspector, "notifications", "metadata"):
        op.add_column("notifications", sa.Column("metadata", sa.JSON(), nullable=True))
    if _has_table(inspector, "notifications") and not _has_column(inspector, "notifications", "is_archived"):
        op.add_column(
            "notifications",
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if not _has_table(inspector, "file_indexes"):
        op.create_table(
            "file_indexes",
            sa.Column("mount_id", sa.Integer(), sa.ForeignKey("mounts.id"), nullable=False),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("mount_name", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("mount_owner", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("name", sa.String(length=512), nullable=False),
            sa.Column("path", sa.Text(), nullable=False),
            sa.Column("parent_path", sa.Text(), nullable=False, server_default="/"),
            sa.Column("is_dir", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("size", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("mime_type", sa.String(length=255), nullable=True),
            sa.Column("extension", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("file_type", sa.String(length=32), nullable=False, server_default="other"),
            sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("file_created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("mount_id", "path", name="uq_file_indexes_mount_path"),
        )
        op.create_index("ix_file_indexes_mount_type", "file_indexes", ["mount_id", "file_type"])
        op.create_index("ix_file_indexes_size", "file_indexes", ["size"])
        op.create_index("ix_file_indexes_modified_at", "file_indexes", ["modified_at"])

    if _has_table(inspector, "transfer_tasks"):
        if not _has_column(inspector, "transfer_tasks", "source_mount_id"):
            op.add_column("transfer_tasks", sa.Column("source_mount_id", sa.Integer(), nullable=True))
        if not _has_column(inspector, "transfer_tasks", "target_mount_id"):
            op.add_column("transfer_tasks", sa.Column("target_mount_id", sa.Integer(), nullable=True))
        if not _has_column(inspector, "transfer_tasks", "conflict_policy"):
            op.add_column(
                "transfer_tasks",
                sa.Column("conflict_policy", sa.String(length=16), nullable=False, server_default="error"),
            )
        if not _has_column(inspector, "transfer_tasks", "download_limit_bps"):
            op.add_column("transfer_tasks", sa.Column("download_limit_bps", sa.BigInteger(), nullable=True))
        if not _has_column(inspector, "transfer_tasks", "upload_limit_bps"):
            op.add_column("transfer_tasks", sa.Column("upload_limit_bps", sa.BigInteger(), nullable=True))
        if not _has_column(inspector, "transfer_tasks", "checkpoint"):
            op.add_column("transfer_tasks", sa.Column("checkpoint", sa.JSON(), nullable=True))

    if _has_table(inspector, "users") and not _has_column(inspector, "users", "account"):
        op.add_column("users", sa.Column("account", sa.String(length=64), nullable=True))
        op.execute("UPDATE users SET account = username WHERE account IS NULL")
        op.create_index("ix_users_account", "users", ["account"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "users") and _has_column(inspector, "users", "account"):
        op.drop_index("ix_users_account", table_name="users")
        op.drop_column("users", "account")

    if _has_table(inspector, "transfer_tasks"):
        if _has_column(inspector, "transfer_tasks", "checkpoint"):
            op.drop_column("transfer_tasks", "checkpoint")
        if _has_column(inspector, "transfer_tasks", "upload_limit_bps"):
            op.drop_column("transfer_tasks", "upload_limit_bps")
        if _has_column(inspector, "transfer_tasks", "download_limit_bps"):
            op.drop_column("transfer_tasks", "download_limit_bps")
        if _has_column(inspector, "transfer_tasks", "conflict_policy"):
            op.drop_column("transfer_tasks", "conflict_policy")
        if _has_column(inspector, "transfer_tasks", "target_mount_id"):
            op.drop_column("transfer_tasks", "target_mount_id")
        if _has_column(inspector, "transfer_tasks", "source_mount_id"):
            op.drop_column("transfer_tasks", "source_mount_id")

    if _has_table(inspector, "file_indexes"):
        op.drop_index("ix_file_indexes_modified_at", table_name="file_indexes")
        op.drop_index("ix_file_indexes_size", table_name="file_indexes")
        op.drop_index("ix_file_indexes_mount_type", table_name="file_indexes")
        op.drop_table("file_indexes")

    if _has_table(inspector, "notifications"):
        if _has_column(inspector, "notifications", "is_archived"):
            op.drop_column("notifications", "is_archived")
        if _has_column(inspector, "notifications", "metadata"):
            op.drop_column("notifications", "metadata")

    if _has_table(inspector, "trash_items"):
        op.drop_index("ix_trash_items_deleted_at", table_name="trash_items")
        op.drop_index("ix_trash_items_deleted_by", table_name="trash_items")
        op.drop_index("ix_trash_items_mount_id", table_name="trash_items")
        op.drop_table("trash_items")

    if _has_table(inspector, "share_links"):
        for column_name in ["snapshot_size", "snapshot_path", "mime_type", "file_size", "is_dir", "file_name"]:
            if _has_column(inspector, "share_links", column_name):
                op.drop_column("share_links", column_name)
        op.drop_index("ix_share_links_token", table_name="share_links")
        op.drop_index("ix_share_links_mount_id", table_name="share_links")
        op.drop_table("share_links")

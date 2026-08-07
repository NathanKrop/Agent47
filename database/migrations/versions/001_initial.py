"""Initial schema migration."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "listings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("county", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("google_maps_url", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("website_url", sa.String(), nullable=True),
        sa.Column(
            "website_status",
            sa.Enum(
                "no_website", "broken", "parked", "placeholder", "poor", "good",
                name="websitestatus",
            ),
            nullable=True,
        ),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("priority", sa.String(), nullable=True),
        sa.Column("phone_verified", sa.Boolean(), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=True),
        sa.Column("active_recently", sa.Boolean(), nullable=True),
        sa.Column("likely_closed", sa.Boolean(), nullable=True),
        sa.Column("outreach_status", sa.String(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "outreach_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("listing_id", sa.String(), nullable=True),
        sa.Column("channel", sa.String(), nullable=True),
        sa.Column("template_name", sa.String(), nullable=True),
        sa.Column("recipient", sa.String(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "sent", "delivered", "replied", "opted_out", "failed", "do_not_contact",
                name="outreachstatus",
            ),
            nullable=True,
        ),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("replied_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outreach_logs_listing_id", "outreach_logs", ["listing_id"])
    op.create_table(
        "do_not_contact",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("contact", sa.String(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("added_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contact"),
    )
    op.create_index("ix_do_not_contact_contact", "do_not_contact", ["contact"])


def downgrade() -> None:
    op.drop_index("ix_do_not_contact_contact", table_name="do_not_contact")
    op.drop_table("do_not_contact")
    op.drop_index("ix_outreach_logs_listing_id", table_name="outreach_logs")
    op.drop_table("outreach_logs")
    op.drop_table("listings")

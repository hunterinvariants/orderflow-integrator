"""Create order workflow tables.

Revision ID: 0001
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("external_order_id", sa.String(120), nullable=False),
        sa.Column("source_system", sa.String(50), nullable=False),
        sa.Column("destination_system", sa.String(50), nullable=False),
        sa.Column("customer_id", sa.String(120), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("integration_name", sa.String(50)),
        sa.Column("transport_reference", sa.String(120)),
        sa.Column("notes", sa.Text()),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("external_order_id"),
    )
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_source_system", "orders", ["source_system"])
    op.create_index("ix_orders_destination_system", "orders", ["destination_system"])
    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sku", sa.String(120), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_table(
        "order_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_order_events_order_id", "order_events", ["order_id"])
    op.create_index("ix_order_events_event_type", "order_events", ["event_type"])
    op.create_table(
        "routing_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("source_system", sa.String(50)),
        sa.Column("destination_system", sa.String(50)),
        sa.Column("min_total", sa.Numeric(12, 2)),
        sa.Column("integration_name", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_routing_rules_priority", "routing_rules", ["priority"])


def downgrade() -> None:
    op.drop_table("routing_rules")
    op.drop_table("order_events")
    op.drop_table("order_items")
    op.drop_table("orders")

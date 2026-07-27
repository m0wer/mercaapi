"""Index warehouse tracking queries

Revision ID: c3d4e5f6a7b8
Revises: b7c8d9e0f1a2
Create Date: 2026-07-27 19:20:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_productwarehousestatus_warehouse_id",
        "productwarehousestatus",
        ["warehouse_id"],
    )
    op.create_index(
        "ix_availabilityhistory_warehouse_id",
        "availabilityhistory",
        ["warehouse_id"],
    )
    op.create_index(
        "ix_pricehistory_warehouse_id", "pricehistory", ["warehouse_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_pricehistory_warehouse_id", table_name="pricehistory")
    op.drop_index(
        "ix_availabilityhistory_warehouse_id", table_name="availabilityhistory"
    )
    op.drop_index(
        "ix_productwarehousestatus_warehouse_id",
        table_name="productwarehousestatus",
    )

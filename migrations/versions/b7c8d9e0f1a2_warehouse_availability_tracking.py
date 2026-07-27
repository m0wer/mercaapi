"""Warehouse availability tracking

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-07-27 17:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "warehouse",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("postal_code", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "productwarehousestatus",
        sa.Column("product_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("warehouse_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouse.id"]),
        sa.PrimaryKeyConstraint("product_id", "warehouse_id"),
    )
    op.create_table(
        "availabilityhistory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("warehouse_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouse.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_availabilityhistory_product_id",
        "availabilityhistory",
        ["product_id"],
    )
    with op.batch_alter_table("pricehistory") as batch_op:
        batch_op.add_column(
            sa.Column(
                "warehouse_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True
            )
        )
        batch_op.create_foreign_key(
            "fk_pricehistory_warehouse_id", "warehouse", ["warehouse_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("pricehistory") as batch_op:
        batch_op.drop_constraint("fk_pricehistory_warehouse_id", type_="foreignkey")
        batch_op.drop_column("warehouse_id")
    op.drop_index(
        "ix_availabilityhistory_product_id", table_name="availabilityhistory"
    )
    op.drop_table("availabilityhistory")
    op.drop_table("productwarehousestatus")
    op.drop_table("warehouse")

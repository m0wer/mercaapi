"""Deduplicate nutritional information and enforce one row per product

Revision ID: a1b2c3d4e5f6
Revises: 842908057be0
Create Date: 2026-07-27 10:40:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "842908057be0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Repoint reports at the row that will be kept (lowest id per product).
    op.execute(
        """
        UPDATE wrongnutritionreport
        SET nutrition_id = COALESCE(
            (
                SELECT MIN(n2.id)
                FROM nutritionalinformation n2
                WHERE n2.product_id = (
                    SELECT n3.product_id
                    FROM nutritionalinformation n3
                    WHERE n3.id = wrongnutritionreport.nutrition_id
                )
            ),
            nutrition_id
        )
        """
    )
    # Remove duplicate rows, keeping the lowest id per product.
    op.execute(
        """
        DELETE FROM nutritionalinformation
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM nutritionalinformation
            GROUP BY product_id
        )
        """
    )
    op.create_index(
        "ix_nutritionalinformation_product_id",
        "nutritionalinformation",
        ["product_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_nutritionalinformation_product_id", table_name="nutritionalinformation"
    )

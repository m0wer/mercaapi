"""Add wrong match and nutrition reports

Revision ID: feff058e9105
Revises: 07d7883b354c
Create Date: 2024-10-21 17:13:13.996589

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "feff058e9105"
down_revision: Union[str, None] = "07d7883b354c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "wrongmatchreport",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("original_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("original_price", sa.Float(), nullable=False),
        sa.Column("wrong_match_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(
            ["wrong_match_id"],
            ["product.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "wrongnutritionreport",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("nutrition_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(
            ["nutrition_id"],
            ["nutritionalinformation.id"],
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("wrongnutritionreport")
    op.drop_table("wrongmatchreport")
    # ### end Alembic commands ###

"""Change ticket item quantity to float

Revision ID: 842908057be0
Revises: 783f148d39eb
Create Date: 2024-10-25 15:00:14.655206

"""

from typing import Sequence, Union
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "842908057be0"
down_revision: Union[str, None] = "783f148d39eb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create new table with desired schema
    op.execute("""
        CREATE TABLE ticketitem_new (
            id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL,
            quantity FLOAT NOT NULL,
            total_price FLOAT NOT NULL,
            unit_price FLOAT NOT NULL,
            ticket_id INTEGER NOT NULL,
            matched_product_id VARCHAR,
            FOREIGN KEY(ticket_id) REFERENCES ticket (id),
            FOREIGN KEY(matched_product_id) REFERENCES product (id)
        )
    """)

    # Copy data from old table to new table, converting quantity to float
    op.execute("""
        INSERT INTO ticketitem_new
        SELECT id, name, CAST(quantity AS FLOAT), total_price, unit_price, 
               ticket_id, matched_product_id
        FROM ticketitem
    """)

    # Drop old table
    op.execute("DROP TABLE ticketitem")

    # Rename new table to original name
    op.execute("ALTER TABLE ticketitem_new RENAME TO ticketitem")


def downgrade() -> None:
    # Create new table with integer quantity
    op.execute("""
        CREATE TABLE ticketitem_new (
            id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL,
            quantity INTEGER NOT NULL,
            total_price FLOAT NOT NULL,
            unit_price FLOAT NOT NULL,
            ticket_id INTEGER NOT NULL,
            matched_product_id VARCHAR,
            FOREIGN KEY(ticket_id) REFERENCES ticket (id),
            FOREIGN KEY(matched_product_id) REFERENCES product (id)
        )
    """)

    # Copy data back, converting float to integer
    op.execute("""
        INSERT INTO ticketitem_new
        SELECT id, name, CAST(quantity AS INTEGER), total_price, unit_price,
               ticket_id, matched_product_id
        FROM ticketitem
    """)

    # Drop old table
    op.execute("DROP TABLE ticketitem")

    # Rename new table to original name
    op.execute("ALTER TABLE ticketitem_new RENAME TO ticketitem")

"""remove subscriptions

Subscriptions and the free-tier cap were removed from ZEXR Deal Hub — the catalogue is
open to everyone. This drops the leftover table so the schema matches the models.

Revision ID: 0002_drop_subscriptions
Revises: 959a926bc68b
Create Date: 2026-10-15

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_drop_subscriptions"
down_revision = "959a926bc68b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("subscriptions")


def downgrade() -> None:
    # Recreating a table nobody uses is not worth it; the model is gone too, so
    # downgrade is intentionally a no-op rather than a schema that would not
    # match the code.
    pass
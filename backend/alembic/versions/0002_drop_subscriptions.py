"""remove subscriptions

Subscriptions and the free-tier cap were removed from ZEXR Deal Hub - the
catalogue is open to everyone. This drops the leftover table so the schema
matches the models.

Revision ID: 0002_drop_subscriptions
Revises: 959a926bc68b
Create Date: 2026-10-15

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_drop_subscriptions"
down_revision = "959a926bc68b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Not every database has this table, so the drop has to be conditional.
    #
    # 0001_initial was generated before subscriptions existed, and
    # 959a926bc68b_add_subscriptions is an empty revision, so a database built
    # purely from migrations never creates the table at all. Only databases
    # created straight from the models while the Subscription model was still
    # present actually have it. Dropping unconditionally crashed every fresh
    # `alembic upgrade head`, which meant no clean deployment could ever be
    # built from scratch.
    bind = op.get_bind()
    if "subscriptions" in sa.inspect(bind).get_table_names():
        op.drop_table("subscriptions")


def downgrade() -> None:
    # Recreating a table nobody uses is not worth it; the model is gone too, so
    # downgrade is intentionally a no-op rather than a schema that would not
    # match the code.
    pass
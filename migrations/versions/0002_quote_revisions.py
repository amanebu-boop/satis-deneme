"""Add shared quote numbers and immutable revision links."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "0002_quote_revisions"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("quotations")}

    if "quote_group_number" not in columns:
        op.add_column("quotations", sa.Column("quote_group_number", sa.Text(), nullable=True))
    if "revision_of" not in columns:
        op.add_column("quotations", sa.Column("revision_of", sa.Text(), nullable=True))

    bind.execute(text(
        "UPDATE quotations SET quote_group_number = quote_number "
        "WHERE quote_group_number IS NULL"
    ))

    foreign_keys = inspect(bind).get_foreign_keys("quotations")
    if not any(fk.get("constrained_columns") == ["revision_of"] for fk in foreign_keys):
        op.create_foreign_key(
            "fk_quotations_revision_of", "quotations", "quotations",
            ["revision_of"], ["id"], ondelete="SET NULL",
        )

    if "quote_revision_sequences" not in inspect(bind).get_table_names():
        op.create_table(
            "quote_revision_sequences",
            sa.Column("quote_group_number", sa.Text(), primary_key=True),
            sa.Column("last_revision", sa.Integer(), nullable=False),
        )

    indexes = {index["name"] for index in inspect(bind).get_indexes("quotations")}
    if "idx_quotations_group_revision" not in indexes:
        op.create_index(
            "idx_quotations_group_revision", "quotations",
            ["quote_group_number", "revision"], unique=True,
        )
    if "idx_quotations_revision_of" not in indexes:
        op.create_index("idx_quotations_revision_of", "quotations", ["revision_of"])


def downgrade():
    raise RuntimeError(
        "Quote revision history is append-only; restore from a verified backup to downgrade."
    )

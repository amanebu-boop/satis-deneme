"""Create the initial application schema using the repository's portable bootstrap."""
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # db.init_db() is idempotent and is also used by the SQLite development backend.
    # The SQLAlchemy compatibility layer routes it through the Alembic-selected PostgreSQL URL.
    from app import db
    db.init_db()


def downgrade():
    raise RuntimeError("Initial schema downgrade is intentionally disabled; restore from a verified backup.")

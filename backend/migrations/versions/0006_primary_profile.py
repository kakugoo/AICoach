"""Allow one primary tracked profile per user."""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tracked_profiles", sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("uq_tracked_primary_user", "tracked_profiles", ["user_id"], unique=True,
                    postgresql_where=sa.text("is_primary"))


def downgrade():
    op.drop_index("uq_tracked_primary_user", table_name="tracked_profiles")
    op.drop_column("tracked_profiles", "is_primary")

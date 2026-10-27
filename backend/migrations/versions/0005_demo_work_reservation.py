"""Reserve disk space for decompressed files."""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("demo_uploads", sa.Column("work_bytes", sa.BigInteger(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("demo_uploads", "work_bytes")

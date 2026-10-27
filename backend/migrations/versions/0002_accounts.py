"""Create users, server sessions, and login throttling records."""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("users", sa.Column("id", sa.Uuid(), primary_key=True),
                    sa.Column("email", sa.String(320), nullable=False, unique=True),
                    sa.Column("password_hash", sa.String(512), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("user_sessions", sa.Column("token_hash", sa.String(64), primary_key=True),
                    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_table("login_attempts", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("ip_key", sa.String(64), nullable=False),
                    sa.Column("email_key", sa.String(64), nullable=False),
                    sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False))
    for column in ("ip_key", "email_key", "attempted_at"):
        op.create_index(f"ix_login_attempts_{column}", "login_attempts", [column])


def downgrade() -> None:
    op.drop_table("login_attempts")
    op.drop_table("user_sessions")
    op.drop_table("users")

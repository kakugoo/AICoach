"""Store FACEIT players separately from the users tracking them."""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "faceit_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("faceit_player_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("nickname", sa.String(64), nullable=False),
        sa.Column("steam_id64", sa.String(20), nullable=True),
        sa.Column("profile_url", sa.String(512), nullable=False),
        sa.Column("avatar_url", sa.String(1024), nullable=True),
        sa.Column("elo", sa.Integer(), nullable=True),
        sa.Column("skill_level", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_faceit_profiles_steam_id64", "faceit_profiles", ["steam_id64"])
    op.create_table(
        "tracked_profiles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("profile_id", sa.Uuid(), sa.ForeignKey("faceit_profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("tracked_profiles")
    op.drop_table("faceit_profiles")

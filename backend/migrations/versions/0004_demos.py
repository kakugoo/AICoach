"""Store uploaded demos and versioned match results."""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("demo_uploads", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False), sa.Column("storage_name", sa.String(64), nullable=False, unique=True),
        sa.Column("checksum", sa.String(64)), sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)))
    op.create_index("ix_demo_uploads_owner_id", "demo_uploads", ["owner_id"])
    op.create_index("ix_demo_uploads_status", "demo_uploads", ["status"])
    op.create_table("matches", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("demo_id", sa.Uuid(), sa.ForeignKey("demo_uploads.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("map_name", sa.String(128)), sa.Column("score", sa.JSON()),
        sa.Column("parser_version", sa.String(32), nullable=False), sa.Column("analysis_version", sa.String(32), nullable=False),
        sa.Column("facts", sa.JSON(), nullable=False))
    op.create_table("match_players", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("match_id", sa.Uuid(), sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("steam_id64", sa.String(20)), sa.Column("name", sa.String(128), nullable=False),
        sa.Column("team", sa.String(32)), sa.Column("kills", sa.Integer()), sa.Column("deaths", sa.Integer()),
        sa.Column("assists", sa.Integer()), sa.Column("headshots", sa.Integer()))
    op.create_index("ix_match_players_match_id", "match_players", ["match_id"])
    op.create_table("match_rounds", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("match_id", sa.Uuid(), sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False), sa.Column("winner", sa.String(32)), sa.Column("tick", sa.Integer()))
    op.create_index("ix_match_rounds_match_id", "match_rounds", ["match_id"])


def downgrade():
    op.drop_table("match_rounds")
    op.drop_table("match_players")
    op.drop_table("matches")
    op.drop_table("demo_uploads")

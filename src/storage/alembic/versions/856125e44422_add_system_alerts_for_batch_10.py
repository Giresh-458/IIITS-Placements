"""Add system_alerts for Batch 10

Revision ID: 856125e44422
Revises: cc83c9d0cd44
Create Date: 2026-10-07 09:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import src.storage.models.json_type


# revision identifiers, used by Alembic.
revision: str = '856125e44422'
down_revision: Union[str, Sequence[str], None] = 'cc83c9d0cd44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('system_alerts',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('snapshot_id', sa.String(), nullable=True),
    sa.Column('lead_id', sa.String(), nullable=True),
    sa.Column('alert_type', sa.String(), nullable=False),
    sa.Column('priority', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('message', sa.String(), nullable=False),
    sa.Column('old_value', src.storage.models.json_type.JSONEncodedDict(), nullable=True),
    sa.Column('new_value', src.storage.models.json_type.JSONEncodedDict(), nullable=True),
    sa.Column('evidence_reference', src.storage.models.json_type.JSONEncodedDict(), nullable=True),
    sa.Column('change_fingerprint', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('delivery_status', sa.String(), nullable=False),
    sa.Column('delivery_attempts', sa.Integer(), nullable=False),
    sa.Column('detected_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
    sa.Column('actioned_at', sa.DateTime(), nullable=True),
    sa.Column('next_retry_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['lead_id'], ['outreach_leads.canonical_event_id'], ),
    sa.ForeignKeyConstraint(['snapshot_id'], ['snapshots.snapshot_id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('change_fingerprint', name='uq_alert_change_fingerprint')
    )
    op.create_index('ix_alerts_delivery', 'system_alerts', ['delivery_status'], unique=False)
    op.create_index('ix_alerts_priority', 'system_alerts', ['priority'], unique=False)
    op.create_index('ix_alerts_status', 'system_alerts', ['status'], unique=False)
    op.create_index(op.f('ix_system_alerts_lead_id'), 'system_alerts', ['lead_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_system_alerts_lead_id'), table_name='system_alerts')
    op.drop_index('ix_alerts_status', table_name='system_alerts')
    op.drop_index('ix_alerts_priority', table_name='system_alerts')
    op.drop_index('ix_alerts_delivery', table_name='system_alerts')
    op.drop_table('system_alerts')

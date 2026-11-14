"""Initial database schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-11-14 22:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Attempt to enable extensions on postgres
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS citext;")
        op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('phone_e164', sa.String(length=32), nullable=True),
        sa.Column('preferred_language', sa.String(length=8), server_default='en', nullable=False),
        sa.Column('timezone', sa.String(length=64), server_default='Asia/Kolkata', nullable=False),
        sa.Column('quiet_start', sa.Time(), nullable=True),
        sa.Column('quiet_end', sa.Time(), nullable=True),
        sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. user_refresh_tokens
    op.create_table(
        'user_refresh_tokens',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('family_id', sa.Uuid(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_refresh_tokens_family_id'), 'user_refresh_tokens', ['family_id'], unique=False)
    op.create_index(op.f('ix_user_refresh_tokens_token_hash'), 'user_refresh_tokens', ['token_hash'], unique=False)
    op.create_index(op.f('ix_user_refresh_tokens_user_id'), 'user_refresh_tokens', ['user_id'], unique=False)

    # 3. elders
    op.create_table(
        'elders',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('preferred_name', sa.String(length=255), nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('language', sa.String(length=8), server_default='hi', nullable=False),
        sa.Column('timezone', sa.String(length=64), server_default='Asia/Kolkata', nullable=False),
        sa.Column('day_close_time', sa.Time(), nullable=False),
        sa.Column('text_size', sa.SmallInteger(), server_default='1', nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )

    # 4. care_links
    op.create_table(
        'care_links',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('elder_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('role', sa.String(length=16), nullable=False),
        sa.Column('is_owner', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('can_manage_medicines', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['elder_id'], ['elders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('elder_id', 'user_id', name='uq_care_link_elder_user')
    )

    # 5. elder_credentials
    op.create_table(
        'elder_credentials',
        sa.Column('elder_id', sa.Uuid(), nullable=False),
        sa.Column('access_code', sa.String(length=32), nullable=False),
        sa.Column('pin_hash', sa.String(length=255), nullable=False),
        sa.Column('qr_token_hash', sa.String(length=64), nullable=False),
        sa.Column('failed_attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rotated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['elder_id'], ['elders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('elder_id'),
        sa.UniqueConstraint('access_code'),
        sa.UniqueConstraint('qr_token_hash')
    )

    # 6. contacts
    op.create_table(
        'contacts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('elder_id', sa.Uuid(), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('phone_e164', sa.String(length=32), nullable=False),
        sa.Column('whatsapp_e164', sa.String(length=32), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('whatsapp_opt_in', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('preferred_channels', sa.JSON(), nullable=False),
        sa.Column('escalation_order', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['elder_id'], ['elders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('elder_id', 'escalation_order', name='uq_contact_elder_escalation_order')
    )
    op.create_index(op.f('ix_contacts_elder_id'), 'contacts', ['elder_id'], unique=False)

    # 7. notifications & outbox
    op.create_table(
        'notifications',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('elder_id', sa.Uuid(), nullable=True),
        sa.Column('category', sa.String(length=16), nullable=False),
        sa.Column('template_key', sa.String(length=64), nullable=False),
        sa.Column('params', sa.JSON(), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['elder_id'], ['elders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)
    op.create_index(op.f('ix_notifications_elder_id'), 'notifications', ['elder_id'], unique=False)
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)

    op.create_table(
        'outbox',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('channel', sa.String(length=16), nullable=False),
        sa.Column('recipient', sa.String(length=255), nullable=False),
        sa.Column('template_key', sa.String(length=64), nullable=False),
        sa.Column('language', sa.String(length=8), server_default='en', nullable=False),
        sa.Column('params', sa.JSON(), nullable=False),
        sa.Column('dedupe_key', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=16), server_default='queued', nullable=False),
        sa.Column('provider_message_id', sa.String(length=255), nullable=True),
        sa.Column('attempts', sa.SmallInteger(), server_default='0', nullable=False),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dedupe_key')
    )
    op.create_index(op.f('ix_outbox_status_next_attempt_at'), 'outbox', ['status', 'next_attempt_at'], unique=False)


def downgrade() -> None:
    op.drop_table('outbox')
    op.drop_table('notifications')
    op.drop_table('contacts')
    op.drop_table('elder_credentials')
    op.drop_table('care_links')
    op.drop_table('elders')
    op.drop_table('user_refresh_tokens')
    op.drop_table('users')

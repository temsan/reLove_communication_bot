"""Add youtube_chat_users table

Revision ID: 1a2b3c4d5e6f
Revises: 103c3eae0410
Create Date: 2025-05-25 15:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '1a2b3c4d5e6f'
down_revision = '103c3eae0410'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'youtube_chat_users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('youtube_display_name', sa.String(), nullable=False, comment='Отображаемое имя в YouTube чате'),
        sa.Column('youtube_channel_id', sa.String(), nullable=True, comment='ID канала пользователя в YouTube'),
        sa.Column('message_count', sa.Integer(), server_default='0', nullable=False, comment='Количество сообщений в чате'),
        sa.Column('first_seen', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Дата первого сообщения'),
        sa.Column('last_seen', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Дата последнего сообщения'),
        sa.Column('telegram_username', sa.String(), nullable=True, comment='Найденный username в Telegram'),
        sa.Column('telegram_id', sa.BigInteger(), nullable=True, comment='ID пользователя в Telegram, если найден'),
        sa.Column('is_community_member', sa.Boolean(), server_default='f', nullable=False, comment='Является ли участником сообщества'),
        sa.Column('metadata', postgresql.JSONB(), nullable=True, comment='Дополнительные данные'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_youtube_chat_users_youtube_display_name'), 'youtube_chat_users', ['youtube_display_name'], unique=False)
    op.create_index(op.f('ix_youtube_chat_users_telegram_username'), 'youtube_chat_users', ['telegram_username'], unique=False)
    op.create_index(op.f('ix_youtube_chat_users_telegram_id'), 'youtube_chat_users', ['telegram_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_youtube_chat_users_telegram_id'), table_name='youtube_chat_users')
    op.drop_index(op.f('ix_youtube_chat_users_telegram_username'), table_name='youtube_chat_users')
    op.drop_index(op.f('ix_youtube_chat_users_youtube_display_name'), table_name='youtube_chat_users')
    op.drop_table('youtube_chat_users')

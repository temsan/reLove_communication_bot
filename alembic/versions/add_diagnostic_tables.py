"""add diagnostic tables

Revision ID: add_diagnostic_tables
Revises: 
Create Date: 2024-03-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_diagnostic_tables'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Создаем enum типы
    op.execute("CREATE TYPE psychotypeenum AS ENUM ('matrix', 'seeker', 'transformer')")
    op.execute("CREATE TYPE journeystageenum AS ENUM ('ordinary_world', 'call_to_adventure', 'refusal', 'meeting_mentor', 'crossing_threshold')")
    
    # Создаем таблицу diagnostic_questions
    op.create_table(
        'diagnostic_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('options', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Создаем таблицу diagnostic_results
    op.create_table(
        'diagnostic_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('psychotype', sa.Enum('matrix', 'seeker', 'transformer', name='psychotypeenum'), nullable=False),
        sa.Column('journey_stage', sa.Enum('ordinary_world', 'call_to_adventure', 'refusal', 'meeting_mentor', 'crossing_threshold', name='journeystageenum'), nullable=False),
        sa.Column('answers', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('recommended_stream', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Создаем индексы
    op.create_index(op.f('ix_diagnostic_results_user_id'), 'diagnostic_results', ['user_id'], unique=False)
    op.create_index(op.f('ix_diagnostic_results_psychotype'), 'diagnostic_results', ['psychotype'], unique=False)
    op.create_index(op.f('ix_diagnostic_results_journey_stage'), 'diagnostic_results', ['journey_stage'], unique=False)

def downgrade() -> None:
    # Удаляем таблицы
    op.drop_table('diagnostic_results')
    op.drop_table('diagnostic_questions')
    
    # Удаляем enum типы
    op.execute('DROP TYPE journeystageenum')
    op.execute('DROP TYPE psychotypeenum') 
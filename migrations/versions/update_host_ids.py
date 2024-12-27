"""Update host IDs

Revision ID: update_host_ids
Revises: 40e29184ee43
Create Date: 2024-12-27 18:28:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


# revision identifiers, used by Alembic.
revision = 'update_host_ids'
down_revision = '40e29184ee43'
branch_labels = None
depends_on = None


def upgrade():
    # Временно делаем колонку nullable
    op.alter_column('project', 'yandex_webmaster_host_id',
               existing_type=sa.String(length=50),
               nullable=True)
    
    # Обнуляем значения host_id
    project_table = table('project',
        column('yandex_webmaster_host_id', sa.String)
    )
    op.execute(
        project_table.update().values(yandex_webmaster_host_id=None)
    )


def downgrade():
    pass

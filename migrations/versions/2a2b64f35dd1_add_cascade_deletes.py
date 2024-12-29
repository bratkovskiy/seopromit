"""Add cascade deletes

Revision ID: 2a2b64f35dd1
Revises: 6f4b42656a5a
Create Date: 2024-12-29 22:55:39.359028

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2a2b64f35dd1'
down_revision = '6f4b42656a5a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('keyword', schema=None) as batch_op:
        batch_op.drop_constraint('keyword_ibfk_1', type_='foreignkey')
        batch_op.create_foreign_key(None, 'project', ['project_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('url', schema=None) as batch_op:
        batch_op.drop_constraint('url_ibfk_1', type_='foreignkey')
        batch_op.create_foreign_key(None, 'project', ['project_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('url_traffic', schema=None) as batch_op:
        batch_op.drop_constraint('url_traffic_ibfk_1', type_='foreignkey')
        batch_op.create_foreign_key(None, 'url', ['url_id'], ['id'], ondelete='CASCADE')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('url_traffic', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key('url_traffic_ibfk_1', 'url', ['url_id'], ['id'])

    with op.batch_alter_table('url', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key('url_ibfk_1', 'project', ['project_id'], ['id'])

    with op.batch_alter_table('keyword', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key('keyword_ibfk_1', 'project', ['project_id'], ['id'])

    # ### end Alembic commands ###
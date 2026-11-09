# 캐시 표(django_cache) 만들기
# settings.CACHES가 DB 캐시라서, 팀원·서버가 평소처럼 migrate만 하면 표가 생기게 한다.
# (createcachetable은 표가 이미 있으면 아무것도 하지 않는다)

from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    call_command('createcachetable', database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):

    dependencies = [
        ('sherpaapp', '0014_shared_route'),
    ]

    operations = [
        migrations.RunPython(create_cache_table, migrations.RunPython.noop),
    ]

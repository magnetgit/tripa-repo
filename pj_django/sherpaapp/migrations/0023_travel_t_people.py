# 여행 표에 인원 칸 추가 (🟧 11/18) — 계산 인원을 로그인 세션 대신 DB 에 저장

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sherpaapp', '0022_ui_translation'),
    ]

    operations = [
        migrations.AddField(
            model_name='travel',
            name='t_people',
            field=models.PositiveSmallIntegerField(blank=True, db_column='T_PEOPLE', null=True),
        ),
    ]

from django.db import migrations, models


def blank_to_null(apps, schema_editor):
    # 카카오 id 없이 저장된 리뷰('')를 NULL로: 빈칸끼리 "같은 장소"로 걸리지 않게
    Review = apps.get_model('sherpaapp', 'Review')
    Review.objects.filter(kakao_id='').update(kakao_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ('sherpaapp', '0010_merge_20261103_1037'),
    ]

    operations = [
        migrations.AlterField(
            model_name='review',
            name='kakao_id',
            field=models.CharField(blank=True, db_column='KAKAO_ID', db_index=True, max_length=20, null=True),
        ),
        migrations.RunPython(blank_to_null, migrations.RunPython.noop),
    ]

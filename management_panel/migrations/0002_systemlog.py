from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('management_panel', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('level', models.CharField(db_index=True, editable=False, max_length=20)),
                ('logger_name', models.CharField(editable=False, max_length=150)),
                ('message', models.TextField(editable=False)),
                ('request_id', models.CharField(blank=True, editable=False, max_length=32)),
                ('method', models.CharField(blank=True, editable=False, max_length=10)),
                ('path', models.CharField(blank=True, editable=False, max_length=500)),
                ('status_code', models.PositiveSmallIntegerField(editable=False, null=True)),
                ('traceback', models.TextField(blank=True, editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, editable=False)),
            ],
            options={
                'ordering': ('-created_at', '-id'),
            },
        ),
    ]

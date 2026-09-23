from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog_generator', '0002_alter_blogpost_options_alter_blogpost_user_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='blogpost',
            name='status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('pending', 'Pending'),
                    ('processing', 'Processing'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed'),
                ],
                default='completed',  # existing rows are already done
            ),
        ),
        migrations.AddField(
            model_name='blogpost',
            name='error_message',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='blogpost',
            name='generated_content',
            field=models.TextField(blank=True, default=''),
        ),
    ]

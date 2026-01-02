# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workorder', '0039_change_printing_colors_to_cmyk_and_other'),
    ]

    operations = [
        migrations.AddField(
            model_name='artwork',
            name='dies',
            field=models.ManyToManyField(
                blank=True,
                help_text='该图稿关联的刀模',
                related_name='artworks',
                to='workorder.Die',
                verbose_name='关联刀模'
            ),
        ),
    ]


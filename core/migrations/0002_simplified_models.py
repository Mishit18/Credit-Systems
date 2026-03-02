from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='loan',
            name='is_active',
        ),
        
        migrations.AddIndex(
            model_name='loan',
            index=models.Index(fields=['customer', 'end_date'], name='core_loan_cust_end_idx'),
        ),
    ]

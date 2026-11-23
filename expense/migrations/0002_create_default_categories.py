from django.db import migrations

DEFAULT_CATEGORIES = [
    'Food',
    'Transport',
    'Shopping',
    'Bills',
    'Entertainment',
    'Health',
    'Education',
    'Travel',
    'Other',
]


def create_default_categories(apps, schema_editor):
    Category = apps.get_model('expense', 'Category')
    for name in DEFAULT_CATEGORIES:
        Category.objects.get_or_create(name=name, user=None)


def remove_default_categories(apps, schema_editor):
    Category = apps.get_model('expense', 'Category')
    Category.objects.filter(name__in=DEFAULT_CATEGORIES, user__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('expense', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_default_categories, remove_default_categories),
    ]

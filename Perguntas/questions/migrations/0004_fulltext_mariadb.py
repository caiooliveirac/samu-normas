# questions/migrations/XXXX_fulltext_mariadb.py
from django.db import migrations

FTL = """
ALTER TABLE {table} 
ADD FULLTEXT INDEX {index_name} ({columns});
"""

def add_fulltext(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor != "mysql":  # MariaDB reporta como mysql para o Django
        return
    with schema_editor.connection.cursor() as c:
        # full-text em títulos e corpo de Rule
        c.execute(FTL.format(table="questions_rule", index_name="ft_rule_title_body", columns="title, body"))
        # full-text em bullets
        c.execute(FTL.format(table="questions_rulebullet", index_name="ft_bullet_text", columns="text"))

def drop_fulltext(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor != "mysql":
        return
    with schema_editor.connection.cursor() as c:
        c.execute("ALTER TABLE questions_rule DROP INDEX ft_rule_title_body;")
        c.execute("ALTER TABLE questions_rulebullet DROP INDEX ft_bullet_text;")

class Migration(migrations.Migration):
    dependencies = [
        ("questions", "0003_category_rulebullet_rulecard_tag_alter_rule_options_and_more"),  # ajuste para a migration anterior
    ]
    operations = [
        migrations.RunPython(add_fulltext, reverse_code=drop_fulltext),
    ]

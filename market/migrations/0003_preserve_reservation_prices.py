from django.db import migrations


def preserve_prices(apps, schema_editor):
    Reservation = apps.get_model("market", "Reservation")
    for reservation in Reservation.objects.using(schema_editor.connection.alias).select_related(
        "campaign"
    ):
        reservation.unit_price = reservation.campaign.group_price
        reservation.save(update_fields=["unit_price"])


class Migration(migrations.Migration):
    dependencies = [("market", "0002_reservation_paid_amount_reservation_unit_price_and_more")]
    operations = [migrations.RunPython(preserve_prices, migrations.RunPython.noop)]

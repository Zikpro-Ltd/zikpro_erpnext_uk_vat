from your_app.patches.v1_0.add_eu_vat_fields import create_custom_fields

def after_install():
    create_custom_fields()
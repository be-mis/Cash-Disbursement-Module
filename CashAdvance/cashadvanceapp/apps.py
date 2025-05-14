from django.apps import AppConfig


class CashadvanceappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cashadvanceapp'


    def ready(self):
        import cashadvanceapp.signals
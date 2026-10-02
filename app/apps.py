import sys
import threading

from django.apps import AppConfig


def _is_management_command():
    """True para `manage.py test/check/collectstatic...` (exceto runserver)."""
    return (
        len(sys.argv) > 1
        and sys.argv[0].endswith("manage.py")
        and sys.argv[1] != "runserver"
    )


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'

    def ready(self):
        # Pré-carrega o catálogo TOI em segundo plano para a home mostrar o total.
        if _is_management_command():
            return

        def _prefetch():
            try:
                from .data import get_toi_dataframe
                get_toi_dataframe()
            except Exception:
                pass

        threading.Thread(target=_prefetch, daemon=True).start()

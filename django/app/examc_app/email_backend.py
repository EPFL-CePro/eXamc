from constance import config
from django.core.mail.backends.smtp import EmailBackend


class ConstanceEmailBackend(EmailBackend):
    """
    SMTP backend that pulls its config from django-constance.
    """

    def __init__(self, fail_silently: bool = False, **kwargs):
        # Constance values are defaults: arguments passed explicitly by a caller still win.
        kwargs.setdefault("host", config.EMAIL_HOST)
        kwargs.setdefault("port", config.EMAIL_PORT)
        kwargs.setdefault("username", config.EMAIL_HOST_USER)
        kwargs.setdefault("password", config.EMAIL_HOST_PASSWORD)
        kwargs.setdefault("use_ssl", config.EMAIL_USE_SSL)
        # you can also wire use_tls here if you add a separate Constance flag

        super().__init__(fail_silently=fail_silently, **kwargs)
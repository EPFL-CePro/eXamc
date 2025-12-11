# myproject/email_backend.py
from django.core.mail.backends.smtp import EmailBackend
from constance import config


class ConstanceEmailBackend(EmailBackend):
    """
    SMTP backend that pulls its config from django-constance.
    """

    def __init__(self, **kwargs):
        super().__init__(
            host=config.EMAIL_HOST,
            port=config.EMAIL_PORT,
            username=config.EMAIL_HOST_USER,
            password=config.EMAIL_HOST_PASSWORD,
            use_ssl=config.EMAIL_USE_SSL,
            # you can also wire use_tls here if you add a separate Constance flag
            fail_silently=kwargs.get("fail_silently", False),
            **kwargs,
        )

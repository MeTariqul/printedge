"""Custom email backends for handling SMTP connection errors."""

from django.core.mail.backends.smtp import EmailBackend as SMTPBackend
import logging
from django.conf import settings


class SMTPBackend(SMTPBackend):
    """
    Custom SMTP backend that catches ConnectionResetError and BrokenPipeError
    to prevent unnecessary error logs, especially in development when testing
    with real SMTP server but wanting to avoid crashes.
    """

    def send_messages(self, email_messages):
        """
        Send email messages and handle connection errors.
        """
        try:
            return super().send_messages(email_messages)
        except (ConnectionResetError, BrokenPipeError) as e:
            if not self.fail_silently:
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"SMTP connection unexpectedly closed: {e}. "
                    f"Email not sent. fail_silently={self.fail_silently}"
                )
            return 0
        except Exception:
            # Re-raise any other exceptions
            raise
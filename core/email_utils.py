"""Brevo email utility for sending transactional emails."""

import os
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException


def send_brevo_email(to_email, subject, html_content, text_content=None):
    """
    Send an email via Brevo REST API.
    Returns (success, message_id_or_error).
    """
    api_key = os.environ.get('BREVO_API_KEY')
    if not api_key:
        return False, 'BREVO_API_KEY not configured'

    try:
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = api_key

        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

        sender_email = os.environ.get('DEFAULT_FROM_EMAIL', 'print-edge@outlook.com')
        sender = {"email": sender_email, "name": "PrintEdge"}
        to = [{"email": to_email, "name": to_email.split('@')[0]}]

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            sender=sender,
            to=to,
            subject=subject,
            html_content=html_content,
            text_content=text_content or ''
        )

        api_response = api_instance.send_transac_email(send_smtp_email)
        return True, getattr(api_response, 'message_id', 'sent')
    except ApiException as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)
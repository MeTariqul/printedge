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

        from .models import SiteSettings
        try:
            site = SiteSettings.get()
            sender_name = site.email_from_name or "PrintEdge"
        except Exception:
            sender_name = "PrintEdge"

        sender_email = os.environ.get('DEFAULT_FROM_EMAIL', 'print-edge@outlook.com')
        sender = {"email": sender_email, "name": sender_name}
        to = [{"email": to_email, "name": to_email.split('@')[0]}]

        plain_text = text_content or ''
        if not plain_text and html_content:
            from django.utils.html import strip_tags
            plain_text = strip_tags(html_content)

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            sender=sender,
            to=to,
            subject=subject,
            html_content=html_content,
            text_content=plain_text,
        )

        api_response = api_instance.send_transac_email(send_smtp_email)
        return True, getattr(api_response, 'message_id', 'sent')
    except ApiException as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


def send_db_email(template_name, to_email, context_data):
    """
    Fetches an EmailTemplate by name, renders it with context_data, and sends it.
    """
    from .models import EmailTemplate, EmailLog
    from django.template import Context, Template
    from django.utils.html import strip_tags

    try:
        tpl = EmailTemplate.objects.get(name=template_name)
    except EmailTemplate.DoesNotExist:
        return False, f"Template {template_name} not found"
    
    subject_tpl = Template(tpl.subject)
    body_tpl = Template(tpl.html_body)
    
    ctx = Context(context_data)
    subject = subject_tpl.render(ctx)
    html_content = body_tpl.render(ctx)
    text_content = strip_tags(html_content)
    
    success, result = send_brevo_email(to_email, subject, html_content, text_content)
    EmailLog.objects.create(
        recipient=to_email,
        subject=subject,
        body=text_content[:500],
        status='sent' if success else 'failed',
        error_message='' if success else result,
    )
    return success, result
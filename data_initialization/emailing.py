# utils/emailing.py
from typing import Iterable, Optional, Sequence, Tuple, Union
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.mail.backends.smtp import EmailBackend


Attachment = Union[str, Tuple[str, bytes, str]]  # path OR (filename, content, mimetype)

def send_custom_email(
    EMAIL_HOST: str,
    EMAIL_PORT: int,
    EMAIL_USE_SSL: bool,
    EMAIL_HOST_USER: str,
    EMAIL_HOST_PASSWORD: str,
    subject: str,
    body: str,
    to: Sequence[str],
    *,
    from_email: Optional[str] = None,
    html_body: Optional[str] = None,
    cc: Optional[Iterable[str]] = None,
    bcc: Optional[Iterable[str]] = None,
    reply_to: Optional[Iterable[str]] = None,
    attachments: Optional[Iterable[Attachment]] = None,
    timeout: int = 30,
    fail_silently: bool = False,
) -> int:
    """
    Envoie un e-mail via un backend SMTP construit à la volée.
    Retourne le nombre de messages envoyés (0 ou 1).

    - attachments: soit chemins de fichiers, soit tuples (filename, content_bytes, mimetype)
    """
    # 1) Crée une connexion SMTP dédiée, sans toucher aux settings globaux
    connection = EmailBackend(
        host=EMAIL_HOST,
        port=EMAIL_PORT,
        username=EMAIL_HOST_USER,
        password=EMAIL_HOST_PASSWORD,
        use_ssl=EMAIL_USE_SSL,
        use_tls=False,   # tu peux passer à True si tu utilises STARTTLS (au lieu de SSL)
        timeout=timeout,
        fail_silently=fail_silently,
    )

    # 2) Prépare le message
    sender = from_email or EMAIL_HOST_USER
    message = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=sender,
        to=list(to),
        cc=list(cc) if cc else None,
        bcc=list(bcc) if bcc else None,
        reply_to=list(reply_to) if reply_to else None,
        connection=connection,
    )

    if html_body:
        message.attach_alternative(html_body, "text/html")

    if attachments:
        for att in attachments:
            if isinstance(att, str):
                message.attach_file(att)  # chemin de fichier
            else:
                filename, content, mimetype = att
                message.attach(filename, content, mimetype)

    # 3) Envoie
    return message.send(fail_silently=fail_silently)

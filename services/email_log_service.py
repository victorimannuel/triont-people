"""Allowlisted delivery errors: never expose raw SMTP replies or credentials."""
import smtplib
import ssl

SAFE_ERRORS = (
    'SMTP authentication failed.',
    'SMTP recipient rejected.',
    'SMTP sender rejected.',
    'SMTP connection failed.',
    'SMTP server rejected the message.',
    'SMTP connection timed out.',
    'SMTP TLS verification failed.',
    'SMTP configuration unavailable.',
    'SMTP delivery failed or is no longer configured.',
    'Delivery attempts exhausted.',
)


def safe_delivery_error(exc):
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return SAFE_ERRORS[0]
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return SAFE_ERRORS[1]
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return SAFE_ERRORS[2]
    if isinstance(exc, (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected)):
        return SAFE_ERRORS[3]
    if isinstance(exc, smtplib.SMTPResponseException):
        return SAFE_ERRORS[4]
    if isinstance(exc, TimeoutError):
        return SAFE_ERRORS[5]
    if isinstance(exc, ssl.SSLError):
        return SAFE_ERRORS[6]
    if isinstance(exc, ValueError):
        return SAFE_ERRORS[7]
    return SAFE_ERRORS[8]


def public_delivery_error(value):
    return value if value in SAFE_ERRORS else (SAFE_ERRORS[8] if value else '')

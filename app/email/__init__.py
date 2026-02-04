"""Email module for sending notifications."""

from app.email.service import EmailService, get_email_service

__all__ = ["EmailService", "get_email_service"]

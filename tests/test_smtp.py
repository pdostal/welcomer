"""Tests for SMTP email sending."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from welcomer.config import SmtpConfig
from welcomer.smtp import send_email

BASE_CFG = SmtpConfig(host="localhost", port=1025, from_addr="from@example.com")
AUTH_CFG = SmtpConfig(
    host="smtp.example.com",
    port=587,
    from_addr="from@example.com",
    username="user",
    password="secret",
    tls=True,
)
SSL_CFG = SmtpConfig(
    host="smtp.example.com",
    port=465,
    from_addr="from@example.com",
    ssl=True,
)


def _make_smtp_mock():
    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    return mock


# ---------------------------------------------------------------------------
# Plain SMTP (no TLS, no auth)
# ---------------------------------------------------------------------------


def test_send_email_uses_plain_smtp():
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp) as mock_cls:
        send_email(BASE_CFG, "to@example.com", "Hello", "Body text")
    mock_cls.assert_called_once_with("localhost", 1025)


def test_send_email_no_starttls_by_default():
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_email(BASE_CFG, "to@example.com", "Hello", "Body text")
    mock_smtp.starttls.assert_not_called()


def test_send_email_no_login_without_credentials():
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_email(BASE_CFG, "to@example.com", "Hello", "Body text")
    mock_smtp.login.assert_not_called()


def test_send_email_calls_send_message():
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_email(BASE_CFG, "to@example.com", "Subject here", "Body text")
    mock_smtp.send_message.assert_called_once()
    msg = mock_smtp.send_message.call_args[0][0]
    assert msg["To"] == "to@example.com"
    assert msg["From"] == "from@example.com"
    assert msg["Subject"] == "Subject here"


def test_send_email_body_content():
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_email(BASE_CFG, "to@example.com", "Hi", "Dear guest,\n\nWelcome!")
    msg = mock_smtp.send_message.call_args[0][0]
    assert "Dear guest" in msg.get_content()


# ---------------------------------------------------------------------------
# STARTTLS + auth
# ---------------------------------------------------------------------------


def test_send_email_calls_starttls_when_tls_true():
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_email(AUTH_CFG, "to@example.com", "Hi", "Body")
    mock_smtp.starttls.assert_called_once()


def test_send_email_calls_login_with_credentials():
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_email(AUTH_CFG, "to@example.com", "Hi", "Body")
    mock_smtp.login.assert_called_once_with("user", "secret")


def test_send_email_login_after_starttls():
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_email(AUTH_CFG, "to@example.com", "Hi", "Body")
    order = [c[0] for c in mock_smtp.method_calls]
    assert order.index("starttls") < order.index("login")


# ---------------------------------------------------------------------------
# SSL (SMTP_SSL)
# ---------------------------------------------------------------------------


def test_send_email_uses_smtp_ssl_when_ssl_true():
    mock_smtp = _make_smtp_mock()
    with (
        patch("smtplib.SMTP_SSL", return_value=mock_smtp) as mock_cls,
        patch("ssl.create_default_context"),
    ):
        send_email(SSL_CFG, "to@example.com", "Hi", "Body")
    mock_cls.assert_called_once()
    assert mock_cls.call_args[0][0] == "smtp.example.com"
    assert mock_cls.call_args[0][1] == 465


def test_send_email_ssl_does_not_use_plain_smtp():
    mock_smtp = _make_smtp_mock()
    with (
        patch("smtplib.SMTP_SSL", return_value=mock_smtp),
        patch("smtplib.SMTP") as mock_plain,
        patch("ssl.create_default_context"),
    ):
        send_email(SSL_CFG, "to@example.com", "Hi", "Body")
    mock_plain.assert_not_called()

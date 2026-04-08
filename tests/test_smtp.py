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


# ---------------------------------------------------------------------------
# from_name — display name in From header
# ---------------------------------------------------------------------------


def test_from_name_formats_from_header():
    cfg = SmtpConfig(
        host="localhost", port=1025, from_addr="info@example.com", from_name="My Property"
    )
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_email(cfg, "to@example.com", "Hi", "Body")
    msg = mock_smtp.send_message.call_args[0][0]
    assert msg["From"] == "My Property <info@example.com>"


def test_from_name_empty_uses_plain_address():
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_email(BASE_CFG, "to@example.com", "Hi", "Body")
    msg = mock_smtp.send_message.call_args[0][0]
    assert msg["From"] == "from@example.com"


# ---------------------------------------------------------------------------
# CC header
# ---------------------------------------------------------------------------


def test_cc_header_set_when_configured():
    cfg = SmtpConfig(
        host="localhost", port=1025, from_addr="from@example.com", cc=["mgr@example.com"]
    )
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_email(cfg, "to@example.com", "Hi", "Body")
    msg = mock_smtp.send_message.call_args[0][0]
    assert "mgr@example.com" in msg["CC"]


def test_cc_multiple_addresses_in_header():
    cfg = SmtpConfig(
        host="localhost",
        port=1025,
        from_addr="from@example.com",
        cc=["a@example.com", "b@example.com"],
    )
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_email(cfg, "to@example.com", "Hi", "Body")
    msg = mock_smtp.send_message.call_args[0][0]
    assert "a@example.com" in msg["CC"]
    assert "b@example.com" in msg["CC"]


def test_no_cc_header_when_not_configured():
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_email(BASE_CFG, "to@example.com", "Hi", "Body")
    msg = mock_smtp.send_message.call_args[0][0]
    assert msg["CC"] is None


# ---------------------------------------------------------------------------
# BCC — in envelope but NOT in headers
# ---------------------------------------------------------------------------


def test_bcc_not_in_message_headers():
    cfg = SmtpConfig(
        host="localhost", port=1025, from_addr="from@example.com", bcc=["secret@example.com"]
    )
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_email(cfg, "to@example.com", "Hi", "Body")
    msg = mock_smtp.send_message.call_args[0][0]
    assert msg["BCC"] is None


def test_bcc_in_envelope_to_addrs():
    cfg = SmtpConfig(
        host="localhost", port=1025, from_addr="from@example.com", bcc=["secret@example.com"]
    )
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_email(cfg, "to@example.com", "Hi", "Body")
    call_kwargs = mock_smtp.send_message.call_args
    to_addrs = call_kwargs[1].get("to_addrs") or call_kwargs[0][1]
    assert "secret@example.com" in to_addrs


def test_cc_and_bcc_combined_in_envelope():
    cfg = SmtpConfig(
        host="localhost",
        port=1025,
        from_addr="from@example.com",
        cc=["cc@example.com"],
        bcc=["bcc@example.com"],
    )
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_email(cfg, "to@example.com", "Hi", "Body")
    call_kwargs = mock_smtp.send_message.call_args
    to_addrs = call_kwargs[1].get("to_addrs") or call_kwargs[0][1]
    assert "to@example.com" in to_addrs
    assert "cc@example.com" in to_addrs
    assert "bcc@example.com" in to_addrs


# ---------------------------------------------------------------------------
# send_without_email — empty To with CC/BCC
# ---------------------------------------------------------------------------


def test_empty_to_with_cc_still_sends():
    """When to is empty string but cc is set, the email is sent to cc."""
    cfg = SmtpConfig(
        host="localhost", port=1025, from_addr="from@example.com", cc=["mgr@example.com"]
    )
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_email(cfg, "", "Hi", "Body")
    mock_smtp.send_message.assert_called_once()
    msg = mock_smtp.send_message.call_args[0][0]
    assert msg["To"] is None  # no To header when to is empty


def test_empty_to_with_bcc_still_sends():
    cfg = SmtpConfig(
        host="localhost", port=1025, from_addr="from@example.com", bcc=["audit@example.com"]
    )
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_email(cfg, "", "Hi", "Body")
    mock_smtp.send_message.assert_called_once()
    call_kwargs = mock_smtp.send_message.call_args
    to_addrs = call_kwargs[1].get("to_addrs") or call_kwargs[0][1]
    assert "audit@example.com" in to_addrs


def test_empty_to_no_cc_no_bcc_skips_send():
    """When to is empty and no cc/bcc are configured, nothing should be sent."""
    mock_smtp = _make_smtp_mock()
    with patch("smtplib.SMTP", return_value=mock_smtp):
        send_email(BASE_CFG, "", "Hi", "Body")
    mock_smtp.send_message.assert_not_called()

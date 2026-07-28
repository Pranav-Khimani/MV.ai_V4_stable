from __future__ import annotations

import os
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage

from dotenv import load_dotenv

from core.tool import Tool


load_dotenv()


class EmailTool(Tool):
    """
    Send plain-text email using the user's own SMTP account.

    The SMTP session is reused when possible so later messages are
    significantly faster than reconnecting for every send.
    """

    name = "email"
    description = (
        "Sends an email after explicit user confirmation."
    )

    def __init__(self):
        self._server = None
        self._connection_key = None
        self._lock = threading.RLock()

    def execute(self, args=None):
        args = args or {}
        action = str(
            args.get("action", "")
        ).strip().lower()

        if action != "send_email":
            return (
                f"Unknown email action: {action}"
            )

        return self.send_email(
            recipient=str(
                args.get("to", "")
            ).strip(),
            subject=str(
                args.get("subject", "")
            ).strip(),
            body=str(
                args.get("body", "")
            ).strip(),
        )

    def _disconnect(self) -> None:
        server = self._server
        self._server = None
        self._connection_key = None

        if server is None:
            return

        try:
            server.quit()
        except Exception:
            try:
                server.close()
            except Exception:
                pass

    def _get_server(
        self,
        host: str,
        port: int,
        sender: str,
        password: str,
    ):
        key = (
            host,
            port,
            sender,
        )

        if (
            self._server is not None
            and self._connection_key == key
        ):
            try:
                status, _ = self._server.noop()

                if 200 <= status < 300:
                    return self._server
            except Exception:
                self._disconnect()

        context = ssl.create_default_context()
        server = smtplib.SMTP_SSL(
            host,
            port,
            context=context,
            timeout=8,
        )
        server.login(
            sender,
            password,
        )

        self._server = server
        self._connection_key = key
        return server

    def send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
    ) -> str:
        if not recipient:
            return "Could not send email: recipient is missing."

        if "@" not in recipient:
            return "Could not send email: recipient address is invalid."

        if not subject:
            return "Could not send email: subject is missing."

        if not body:
            return "Could not send email: message body is missing."

        sender = os.getenv(
            "MV_EMAIL_ADDRESS",
            "",
        ).strip()
        password = os.getenv(
            "MV_EMAIL_APP_PASSWORD",
            "",
        ).replace(" ", "").strip()
        host = os.getenv(
            "MV_SMTP_HOST",
            "smtp.gmail.com",
        ).strip()
        port_text = os.getenv(
            "MV_SMTP_PORT",
            "465",
        ).strip()

        if not sender or not password:
            return (
                "Could not send email: configure "
                "MV_EMAIL_ADDRESS and MV_EMAIL_APP_PASSWORD "
                "in your local .env file."
            )

        try:
            port = int(port_text)
        except ValueError:
            return (
                "Could not send email: MV_SMTP_PORT "
                "must be a number."
            )

        message = EmailMessage()
        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)

        started = time.perf_counter()

        with self._lock:
            try:
                server = self._get_server(
                    host=host,
                    port=port,
                    sender=sender,
                    password=password,
                )
                server.send_message(
                    message
                )
            except smtplib.SMTPAuthenticationError:
                self._disconnect()
                return (
                    "Could not send email: authentication failed. "
                    "Use a Google App Password, not your normal password."
                )
            except (smtplib.SMTPException, OSError):
                # A reused connection may have expired. Retry once with
                # a fresh authenticated connection.
                self._disconnect()

                try:
                    server = self._get_server(
                        host=host,
                        port=port,
                        sender=sender,
                        password=password,
                    )
                    server.send_message(
                        message
                    )
                except smtplib.SMTPAuthenticationError:
                    self._disconnect()
                    return (
                        "Could not send email: authentication failed. "
                        "Use a Google App Password, not your normal password."
                    )
                except (smtplib.SMTPException, OSError) as error:
                    self._disconnect()
                    return (
                        "Could not send email: "
                        f"{error}"
                    )

        elapsed = time.perf_counter() - started

        return (
            f"Email sent to {recipient} "
            f"with subject '{subject}' "
            f"in {elapsed:.1f} seconds."
        )

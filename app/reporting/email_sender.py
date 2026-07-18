import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_html_email(
    smtp_host: str,
    smtp_port: int,
    sender: str,
    recipients: list[str],
    subject: str,
    html_body: str,
    username: str = "",
    password: str = "",
    use_tls: bool = True,
) -> None:
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        if use_tls:
            server.starttls()

        if username and password:
            server.login(username, password)

        server.sendmail(sender, recipients, message.as_string())

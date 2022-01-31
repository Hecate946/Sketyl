import re
import asyncio
import aiosmtplib

from email import encoders
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart

import config


HOST = "smtp.gmail.com"
CARRIER_MAP = {
    "verizon": "vtext.com",
    "tmobile": "tmomail.net",
    "sprint": "messaging.sprintpcs.com",
    "at&t": "txt.att.net",
    "boost": "smsmyboostmobile.com",
    "cricket": "sms.cricketwireless.net",
    "uscellular": "email.uscc.net",
}

email = config.EMAIL.address
password = config.EMAIL.password
port = config.EMAIL.port


async def send_email(
    address: str, msg: str = None, subj: str = None, *, html: str = None
):
    message = MIMEMultipart()
    message["From"] = email
    message["To"] = address
    message["Subject"] = subj

    if html:
        message.attach(MIMEText(html, "html"))
    else:
        message.attach(MIMEText(msg, "plain"))

    # send
    send_kws = dict(
        username=email,
        password=password,
        hostname=HOST,
        port=port,
        start_tls=True,
    )
    res = await aiosmtplib.send(message, **send_kws)  # type: ignore
    msg = "failed" if not re.search(r"\sOK\s", res[1]) else "succeeded"
    return res


async def send_emails(self, addresses: list, msg: str, subj: str):
    tasks = [send_email(a, msg, subj) for a in set(addresses)]
    return await asyncio.gather(*tasks)

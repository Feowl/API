from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import get_template
from django.template import Context
from django.utils.translation import ugettext_lazy as _

from datetime import datetime
import settings


def send_message(users, message, channel):
    email_messages = []
    plaintext = get_template('messages/{0}.txt'.format(message))
    html = get_template('messages/{0}.html'.format(message))
    subject = _(message)
    connection = get_connection()
    connection.open()
    for user in users:
        if user.channel == "Email":
            if user.email and user.name:
                d = Context({'name': user.name, 'email_language': user.language})
                text_content = plaintext.render(d)
                html_content = html.render(d)
                msg = EmailMultiAlternatives(subject, text_content, settings.NEWSLETTER_FROM, [user.email], connection=connection)
                msg.attach_alternative(html_content, "text/html")
                email_messages.append(msg)
        elif user.channel == "SMS":
            pass
        user.enquiry = datetime.today().date()
        user.save()

    connection.send_messages(email_messages)
    connection.close()


def parse(message):
    if message == "contribute":
        pass
    elif message == "help":
        pass
    elif message == "register":
        pass
    elif message == "unregister":
        pass
    elif message == "poll":
        pass


def read_message(message):
    parse(message)

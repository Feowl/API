from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import get_template
from django.template import Context
from django.utils.translation import ugettext_lazy as _

from datetime import datetime
from optparse import make_option
import settings

from feowl.models import Contributor, SMS, EMAIL
from feowl.message_helper import send_message as send_sms


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--limit', '-l', dest='limit', default=100,
            help='Pass the Range of contributors you want to send a newsletter'),
    )
    help = 'Send poll to a range of contributors'

    can_import_settings = True

    def handle(self, *args, **options):
        limit = options.get("limit")

        contributors = Contributor.objects.exclude(name=settings.ANONYMOUS_USER_NAME).order_by('-enquiry')[:limit]
        messages = []
        plaintext = get_template('email/newsletter.txt')
        html = get_template('email/newsletter.html')
        subject = _('Hello from Feowl')
        connection = get_connection()
        connection.open()

        for user in contributors:
            if user.email and user.name:
                if user.channel == EMAIL:
                    d = Context({'name': user.name, 'newsletter_language': user.language})
                    text_content = plaintext.render(d)
                    html_content = html.render(d)
                    msg = EmailMultiAlternatives(subject, text_content, settings.NEWSLETTER_FROM, [user.email], connection=connection)
                    msg.attach_alternative(html_content, "text/html")
                    messages.append(msg)
                if user.channel == SMS:
                    msg = """Did u witness powercuts in Douala yesterday? Reply
                        with PC NO or PC district name&duration in mn. Seperate
                        each powercut by a space(ex: PC akwa10 deido70)"""
                    #msg = get_template('sms.txt')
                    send_sms([user], msg)
                # Update the list of targeted users
                user.enquiry = datetime.today().date()
                user.save()

        connection.send_messages(messages)
        connection.close()

from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import get_template
from django.template import Context
from django.utils.translation import ugettext_lazy as _


from datetime import datetime
from optparse import make_option
import settings

from feowl.models import Contributor, SMS, EMAIL,  Device
from feowl.sms_helper import send_sms
from feowl.email_helper import is_valid_email
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--limit', '-l', dest='limit', default=100,
            help='Pass the Range of contributors you want to send a newsletter'),
    )
    help = 'Send poll to a range of contributors'

    can_import_settings = True

    def handle(self, *args, **options):
        limit = options.get("limit")

        contributors = Contributor.objects.exclude(status=Contributor.UNKNOWN).exclude(name=settings.ANONYMOUS_USER_NAME).order_by('-enquiry')[:limit]
        messages = []
        plaintext = get_template('email/newsletter.txt')
        html = get_template('email/newsletter.html')
        subject = _('Hello from Feowl')
        connection = get_connection()
        connection.open()
        for i, user in enumerate(contributors):
                if user.channel == EMAIL and is_valid_email(user.email):
                    d = Context({'name': user.name, 'newsletter_language': user.language})
                    text_content = plaintext.render(d)
                    html_content = html.render(d)
                    msg = EmailMultiAlternatives(subject, text_content, settings.NEWSLETTER_FROM, [user.email], connection=connection)
                    msg.attach_alternative(html_content, "text/html")
                    messages.append(msg)
                    logger.info("Poll Email sent to {0}".format(user.email))

                else:
                    if user.channel == SMS:
                        d = Context({'name': user.name, 'newsletter_language': user.language})
                        msg = get_template('sms.txt')
                        content = msg.render(d)
                        try:
                            mobile = Device.objects.get(contributor=user)
                            send_sms(mobile.phone_number, content)
                            logger.info("Poll SMS sent to {0}".format(mobile.phone_number))
                        except:
                            logger.error("Impossible to send an SMS")

                # Update the list of targeted users
                user.enquiry = datetime.today().date()
                user.save()

        connection.send_messages(messages)
        connection.close()
        logger.info("Poll of {0} sent".format(datetime.today().date()))

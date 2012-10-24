from django.core.mail import EmailMultiAlternatives
from django.template import Context
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _
import settings


def send_email(name, email, language):
    if is_valid_email(email):
        plaintext = get_template('email/registration_confirmation.txt')
        html = get_template('email/registration_confirmation.html')
        subject = _('Welcome to Feowl')
        d = Context({'name': name, 'email_language': language})
        text_content = plaintext.render(d)
        html_content = html.render(d)
        msg = EmailMultiAlternatives(subject, text_content,
                 settings.REGISTRATION_FROM, [email])
        msg.attach_alternative(html_content, "text/html")
        msg.send()


def is_valid_email(email):
    if len(email) > 6 and "@" in email:
        if re.match('\d+@feowl.com', email) != None:
            return False
        else:
            return True
    else:
        return False

from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import IntegrityError, DoesNotExist
from django.template.loader import get_template
from django.template import Context
from django.utils.translation import ugettext_lazy as _

from datetime import datetime
import settings

from feowl.models import Contributor, Device

#TODO: optimize the use of send_message in the functions


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
            # Make sure that we have an phone number before sending an SMS
            # If no phone number then send an Email
            pass
        user.enquiry = datetime.today().date()
        user.save()

    connection.send_messages(email_messages)
    connection.close()


def contribute(message_array, mobile_number):
    """
        Message: contribute <duration>, <area>
    """
    try:
        device = Device.objects.get(phone_number=mobile_number)
        # Check if user exist else create a inactive user
        if device.contributor == None:
            try:
                contributor = Contributor(name=mobile_number, email=mobile_number + "@feowl.com", status=Contributor.INACTIVE)
                contributor.save()
                device.contributor = contributor.id
                device.save()
            except IntegrityError, e:
                msg = e.message
                if msg.find("name") != -1:
                    return "Name already exist. Please use an other one"
                elif msg.find("email") != -1:
                    return "Email already exist. Please use an other one."
                return "Unkown Error please try later to register"
            return "User is created"  # END
        # Check if we ask this user to contribute
        if device.contributor.enquiry != datetime.today().date():  # Maybe we have to check if it was yesterday
            return "We dont ask this user"  # END
    except DoesNotExist:
        raise


def register(message_array, mobile_number):
    """
        Message: register <contributor_name>
    """
    from pwgen import pwgen
    pwd = pwgen(10, no_symbols=True)
    mobile_number = pwd  # We get it as a second parameter
    try:
        try:
            device = Device.objects.get(phone_number=mobile_number)
        except DoesNotExist:
            device = Device(phone_number=mobile_number)
            device.save()
        contributor = Contributor(name=message_array[1], email=mobile_number + "@feowl.com", password=pwd)
        contributor.save()
        device.contributor = contributor
        device.save()
        msg = "Congratulations, you are now registered on FEOWL! Your password is {0}".format(pwd)
        channel = ""
        send_message([contributor], msg, channel)
    except IntegrityError, e:
        msg = e.message
        if msg.find("name") != -1:
            return "Name already exist. Please use an other one"
        elif msg.find("email") != -1:
            return "Email already exist. Please use an other one."
        return "Unkown Error please try later to register"


def unregister(mobile_number):
    """
        Message: unregister
    """
    try:
        device = Device.objects.get(phone_number=mobile_number)
    except DoesNotExist:
        return "Your mobile phone is not registered"
    Contributor.objects.get(pk=device.contributor.id).delete()


def parse(message):
    keywords = ['contribute', 'help', 'register', 'unregister']
    message_array = message.split()
    for index, keyword in enumerate(message_array):
        if keyword in keywords:
            return index, keyword, message_array
    return -1, "Bad Keyword", "No clearly keyword in the string"


def read_message(message):
    mobile_number = "test_number"
    index, keyword, message_array = parse(message)
    if keyword == "contribute":
        contribute(message_array, mobile_number)
    elif keyword == "help":
        pass
    elif keyword == "register":
        register(message_array, mobile_number)
    elif keyword == "unregister":
        unregister(mobile_number)
    elif index == -1:  # Should send an error messages and maybe plus help
        pass

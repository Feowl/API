from django.db import IntegrityError

from datetime import datetime
import re

from feowl.models import Contributor, Device, PowerReport, Area

#TODO: optimize the use of send_message in the functions


def send_message(users, message, channel):
    for user in users:
        if user.channel == "SMS":
            # Make sure that we have an phone number before sending an SMS
            user.enquiry = datetime.today().date()
            user.save()


def contribute(message_array, mobile_number):
    """
        Message: contribute <duration>, <area>
    """
    try:
        device = Device.objects.get(phone_number=mobile_number)
        # Check if user exist else create a inactive user
        if device.contributor == None:
            try:
                contributor = Contributor(name=mobile_number,
                    email=mobile_number + "@feowl.com", status=Contributor.INACTIVE)
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
        # Check if the duration a digit and and remove the default comma
        if not message_array[1].replace(",", "").isdigit():
            return "Duration is not a number"
        # Some simple maybe parsing
        msg_area = message_array[2].lower().capitalize()
        if msg_area not in ("Douala1", "Douala2", "Douala3", "Douala4", "Douala5"):
            return "Area is not in the list"
        #TODO: We should make clear names for the area that we dont get hazle sometimes
        area_id = re.findall(r'\d+', msg_area)[0]
        area = Area.objects.get(pk=area_id)
        report = PowerReport(duration=message_array[1], contributor=contributor, device=device,
                    area=area, happened_at=datetime.today().date())
        report.save()
    except Device.DoesNotExist:
        raise


def register(mobile_number):
    """
        Message: register
    """
    from pwgen import pwgen
    pwd = pwgen(10, no_symbols=True)
    try:
        try:
            device = Device.objects.get(phone_number=mobile_number)
        except Device.DoesNotExist:
            device = Device(phone_number=mobile_number)
            device.save()
        contributor = Contributor(name=mobile_number,
            email=mobile_number + "@feowl.com", password=pwd)
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
        if device.contributor != None:
            Contributor.objects.get(pk=device.contributor.id).delete()
        else:
            # Should happen not often
            device.delete()
    except Device.DoesNotExist:
        return "Your mobile phone is not registered"  # Some error message ?


def parse(message):
    keywords = ['contribute', 'help', 'register', 'unregister']
    message_array = message.split()
    for index, keyword in enumerate(message_array):
        if keyword in keywords:
            return index, keyword, message_array
    return -1, "Bad Keyword", ["No clearly keyword in the string"]


def read_message(message, mobile_number):
    index, keyword, message_array = parse(message)
    if keyword == "contribute":
        contribute(message_array, mobile_number)
    elif keyword == "help":
        pass
    elif keyword == "register":
        register(mobile_number)
    elif keyword == "unregister":
        unregister(mobile_number)
    elif index == -1:  # Should send an error messages and maybe plus help
        return "Something went wrong"

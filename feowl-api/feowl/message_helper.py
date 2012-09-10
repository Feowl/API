from django.db import IntegrityError
from django.db.models import F

from datetime import datetime, timedelta
from pwgen import pwgen
import re

from feowl.models import Contributor, Device, PowerReport, Area, Message, SMS

#TODO: optimize the use of send_message in the functions
#TODO: optimize database access
#TODO: integrate logging


def send_message(users, message):
    for user in users:
        pass
        # Make sure that we have an phone number before sending an SMS


def create_unknown_user(device, mobile_number):
    try:
        contributor = Contributor(name=mobile_number,
            email=mobile_number + "@feowl.com", status=Contributor.UNKNOWN)
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


def contribute(message_array, mobile_number):
    """
        Message: contribute <area> <duration>
        TODO: Message: contribute <area> <duration>, <area> <duration>
    """
    today = datetime.today().date()
    try:
        device = Device.objects.get(phone_number=mobile_number)
        # Check if user exist else create a unknow user
        if device.contributor == None:
            return create_unknown_user(device, mobile_number)
        # Check if we ask this user to contribute
        if device.contributor.enquiry != today:
            msg = Message(message=" ".join(message_array), source=SMS, keyword=message_array[0])
            msg.save()
            return "We dont ask this user"  # END
        # Check if we already had an answer on this day
        if device.contributor.response == today:
            return "Already did a contribution"  # END

        validate_msg = ""
        msg_len = len(message_array)
        loops = msg_len / 3
        for x in range(loops):
            x += 1
            # Check if the duration a digit and and remove the default comma
            duration = message_array[x * 3].replace(",", "")
            if not duration.isdigit():
                msg = Message(message=" ".join(message_array), source=SMS, keyword=message_array[0])
                msg.save()
                return "Duration is not a number"
            # Some simple maybe parsing
            msg_area = " ".join(message_array[x * 3 - 2:x * 3])
            areas_obj = Area.objects.filter(name__iexact=msg_area)

            area_count = len(areas_obj)
            if area_count == 0 or area_count > 1:
                msg = Message(message=" ".join(message_array), source=SMS, keyword=message_array[0])
                msg.save()
                return "Area is not in the list or no much Areas"
            report = PowerReport(duration=duration, contributor=device.contributor, device=device,
                        area=areas_obj[0], happened_at=datetime.today().date())
            report.save()
            validate_msg += "{0}.Report: Area - {1} Duration - {2} ".format(x, areas_obj[0].name, duration)

        # Set response to know that we this user already was handled
        device.contributor.response = today
        device.contributor.save()
        msg = Message(message=" ".join(message_array), source=SMS, parsed=Message.YES, keyword=message_array[0])
        msg.save()
        # Increment refunds
        Contributor.objects.filter(pk=device.contributor.id).update(refunds=F('refunds') + 1)

        send_message([device.contributor], validate_msg)
    except Device.DoesNotExist:
        return "Device is not Existing"


def register(mobile_number, message_array):
    """
        Message: register
    """
    pwd = pwgen(10, no_symbols=True)
    try:
        try:
            device = Device.objects.get(phone_number=mobile_number)
            if device.contributor.status == Contributor.UNKNOWN:
                device.contributor.status = Contributor.ACTIVE
                device.contributor.password = pwd
                device.contributor.save()
                msg = "Thanks for texting! You've joined our volunteer list. Your password is {0}. Reply HELP for further informations. ".format(pwd)
                send_message([device.contributor], msg)
        except Device.DoesNotExist:
            contributor = Contributor(name=mobile_number,
                email=mobile_number + "@feowl.com", password=pwd)
            contributor.save()
            device = Device(phone_number=mobile_number, contributor=contributor)
            device.save()
            Contributor.objects.filter(pk=device.contributor.id).update(refunds=F('refunds') + 1)
            msg = "Thanks for texting! You've joined our volunteer list. Your password is {0}. Reply HELP for further informations. ".format(pwd)
            send_message([contributor], msg)
            msg = Message(message=" ".join(message_array), source=SMS, parsed=Message.YES, keyword=message_array[0])
            msg.save()
    except IntegrityError, e:
        msg = e.message
        if msg.find("name") != -1:
            return "Name already exist. Please use an other one"
        elif msg.find("email") != -1:
            return "Email already exist. Please use an other one."
        return "Unkown Error please try later to register"


def unregister(mobile_number, message_array):
    """
        Message: stop
    """
    try:
        device = Device.objects.get(phone_number=mobile_number)
        if device.contributor != None:
            Contributor.objects.get(pk=device.contributor.id).delete()
        else:
            # Should happen not often
            device.delete()
        msg = Message(message=" ".join(message_array), source=SMS, parsed=Message.YES, keyword=message_array[0])
        msg.save()
    except Device.DoesNotExist:
        return "Your mobile phone is not registered"


def help(mobile_number, message_array):
    """
        Message: help
    """
    first_help_msg = """To report a powercut, send the district name and it's
        duration in mn(ex: PC douala10). Please wait for Feowl asking you by
        sms before answer."""
    second_help_msg = """To report many powercuts, separate it with a dot(ex:
        PC akwa10 deido70)"""
    third_help_msg = """To unsuscribe, send STOP. If you wasn't in Douala, send
         OUT. For each valid sms that you send,you'll receive a confirmation
         and your sms will be refund"""

    try:
        device = Device.objects.get(phone_number=mobile_number)
        if device.contributor == None:
            return create_unknown_user(device, mobile_number)
        send_message([device.contributor], first_help_msg)
        send_message([device.contributor], second_help_msg)
        send_message([device.contributor], third_help_msg)
    except Device.DoesNotExist:
        return "Device does not exist"
    msg = Message(message=" ".join(message_array), source=SMS, parsed=Message.NO, keyword=message_array[0])
    msg.save()


def no(mobile_number, message_array):
    """
        Message: no
    """
    today = datetime.today().date()
    try:
        device = Device.objects.get(phone_number=mobile_number)
        if device.contributor == None:
            return create_unknown_user(device, mobile_number)
        PowerReport.objects.filter(contributor=device.contributor, happened_at=today).delete()
        # Reset the response date
        device.contributor.response = today - timedelta(days=1)
        device.contributor.save()
    except Device.DoesNotExist:
        return "Device does not exist"


def invalid(mobile_number, message_array):
    """
        Message: <something wrong>
    """
    try:
        device = Device.objects.get(phone_number=mobile_number)
        if device.contributor == None:
            create_unknown_user(device, mobile_number)
    except Device.DoesNotExist:
        device = Device(phone_number=mobile_number)
        device.save()
        create_unknown_user(device, mobile_number)
    msg = Message(message=" ".join(message_array), source=SMS, parsed=Message.NO, keyword=message_array[0])
    msg.save()


def parse(message):
    keywords = ['contribute', 'help', 'register', 'stop', 'no']
    # Instead of split using we regex to find all words
    message_array = re.findall(r'\w+', message)
    for index, keyword in enumerate(message_array):
        if keyword.lower() in keywords:
            return index, keyword.lower(), message_array
    return -1, "Bad Keyword", ["No clearly keyword in the string"]


def read_message(message, mobile_number):
    index, keyword, message_array = parse(message)
    if keyword == "contribute":
        contribute(message_array, mobile_number)
    elif keyword == "help":
        help(mobile_number, message_array)
    elif keyword == "register":
        register(mobile_number, message_array)
    elif keyword == "stop":
        unregister(mobile_number, message_array)
    elif keyword == "no":
        no(mobile_number, message_array)
    elif index == -1:  # Should send an error messages and maybe plus help
        invalid(mobile_number, message_array)
        return "Something went wrong"

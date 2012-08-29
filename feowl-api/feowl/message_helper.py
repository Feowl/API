from django.db import IntegrityError
from django.db.models import F

from datetime import datetime
from pwgen import pwgen

from feowl.models import Contributor, Device, PowerReport, Area, Message, SMS

#TODO: optimize the use of send_message in the functions
#TODO: optimize database access


def send_message(users, message, channel):
    for user in users:
        if user.channel == "SMS":
            # Make sure that we have an phone number before sending an SMS
            user.enquiry = datetime.today().date()
            user.save()


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
        Message: contribute <duration>, <area>
        TODO: Message: contribute <Nb of reports> <area><duration>, <area><duration>
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
        # Check if the duration a digit and and remove the default comma
        duration = message_array[1].replace(",", "")
        if not duration.isdigit():
            msg = Message(message=" ".join(message_array), source=SMS, keyword=message_array[0])
            msg.save()
            return "Duration is not a number"
        # Some simple maybe parsing
        msg_area = message_array[2].lower().capitalize()
        areas_obj = Area.objects.all()
        areas = []
        [areas.append(area.name) for area in areas_obj]

        if msg_area not in areas:
            msg = Message(message=" ".join(message_array), source=SMS, keyword=message_array[0])
            msg.save()
            return "Area is not in the list"
        area = Area.objects.get(name=msg_area)
        report = PowerReport(duration=duration, contributor=device.contributor, device=device,
                    area=area, happened_at=datetime.today().date())
        report.save()
        # Set response to know that we this user already was handled
        device.contributor.response = today
        device.contributor.save()
        msg = Message(message=" ".join(message_array), source=SMS, parsed=Message.YES, keyword=message_array[0])
        msg.save()
        # Increment refunds
        Contributor.objects.filter(pk=device.contributor.id).update(refunds=F('refunds') + 1)
    except Device.DoesNotExist:
        return "something"


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
                send_message([device.contributor], msg, "SMS")
        except Device.DoesNotExist:
            contributor = Contributor(name=mobile_number,
                email=mobile_number + "@feowl.com", password=pwd)
            contributor.save()
            device = Device(phone_number=mobile_number, contributor=contributor)
            device.save()
            Contributor.objects.filter(pk=device.contributor.id).update(refunds=F('refunds') + 1)
            msg = "Thanks for texting! You've joined our volunteer list. Your password is {0}. Reply HELP for further informations. ".format(pwd)
            send_message([contributor], msg, "SMS")
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
        return "Your mobile phone is not registered"  # Some error message ? NO is only logging like every return


def help(mobile_number, message_array):
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
        send_message([device.contributor], first_help_msg, "SMS")
        send_message([device.contributor], second_help_msg, "SMS")
        send_message([device.contributor], third_help_msg, "SMS")
    except Device.DoesNotExist:
        return "Device does not exist"
    msg = Message(message=" ".join(message_array), source=SMS, parsed=Message.NO, keyword=message_array[0])
    msg.save()


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
    keywords = ['contribute', 'help', 'register', 'stop']
    message_array = message.split()
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
    elif index == -1:  # Should send an error messages and maybe plus help
        invalid(mobile_number, message_array)
        return "Something went wrong"

from django.db import IntegrityError
from django.db.models import F
from feowl.models import Device, PowerReport, Area, Message, SMS, Contributor

from datetime import datetime, timedelta
from pwgen import pwgen
import re
import logging
import sms_helper

# Get an instance of a logger
logger = logging.getLogger(__name__)

#TODO: optimize the use of send_message in the functions
#TODO: optimize database access
#TODO: integrate logging


def read_message(mobile_number, message):
    index, keyword, message_array = parse(message)
    if keyword == "pc":
        contribute(message_array, mobile_number)
    elif keyword == "help":
        help(mobile_number, message_array)
    elif keyword == "register":
        register(mobile_number, message_array)
    elif keyword == "stop":
        unregister(mobile_number, message_array)
    elif keyword == "cancel":
        cancel(mobile_number, message_array)
    elif index == -1:  # Should send an error messages and maybe plus help
        invalid(mobile_number, message_array)
        return "Something went wrong"


def parse(message):
    keywords = ['pc', 'help', 'register', 'stop', 'cancel']
    # Instead of split using we regex to find all words
    message_array = re.findall(r'\w+', message)
    for index, keyword in enumerate(message_array):
        if keyword.lower() in keywords:
            return index, keyword.lower(), message_array
    return -1, "Bad Keyword", message_array


def contribute(message_array, mobile_number):
    """
        Message: pc <area> <duration>
        TODO: Message: pc <area> <duration>, <area> <duration>
    """
    today = datetime.today().date()
    try:
        device = Device.objects.get(phone_number=mobile_number)
        # Check if user exist else create an unknow user
        if device.contributor == None:
            #TODO: find a better solution for this case (can we have a device without a contributor?)
            pass

        # If this user hasn't been asked today OR If has already answered today, then save the message and ignore contribution
        elif (device.contributor.enquiry != today) or (device.contributor.response == today):
            save_message(message_array, SMS)
            return
        #Else try to parse the contribution and save the report
        else:
            duration, areaid, validated_msg = parse_contribute(message_array)
            #If user sent PC No - then no outage has been experienced
            if (duration < 0):
                report = PowerReport(has_experienced_outage=False, duration=0, contributor=device.contributor, device=device,
                        area=areaid, happened_at=today)
            else:
                report = PowerReport(duration=duration, contributor=device.contributor, device=device,
                        area=areaid, happened_at=today)
            report.save()
        # Set response to know that this user was handled already
        device.contributor.response = today
        device.contributor.save()
        #TODO:a better explanation message
        send_message(device.phone_number, "Hello, this is the message that has been recorded: " + validated_msg +
                                         " - if this is not want you wanted to say, please send us a new message")
        # Increment refunds
        increment_refund(device.contributor.id)

    except Device.DoesNotExist:
        logger.warning("Device is not Existing")
        create_unknown_user(mobile_number)
        return


def increment_refund(user_id):
    #add +1 to the refund counter for the current user
    Contributor.objects.filter(pk=user_id).update(refunds=F('refunds') + 1)


def parse_contribute(message_array):
    #TODO:algorithme to be improved
        validated_msg = ""
        if message_array[1] == "no":
            validated_msg = "No Report"
            save_message(message_array, SMS, parsed=Message.YES)
            return -1, -1, -1
        else:
            msg_len = len(message_array)
            loops = msg_len / 3
            for x in range(loops):
                x += 1
                # Check if the duration a digit and and remove the default comma
                duration = message_array[x * 3].replace(",", "")
                if not duration.isdigit():
                    save_message(message_array, SMS)
                    logger.warning("Duration is not a number")
                    return
                # Some simple maybe parsing
                msg_area = " ".join(message_array[x * 3 - 2:x * 3])
                areas_obj = Area.objects.filter(name__iexact=msg_area)

                area_count = len(areas_obj)
                if area_count == 0 or area_count > 1:
                    save_message(message_array, SMS)
                    logger.warning("Area is not in the list or no much Areas")
                    return
                validated_msg += "{0}.Report: Area - {1} Duration - {2} ".format(x, areas_obj[0].name, duration)
                save_message(message_array, SMS, parsed=Message.YES)
                return duration, areas_obj[0], validated_msg


def create_unknown_user(mobile_number):
    #TODO: Really not sure about this process and how python handles the erros, what happen if an error occurs?
    try:
        contributor = Contributor(name="mobile user",
            email=mobile_number + "@feowl.com", status=Contributor.UNKNOWN)
        contributor.save()
        device = Device(category="mobile", phone_number=mobile_number)
        device.contributor = contributor.id
        device.save()
    except IntegrityError, e:
        msg = e.message
        if msg.find("name") != -1:
            logger.warning("Name already exist. Please use an other one")
            return
        elif msg.find("email") != -1:
            logger.warning("Email already exist. Please use an other one.")
            return
        logger.error("Unkown Error please try later to register")
        return
    logger.info("User is created")
    return  # END


def register(mobile_number, message_array):
    """
        Message: register
    """
    pwd = pwgen(10, no_symbols=True)
    try:
        try:
            device = Device.objects.get(phone_number=mobile_number)
            #If Contributor an unknown, then she becomes active
            if device.contributor.status == Contributor.UNKNOWN:
                device.contributor.status = Contributor.ACTIVE
                device.contributor.password = pwd
                device.contributor.save()
                msg = "Thanks for texting! You've joined our volunteer list. Your password is {0}. Reply HELP for further informations. ".format(pwd)
                send_message(device.phone_number, msg)
        except Device.DoesNotExist:
            #If device doesn't exist then create a user
            contributor = Contributor(name=mobile_number,
                email=mobile_number + "@feowl.com", password=pwd)
            contributor.save()
            device = Device(phone_number=mobile_number, contributor=contributor)
            device.save()
            increment_refund(device.contributor.id)
            msg = "Thanks for texting! You've joined our volunteer list. Your password is {0}. Reply HELP for further informations. ".format(pwd)
            send_message(mobile_number, msg)
            save_message(message_array, SMS, parsed=Message.YES)
    except IntegrityError, e:
        msg = e.message
        if msg.find("name") != -1:
            logger.warning("Name already exist. Please use an other one")
            return
        elif msg.find("email") != -1:
            logger.warning("Email already exist. Please use an other one.")
            return
        logger.error("Unkown Error please try later to register")
        return


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
        save_message(message_array, SMS, parsed=Message.YES)
    except Device.DoesNotExist:
        logger.info("Your mobile phone is not registered")
        return


def help(mobile_number, message_array):
    """
        Message: help
    """
    first_help_msg = """To report a powercut, send the district name and it's
        duration in mn(ex: PC douala10). Please wait for Feowl asking you by
        sms before answer."""
    second_help_msg = """To report many powercuts, separate it with a comma(ex:
        pc akwa10, deido70)"""
    third_help_msg = """To unsuscribe, send STOP. If you wasn't in Douala, send
         OUT. For each valid sms that you send,you'll receive a confirmation
         and your sms will be refunded"""

    try:
        device = Device.objects.get(phone_number=mobile_number)
        if device.contributor == None:
            create_unknown_user(device, mobile_number)
        send_message(device.phone_number, first_help_msg)
        send_message(device.phone_number, second_help_msg)
        send_message(device.phone_number, third_help_msg)
    except Device.DoesNotExist:
        return "Device does not exist"
    save_message(message_array, SMS, parsed=Message.YES)


def cancel(mobile_number, message_array):
    """
        Message: cancel
    """
    today = datetime.today().date()
    try:
        device = Device.objects.get(phone_number=mobile_number)
        if (device.contributor != None):
            reports = PowerReport.objects.filter(contributor=device.contributor, happened_at=today)
            if (reports != None):
                if (reports > 0):
                    reports.delete()
            # Reset the response date
            device.contributor.response = today - timedelta(days=1)
            device.contributor.save()
        else:
            return create_unknown_user(device, mobile_number)
        save_message(message_array, SMS, parsed=Message.YES)
    except Device.DoesNotExist:
        logger.info("Device does not exist")
        return


def invalid(mobile_number, message_array):
    """
        Message: <something wrong>
    """
    msg = Message(message=" ".join(message_array), source=SMS, parsed=Message.NO)
    msg.save()
    try:
        device = Device.objects.get(phone_number=mobile_number)
        if device.contributor == None:
            create_unknown_user(device, mobile_number)
    except Device.DoesNotExist:
        device = Device(phone_number=mobile_number)
        device.save()
        create_unknown_user(device, mobile_number)


def send_message(mobile_number, message):
        #TODO: Make sure that we have an phone number before sending an SMS
        sms_helper.send_sms(mobile_number, message)


def save_message(message_array, src, parsed=Message.NO):
    msg = Message(message=" ".join(message_array), source=src, keyword=message_array[0], parsed=parsed)
    msg.save()

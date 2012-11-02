from django.db import IntegrityError
from django.db.models import F
from feowl.models import Device, PowerReport, Area, Message, SMS, Contributor
from django.contrib.gis.db import *
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
    yesterday = today - timedelta(1)
    try:
        device = Device.objects.get(phone_number=mobile_number)
        # Check if user exist else create an unknow user
        if device.contributor == None:
            #TODO: find a better solution for this case (can we have a device without a contributor?)
            create_unknown_user(mobile_number)
            return
        #Else try to parse the contribution and save the report
        else:
            list = parse_contribute(message_array)
            #If we haven't been able to parse the message
            if list is None:
                msg = "Hello, your message couldn't be translated - please send us another SMS, e.g. ""Douala1 40"". reply HELP for further information"
            #If user sent PC No - then no outage has been experienced
            elif list[0][0] == 0:
                report = PowerReport(has_experienced_outage=False, duration=list[0][0], contributor=device.contributor, device=device,
                        area=list[0][1], happened_at=yesterday)
                report.save()
                increment_refund(device.contributor.id)
                msg = "You have choosen to report no power cut, if this is not want you wanted to say, please send us a new message"
                #logger.warning(report)
            else:
                msg = "You had {0} powercuts yesterday. Durations : ".format(len(list))
                i = 1
                for item in list:
                    report = PowerReport(duration=item[0], contributor=device.contributor, device=device,
                        area=item[1], happened_at=yesterday)
                    report.save()
                    increment_refund(device.contributor.id)
                    i += 1
                    msg += str(item[0]) + " min, "
                msg += "If the data have been misunderstood, please send us another SMS."
            send_message(device.phone_number, msg)

    except Device.DoesNotExist:
        logger.warning("Device is not Existing")
        create_unknown_user(mobile_number)
        return


def increment_refund(user_id):
    #add +1 to the refund counter for the current user
    c = Contributor.objects.get(pk=user_id)
    c.refunds += 1
    c.save()
    #c.update(refunds=F('refunds') + 1)


def parse_contribute(message_array):
    #TODO:algorithme to be improved
        #Contributors reports that he hasn't witnessed a power cut
        list = []
        if message_array[1] == "no":
            save_message(message_array, SMS, parsed=Message.YES)
            list.append([0, get_area("other")])
        #Contributor wants to report a power cut
        else:
            i = 1
            for word in message_array[1:]:
                if word.isdigit():
                    duration = word
                    area = get_area(message_array[i - 1])
                    save_message(message_array, SMS, parsed=Message.YES)
                    list.append([duration, area])
                i += 1
            if len(list) == 0:
                #No report could be added
                save_message(message_array, SMS, parsed=Message.NO)
                return None
        return list


def get_all_areas_name():
    areas = Area.objects.all()
    list = []
    for a in areas:
        list.append(a.name)
    return list


def get_area(area_name):
    from difflib import get_close_matches
    from django.contrib.gis.geos import Polygon
    areas = get_all_areas_name()
    corrected_area_name = get_close_matches(area_name, areas, 1)
    try:
        area = Area.objects.get(name=corrected_area_name)
    except Area.DoesNotExist:
        poly = Polygon(((0, 0), (0, 0), (0, 0), (0, 0), (0, 0)), ((0, 0), (0, 0), (0, 0), (0, 0), (0, 0)))
        area = Area.objects.create(name=area_name, overall_population=0, pop_per_sq_km=0, city="Douala", country="Cameroon", geometry=poly)
    return area


def create_unknown_user(mobile_number):
    #TODO: Really not sure about this process and how python handles the erros, what happen if an error occurs?
    try:
        contributor = Contributor(name=mobile_number,
            email=mobile_number + "@feowl.com", status=Contributor.UNKNOWN)
        contributor.save()
        device = Device(category="mobile", phone_number=mobile_number, contributor=contributor)
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
            if (device.contributor.status == Contributor.UNKNOWN) or (device.contributor.status == Contributor.INACTIVE):
                device.contributor.status = Contributor.ACTIVE
                device.contributor.password = pwd
                device.contributor.channel = SMS
                device.contributor.save()
                msg = "Thanks for texting! You've joined our team. Your password is {0}. Reply HELP for further informations. ".format(pwd)
                send_message(device.phone_number, msg)
        except Device.DoesNotExist:
            #If device doesn't exist then create a user
            contributor = Contributor(name=mobile_number,
                email=mobile_number + "@feowl.com", password=pwd, channel=SMS)
            contributor.save()
            device = Device(phone_number=mobile_number, contributor=contributor, category="mobile")
            device.save()
            increment_refund(device.contributor.id)
            msg = "Thanks for texting! You've joined our team. Your password is {0}. Reply HELP for further informations. ".format(pwd)
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


#def register(mobile_number, message_array):
#    print "hello world"


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
            create_unknown_user(mobile_number)
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
            return create_unknown_user(mobile_number)
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
            create_unknown_user(mobile_number)
    except Device.DoesNotExist:
        create_unknown_user(mobile_number)


def send_message(mobile_number, message):
        #TODO: Make sure that we have an phone number before sending an SMS
        sms_helper.send_sms(mobile_number, message)


def save_message(message_array, src, parsed=Message.NO):
    msg = Message(message=" ".join(message_array), source=src, keyword=message_array[0], parsed=parsed)
    msg.save()

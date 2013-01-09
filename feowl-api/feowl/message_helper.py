# -*- encoding:utf-8 -*-
from django.db import IntegrityError
from django.utils.translation import activate, ugettext as _
from feowl.models import Device, PowerReport, Area, Message, SMS, Contributor
from django.contrib.gis.db import *
from datetime import datetime, timedelta
from pwgen import pwgen
import logging
import sms_helper
import json

# Get an instance of a logger
logger = logging.getLogger(__name__)

#TODO: optimize the use of send_message in the functions
#TODO: optimize database access
#TODO: integrate logging

# we map the keyword to the corresponding language
kw2lang = {'pc': 'en',
           'rep': 'fr',
           'help': 'en',
           'aide': 'fr',
           'register': 'en',
           'inscription': 'fr',
           'cancel': 'en',
           'annule': 'fr',
           'test': 'en'}
keywords = kw2lang.keys() + ['stop']


def read_message(mobile_number, message):
    index, keyword, message_array = parse(message)

    # *ensure* that there is both a device with that number and a corresponding contributor
    devices = Device.objects.filter(phone_number=mobile_number)
    if len(devices) > 0:
        device = devices[0]
        # check if user exists; otherwise create an unknown user
        if device.contributor is None:
            logger.error("found mobile device " + str(device) + " without a contributor")
            logger.info("creating a new contributor")
            contributor = Contributor(name=mobile_number,
                        email=mobile_number + "@feowl.com",
                        status=Contributor.UNKNOWN)
            # if we can deduce the language from the current keyword, set
            #  contributor language
            if keyword in kw2lang:
                contributor.language = kw2lang[keyword].upper()
            contributor.save()
            device.contributor = contributor
            device.save()
        else:
            contributor = device.contributor
    else:
        logger.warning("device does not exist")
        logger.warning("creating a new device and contributor")
        # create a new user (potentially with language) and device
        (device, contributor) = create_unknown_user(mobile_number)
        if keyword in kw2lang:
            contributor.language = kw2lang[keyword].upper()
        contributor.save()
    logger.debug("associating incoming message with " + str(device) + " // " + str(contributor))

    # set the language for upcoming messages
    language = (keyword in kw2lang and kw2lang[keyword]) or contributor.language or "en"
    activate(language.lower())

    # invariant: if we arrive here, we are sure that we have a device
    #  and a contributor. now, do the processing
    if keyword in ("pc", "rep"):
        contribute(message_array, device)
    elif keyword in ("help", "aide"):
        help(message_array, device)
    elif keyword in ("register", "inscription"):
        register(message_array, device)
    elif keyword == "stop":
        unregister(message_array, device)
    elif keyword in ("cancel", "annule"):
        cancel(message_array, device)
    elif keyword in ("test"):
        test(message_array, mobile_number)
    elif index == -1:  # Should send an error messages and maybe plus help
        invalid(mobile_number, message_array)
        return "Something went wrong"


def parse(message):
    #Using split instead of regex to avoid problem with Unicode encoded / special caracters
    message_array = message.split()
    logger.info("---- Message to be parsed is {0} ".format(message_array))
    for index, keyword in enumerate(message_array):
        if keyword.lower() in keywords:
            return index, keyword.lower(), message_array
    return -1, "Bad Keyword", message_array


def contribute(message_array, device):
    """
        Message: pc <area> <duration>
        TODO: Message: pc <area> <duration>, <area> <duration>
    """
    today = datetime.today().date()

    # If this user hasn't been asked today OR If has already answered today, then save the message and ignore contribution
    if (device.contributor.enquiry != today) or (device.contributor.response == today):
        save_message(message_array, SMS)
        return
    # else try to parse the contribution and save the report
    else:
        parsed_data = parse_contribute(message_array)
        #If we haven't been able to parse the message
        if not parsed_data:
            msg = _("Hello, your message couldn't be translated - please send us another SMS, e.g. ""PC douala1 40"". reply HELP for further information")
        #If user sent PC No - then no outage has been experienced
        elif parsed_data[0][0] == 0:
            report = PowerReport(
                has_experienced_outage=False,
                duration=parsed_data[0][0],
                contributor=device.contributor,
                device=device,
                area=parsed_data[0][1],
                happened_at=today
            )
            report.save()

            increment_refund(device.contributor)
            msg = _("You chose to report no power cut. If this is not what you wanted to say, please send us a new SMS")
            #logger.warning(report)
        else:
            msg = _("You had {0} powercuts yesterday. Durations : ").format(len(parsed_data))
            for item in parsed_data:
                report = PowerReport(
                    duration=item[0],
                    contributor=device.contributor,
                    device=device,
                    area=item[1],
                    happened_at=today
                )
                report.save()

                increment_refund(device.contributor)
                msg += _(str(item[0]) + "min, ")
            device.contributor.total_response = +1
            device.contributor.save()
            msg += _("If the data have been misunderstood, please send us another SMS.")
        send_message(device.phone_number, msg)


def increment_refund(c):
    #add +1 to the refund counter for the current user
    try:
        #c = Contributor.objects.get(pk=user_id)
        c.refunds += 1
        c.save()
        #logger.info("Contribtuor {0} has an updated refund of {1} ".format(c.name, c.refunds))
    except Exception, e:
        logger.error("Error while updating Contributor's refund counter - {0} ".format(e))


#TODO: algorithm to be improved
def parse_contribute(message_array):
    #Contributors reports that he hasn't witnessed a power cut
    report_data = []
    if message_array[1] == "no":
        save_message(message_array, SMS, parsed=Message.YES)
        report_data.append([0, get_area("other")])
    else:
        #Contributor wants to report a power cut
        for index, data in enumerate(message_array[1:]):
            if data.isdigit() or data[:-1].isdigit():
                if data.isdigit():
                    duration = data
                else:
                    duration = data[:-1]

                area = get_area(message_array[index])

                save_message(message_array, SMS, parsed=Message.YES)
                report_data.append([duration, area])
        if not report_data:
            #No report could be added
            save_message(message_array, SMS, parsed=Message.NO)
            return None
    return report_data


def get_district_name(area_name):
        district = ''
        try:
            json_data = open('feowl/douala-districts.json')
            table = json.load(json_data)
            quartier = area_name.upper()

            for item in table:
                if quartier == item["Quartier"].upper() or quartier == item["Arrondissement"].upper():
                    district = item["Arrondissement"]
                    break
            if not district:
                logger.info('Area does not exist')
        except Exception, e:
            logger.info('Error while computing the district name - {0}'.format(e))
        return district


def get_area(area_name):
    logger.info("Given Area name is {0}".format(area_name))
    corrected_area_name = get_district_name(area_name)
    try:
        area = Area.objects.get(name__iexact=corrected_area_name)
    except Area.DoesNotExist:
        area = Area.objects.get(name='other')
    logger.info("Saved area name is {0}".format(area.name))
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
    return (device, contributor)


def register(message_array, device):
    """
        Message: register
    """
    pwd = pwgen(10, no_symbols=True)

    if (device.contributor.status == Contributor.UNKNOWN) or (device.contributor.status == Contributor.INACTIVE):
        device.contributor.status = Contributor.ACTIVE
        device.contributor.password = pwd
        device.contributor.channel = SMS
        device.contributor.save()
        increment_refund(device.contributor)
        msg = _("Thanks for texting! You've joined our team. Your password is {0}. Reply HELP for further informations. ").format(pwd)
        save_message(message_array, SMS, parsed=Message.YES)
        send_message(device.phone_number, msg)


def unregister(message_array, device):
    """
        Message: stop
    """
    contributor = device.contributor
    try:
        device.delete()
        contributor.delete()
        save_message(message_array, SMS, parsed=Message.YES)
    except Exception, e:
        logger.error("Error while deleting device/contributor: " + str(e))
        return


def help(message_array, device):
    """
        Message: help
    """
    first_help_msg = _("""To report a powercut, send PC + the arrondissement name + it's duration in mn(ex: PC douala5 10). Please wait for Feowl asking you by sms before answering.""")
    second_help_msg = _("""To report many powercuts, separate them with a comma(ex: PC douala3 10, douala3 45)""")
    third_help_msg = _("""To unsuscribe, send STOP. If you wasn't in Douala, send OUT. For each valid sms that you send,you'll receive a confirmation""")

    send_message(device.phone_number, first_help_msg)
    send_message(device.phone_number, second_help_msg)
    send_message(device.phone_number, third_help_msg)

    save_message(message_array, SMS, parsed=Message.YES)


def cancel(message_array, device):
    """
        Message: cancel
    """
    today = datetime.today().date()
    reports = PowerReport.objects.filter(contributor=device.contributor, happened_at=today)
    if reports > 0:
        reports.delete()

    # Reset the response date
    device.contributor.response = today - timedelta(days=1)
    device.contributor.save()
    save_message(message_array, SMS, parsed=Message.YES)


def invalid(mobile_number, message_array):
    """
        Message: <something wrong>
    """
    msg = Message(message=" ".join(message_array), source=SMS, parsed=Message.NO)
    msg.save()


def test(message_array, mobile_number):
    """
        Message: TEST
    """
    save_message(message_array, SMS, parsed=Message.YES)
    send_message(mobile_number, _("Thanks for trying FEOWL! Send Help for more info"))


def send_message(mobile_number, message):
        sms_helper.send_sms(mobile_number, message)
        #sms_helper.send_sms_nexmo(mobile_number, message)


def save_message(message_array, src, parsed=Message.NO):
    msg = Message(message=" ".join(message_array), source=src, keyword=message_array[0], parsed=parsed)
    msg.save()

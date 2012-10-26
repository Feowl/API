from message_helper import read_message
from nexmomessage import NexmoMessage
import logging
from urllib import urlencode
import urllib2

logger = logging.getLogger(__name__)


# Send the request to LMT SMS gateway
def send_sms(mobile_number, message):
    if (is_phone_number(mobile_number)):
        sender = 'feowl'
        #Check handling of accents
        params = {'UserName': 'feowl', 'Password': 'Pr0760ueL261022', 'SOA': sender, 'MN': mobile_number, 'SM': message}
        url = "http://lmtgroup.dyndns.org/sendsms/sendsms.php"
        req = urllib2.Request(url + "?" + urlencode(params))
        f = urllib2.urlopen(req)
        #logger.warning(f.read())
    else:
        logger.error("SMS not sent - Invalid phone number")


def send_sms_nexmo(mobile_number, message):
    if (is_phone_number(mobile_number)):
        req = "json"
        key = "ff33ed3f"
        secret = "eddd3f0c"
        sender = "feowl"
        msg = {'reqtype': req, 'password': secret, 'from': sender, 'to': mobile_number, 'text': message, 'username': key}
        sms = NexmoMessage(msg)
        sms.send_request()
    else:
        logger.error("SMS not sent - Invalid phone number")


def is_phone_number(num):
    #TODO have fun with Regex to find if it's a good phone number or not
    #Cameroon numbers
    if num.startswith("237") and (len(num) == 12):
        return True
    #German Numbers and French Numbers
    elif num.startswith("49") or num.startswith("33"):
        return True
    else:
        False


def special_batch_sms(mobile_numbers_list, message="template"):
    if message == "template":
        f = open('templates/special_sms.txt', 'r')
        msg = f.read()
    else:
        msg = message
    for number in mobile_numbers_list:
        send_sms(number, msg)


def receive_sms(mobile_number, message):
    read_message(mobile_number, message)

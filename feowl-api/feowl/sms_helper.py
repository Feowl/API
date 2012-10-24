from message_helper import read_message
from nexmomessage import NexmoMessage
import logging

logger = logging.getLogger(__name__)


def send_sms(mobile_number, message):
    if (is_phone_number(mobile_number)):
        req = "json"
        key = "ff33ed3f"
        secret = "eddd3f0c"
        sender = "feowl"
        msg = {'reqtype': req, 'password': secret, 'from': sender, 'to': mobile_number, 'text': message, 'username': key}
        sms = NexmoMessage(msg)
        sms.send_request()
    else:
        pass
        #logger.error("Message not sent - Invalid phone number")


def is_phone_number(num):
    #TODO have fun with Regex to find if it's a good phone number or not
    #Cameroon numbers
    if ("+237" in num) and (len(num) == 12):
        return True
    #German Numbers and French Numbers
    elif ("+49" in num) or ("+33" in num):
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

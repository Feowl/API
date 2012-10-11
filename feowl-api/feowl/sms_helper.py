import message_helper


def special_batch_sms(mobile_numbers_list, message="template"):
    if message == "template":
        f = open('templates/special_sms.txt', 'r')
        msg = f.read()
    else:
        msg = message
    for number in mobile_numbers_list:
        message_helper.send_message(number, msg)


def receive_sms(mobile_number, message):
    message_helper.read_message(mobile_number, message)
    print message

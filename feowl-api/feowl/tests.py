# -*- encoding:utf-8 -*-
from django.conf import settings
from django.contrib.auth.models import User, Permission
from django.db import models
from django.test.client import Client
from feowl.sms_helper import receive_sms, send_sms
from django.utils import unittest

from tastypie.models import create_api_key
from tastypie_test import ResourceTestCase

from feowl.models import PowerReport, Area, Contributor, Device
#from feowl.message_helper import read_message

import json
from datetime import datetime, timedelta

models.signals.post_save.connect(create_api_key, sender=User)


#TODO: Isolated the tests from each other

class PowerReportResourceTest(ResourceTestCase):
    fixtures = ['test_data.json']

    def setUp(self):
        super(PowerReportResourceTest, self).setUp()

        # Create a user.
        self.username = u'john'
        self.password = u'doe'
        self.user = User.objects.create_user(self.username, 'john@example.com', self.password)
        self.api_key = self.user.api_key.key
        self.c = Client()
        self.post_data = {
           "area": "/api/v1/areas/1/",
           "happened_at": "2012-06-14 12:37:50",
           "has_experienced_outage": True,
           "duration": 60
        }

        

        # Fetch the ``Entry`` object we'll use in testing.
        # Note that we aren't using PKs because they can change depending
        # on what other tests are running.
        self.power_report_1 = PowerReport.objects.get(duration=121)

        # We also build a detail URI, since we will be using it all over.
        # DRY, baby. DRY.
        self.detail_url = '/api/v1/reports/{0}/'.format(self.power_report_1.pk)

    def get_credentials(self):
        return {"username": self.username, "api_key": self.api_key}

    def test_get_list_unauthorizied(self):
        """Get reports from the API without authenticated"""
        self.assertHttpUnauthorized(self.c.get('/api/v1/reports/'))

    def test_get_list_json(self):
        """Get reports from the API with authenticated. With checks if all keys are available"""
        resp = self.c.get('/api/v1/reports/', self.get_credentials())
        self.assertValidJSONResponse(resp)
        nb = PowerReport.objects.count()

        # Scope out the data for correctness.
        self.assertEqual(len(self.deserialize(resp)['objects']), nb)
        # Here we're checking an entire structure for the expected data.
        self.assertKeys(self.deserialize(resp)['objects'][0], {
            'area': '/api/v1/areas/1/',
            'happened_at': '2012-06-13T12:37:50+00:00',
            'has_experienced_outage': True,
            'location': None,
            'duration': 240,
            'quality': '1.00',
            'resource_uri': '/api/v1/reports/2/',
            'contributor': None,
            'device': None
        })

    def test_header_auth(self):
        resp = self.c.get(self.detail_url, **{'HTTP_AUTHORIZATION': 'ApiKey ' + self.username + ':' + self.api_key})
        self.assertValidJSONResponse(resp)

        # We use ``assertKeys`` here to just verify the keys, not all the data.
        #self.assertKeys(self.deserialize(resp), ['area', 'device', 'happened_at', 'has_experienced_outage', 'contributor', 'location', 'duration', 'quality'])
        self.assertEqual(self.deserialize(resp)['duration'], 121)

    def test_get_detail_unauthenticated(self):
        """Try to Get a single report from the API without authenticated"""
        self.assertHttpUnauthorized(self.c.get(self.detail_url))

    def test_get_detail_json(self):
        """Get a single report from the API with authenticated. With checks if all keys are available"""
        resp = self.c.get(self.detail_url, self.get_credentials())
        self.assertValidJSONResponse(resp)

        # We use ``assertKeys`` here to just verify the keys, not all the data.
        #self.assertKeys(self.deserialize(resp), ['area', 'happened_at', 'has_experienced_outage', 'contributor', 'location', 'duration', 'quality', 'resource_uri'])
        self.assertEqual(self.deserialize(resp)['duration'], 121)

    def test_post_list_unauthenticated(self):
        """Try to Post a single report to the API without authenticated"""
        self.assertHttpUnauthorized(self.c.post('/api/v1/reports/', data=self.post_data))

    def test_post_list_without_permissions(self):
        """Post a single report to the API with authenticated and without add permissions"""
        add_powerreport = Permission.objects.get(codename="add_powerreport")
        self.user.user_permissions.remove(add_powerreport)
        nb = PowerReport.objects.count()
        self.assertHttpUnauthorized(self.c.post('/api/v1/reports/?username=' + self.username + '&api_key=' + self.api_key, data=json.dumps(self.post_data), content_type="application/json"))
        # Verify that nothing was added to the db
        self.assertEqual(PowerReport.objects.count(), nb)

    def test_post_list_with_permissions(self):
        """Post a single report to the API with authenticated and with add permissions"""
        add_powerreport = Permission.objects.get(codename="add_powerreport")
        self.user.user_permissions.add(add_powerreport)
        # Check how many there are first.
        nb = PowerReport.objects.count()
        self.assertHttpCreated(self.c.post('/api/v1/reports/?username=%s&api_key=%s' % (self.username, self.api_key), data=json.dumps(self.post_data), content_type="application/json"))
        # Verify that no report has been added
        self.assertEqual(PowerReport.objects.count(), nb)

    def test_post_list_with_permissions_and_polled_today(self):
        """Post a single report to the API with authenticated and with add permissions"""
        add_powerreport = Permission.objects.get(codename="add_powerreport")
        self.user.user_permissions.add(add_powerreport)

        # Set enquiry to today - so that the contribution is accepted
        self.contributor_1 = Contributor(name="Marc", email="marc@test.de")
        self.contributor_1.set_password("marc")
        self.contributor_1.enquiry = datetime.today().date()
        self.contributor_1.save()

        # Check how many there are first.
        nb = PowerReport.objects.count()
        rt = PowerReport(has_experienced_outage=True, duration=153, contributor=self.contributor_1, area=Area.objects.get(pk=1), happened_at=datetime.today().date())
        rt.save()
        # Verify that a new report has been added.
        self.assertEqual(PowerReport.objects.count(), nb + 1)

    def test_put_detail_unauthenticated(self):
        """Put a single report is not allowed from the API with authenticated"""
        self.assertHttpMethodNotAllowed(self.c.put(self.detail_url))

    def test_put_detail(self):
        """Put a single report is not allowed from the API with authenticated"""
        self.assertHttpMethodNotAllowed(self.c.put(self.detail_url, self.get_credentials()))

    def test_delete_detail_unauthenticated(self):
        """Delete a single report is not allowed from the API without authenticated"""
        self.assertHttpMethodNotAllowed(self.c.delete(self.detail_url))

    def test_delete_detail(self):
        """Delete a single report is not allowed from the API with authenticated"""
        self.assertHttpMethodNotAllowed(self.c.delete(self.detail_url, self.get_credentials()))
    
    def test_accent(self):
        
        self.assertHttpCreated(self.c.get(self.url + '?username=' + self.username + '&api_key=' + self.api_key + '&in_message='+ u'régisèter' + '&mobile_phone=4915738710431'))



class AreaResourceTest(ResourceTestCase):

    def setUp(self):
        super(AreaResourceTest, self).setUp()

        # Create a user.
        self.username = u'john'
        self.password = u'doe'
        self.user = User.objects.create_user(self.username, 'john@example.com', self.password)
        self.api_key = self.user.api_key.key
        self.c = Client()
        self.post_data = {
            'city': 'Douala',
            'country': 'Cameroon',
            'name': 'Douala4',
            'pop_per_sq_km': '12323.00',
            'overall_population': 200000
        }

        # Fetch the ``Entry`` object we'll use in testing.
        # Note that we aren't using PKs because they can change depending
        # on what other tests are running.
        self.area_1 = Area.objects.get(name="douala2")

        # We also build a detail URI, since we will be using it all over.
        # DRY, baby. DRY.
        self.detail_url = '/api/v1/areas/{0}/'.format(self.area_1.pk)
    
    def test_accent(self):
        url = '/api/v1/incoming-sms/?username=' + self.username + '&api_key=' + self.api_key + '&in_message=' + u'régistèr' + '&mobile_phone=4915738710431'
        resp = self.c.get(url)
        print url
        self.assertValidJSONResponse(resp)


    '''
    def get_credentials(self):
        return {"username": self.username, "api_key": self.api_key}
    
    def test_get_list_unauthorzied(self):
        """Get areas from the API without authenticated"""
        self.assertHttpUnauthorized(self.c.get('/api/v1/areas/'))

    def test_get_list_json(self):
        """Get areas from the API with authenticated. With checks if all keys are available"""
        resp = self.c.get('/api/v1/areas/', self.get_credentials())
        self.assertValidJSONResponse(resp)

        # Scope out the data for correctness.
        self.assertEqual(len(self.deserialize(resp)['objects']), 6)


    def test_get_detail_unauthenticated(self):
        """Try to Get a single area from the API without authenticated"""
        self.assertHttpUnauthorized(self.c.get(self.detail_url))

    def test_get_detail_json(self):
        """Get a single area from the API with authenticated. With checks if all keys are available"""
        resp = self.c.get(self.detail_url, self.get_credentials())
        self.assertValidJSONResponse(resp)

        # We use ``assertKeys`` here to just verify the keys, not all the data.
        self.assertKeys(self.deserialize(resp), ['id', 'city', 'country', 'name', 'pop_per_sq_km', 'overall_population', 'resource_uri'])
        self.assertEqual(self.deserialize(resp)['name'], "douala2")

    def test_post_list_unauthenticated(self):
        """Try to Post a single area to the API without authenticated"""
        self.assertHttpMethodNotAllowed(self.c.post('/api/v1/areas/', data=self.post_data))

    def test_post_list(self):
        """Try to Post a single area to the API with authenticated"""
        self.assertHttpMethodNotAllowed(self.c.post('/api/v1/areas/?username=' + self.username + '&api_key=' + self.api_key, data=json.dumps(self.post_data), content_type="application/json"))

    def test_put_detail_unauthenticated(self):
        """Try to Put a single area is not allowed from the API with authenticated"""
        self.assertHttpMethodNotAllowed(self.c.put(self.detail_url))

    def test_put_detail(self):
        """Try to Put a single area is not allowed from the API with authenticated"""
        self.assertHttpMethodNotAllowed(self.c.put(self.detail_url, self.get_credentials()))

    def test_delete_detail_unauthenticated(self):
        """Try to Delete a single area is not allowed from the API without authenticated"""
        self.assertHttpMethodNotAllowed(self.c.delete(self.detail_url))

    def test_delete_detail(self):
        """Try to Delete a single area is not allowed from the API with authenticated"""
        self.assertHttpMethodNotAllowed(self.c.delete(self.detail_url, self.get_credentials()))
    '''

class ContributorResourceTest(ResourceTestCase):

    def setUp(self):
        super(ContributorResourceTest, self).setUp()

        # Create a user.
        self.username = u'john'
        self.password = u'doe'
        self.email = u'john@example.com'
        self.user = User.objects.create_user(self.username, self.email, self.password)
        self.api_key = self.user.api_key.key
        self.c = Client()
        self.post_data = {
            'name': 'james',
            'email': 'james@example.com',
            'password': self.user.__dict__["password"],
            'language': 'DE'
        }
        self.put_data = {
            'email': 'jonny@example.com',
            'language': 'DE'
        }

        # Fetch the ``Entry`` object we'll use in testing.
        # Note that we aren't using PKs because they can change depending
        # on what other tests are running.
        self.contributor_1 = Contributor(name="Tobias", email="tobias@test.de")
        self.contributor_1.set_password("tobias")
        self.contributor_1.save()

        # We also build a detail URI, since we will be using it all over.
        # DRY, baby. DRY.
        self.list_url = '/api/v1/contributors/'
        self.detail_url = '{0}{1}/'.format(self.list_url, self.contributor_1.pk)

    def get_credentials(self):
        return {"username": self.username, "api_key": self.api_key}

    def test_get_list_unauthorzied(self):
        """Get areas from the API without authenticated"""
        self.assertHttpUnauthorized(self.c.get(self.list_url))

    def test_get_list_json(self):
        """Get users from the API with authenticated. With checks if all keys are available"""
        resp = self.c.get(self.list_url, self.get_credentials())
        self.assertValidJSONResponse(resp)

        # Scope out the data for correctness.
        self.assertEqual(len(self.deserialize(resp)['objects']), 1)
        # Here, we're checking an entire structure for the expected data.
        self.assertEqual(self.deserialize(resp)['objects'][0], {
            'id': '1',
            'name': 'Tobias',
            'email': 'tobias@test.de',
            'password': settings.DUMMY_PASSWORD,
            'resource_uri': self.detail_url,
            'language': 'EN',  # EN is the default value
            'frequency': 1
        })

    def test_get_detail_unauthenticated(self):
        """Try to Get a single user from the API without authenticated"""
        self.assertHttpUnauthorized(self.c.get(self.detail_url))

    def test_get_detail_json(self):
        """Get a single user from the API with authenticated. With checks if all keys are available"""
        resp = self.c.get(self.detail_url, self.get_credentials())
        self.assertValidJSONResponse(resp)

        # We use ``assertKeys`` here to just verify the keys, not all the data.
        self.assertKeys(self.deserialize(resp), ['id', 'name', 'email', 'password', 'resource_uri', 'language', 'frequency'])
        self.assertEqual(self.deserialize(resp)['name'], "Tobias")

    def test_post_list_unauthenticated(self):
        """Try to Post a single user to the API without authenticated"""
        self.assertHttpUnauthorized(self.c.post(self.list_url, data=self.post_data))

    def test_post_list_without_permissions(self):
        """Try to Post a single user to the API with authenticated and without permission"""
        self.assertHttpUnauthorized(self.c.post(self.list_url + '?username=' + self.username + '&api_key=' + self.api_key, data=json.dumps(self.post_data), content_type="application/json"))

    def test_post_list_with_permissions(self):
        """Try to Post a single user to the API with authenticated and permission"""
        add_contributor = Permission.objects.get(codename="add_contributor")
        self.user.user_permissions.add(add_contributor)
        self.assertEqual(Contributor.objects.count(), 1)
        self.assertHttpCreated(self.c.post(self.list_url + '?username=' + self.username + '&api_key=' + self.api_key, data=json.dumps(self.post_data), content_type="application/json"))
        self.assertEqual(Contributor.objects.count(), 2)

    def test_put_detail_unauthenticated(self):
        """Try to Put a single user is not allowed from the API with authenticated"""
        self.assertHttpUnauthorized(self.c.put(self.detail_url))

    def test_put_detail_without_permission(self):
        """Try to Put a single user is not allowed from the API with authenticated and without permission"""
        self.assertHttpUnauthorized(self.c.put(self.detail_url, self.get_credentials()))

    def test_put_detail_with_permission(self):
        """Try to Put a single user is not allowed from the API with authenticated abd permission"""
        change_contributor = Permission.objects.get(codename="change_contributor")
        self.user.user_permissions.add(change_contributor)
        self.assertEqual(Contributor.objects.count(), 1)
        self.assertHttpAccepted(self.c.put(self.detail_url + '?username=' + self.username + '&api_key=' + self.api_key, data=json.dumps(self.put_data), content_type="application/json"))
        self.assertEqual(Contributor.objects.count(), 1)
        self.assertEqual(Contributor.objects.get(pk=self.contributor_1.pk).email, self.put_data.get("email"))

    def test_delete_detail_unauthenticated(self):
        """Delete a single user is not allowed from the API without authenticated"""
        self.assertHttpUnauthorized(self.c.delete(self.detail_url))

    def test_delete_detail_without_permission(self):
        """Delete a single user is allowed from the API with authenticated"""
        self.assertEqual(Contributor.objects.count(), 1)
        self.assertHttpUnauthorized(self.c.delete(self.detail_url, self.get_credentials()))
        self.assertEqual(Contributor.objects.count(), 1)

    def test_delete_detail_with_permision(self):
        """Delete a single user is allowed from the API with authenticated"""
        delete_contributor = Permission.objects.get(codename="delete_contributor")
        self.user.user_permissions.add(delete_contributor)
        self.assertEqual(Contributor.objects.count(), 1)
        self.assertHttpAccepted(self.c.delete(self.detail_url, self.get_credentials()))
        self.assertEqual(Contributor.objects.count(), 0)

    def test_check_password(self):
        """Check that the password of the Contributor is right"""
        check_password_url = self.detail_url + "check_password/"
        credentials = self.get_credentials()
        # Check if only authorized can access this url
        self.assertHttpUnauthorized(self.c.get(check_password_url))

        # Test with credentials and wrong password
        credentials_and_wrong_password = credentials
        credentials_and_wrong_password.update({"password": "wrong_tobias"})
        resp = self.c.get(check_password_url, credentials_and_wrong_password)
        self.assertHttpOK(resp)
        self.assertValidJSONResponse(resp)
        self.assertEqual(self.deserialize(resp)['password_valid'], False)

        # Test with credentials and right password
        credentials_and_password = credentials
        credentials_and_password.update({"password": "tobias"})
        resp = self.c.get(check_password_url, credentials_and_password)
        self.assertHttpOK(resp)
        self.assertValidJSONResponse(resp)
        self.assertEqual(self.deserialize(resp)['password_valid'], True)

        # Update password with put and chek password again
        change_contributor = Permission.objects.get(codename="change_contributor")
        self.user.user_permissions.add(change_contributor)
        self.assertHttpAccepted(self.c.put(self.detail_url + '?username=' + self.username + '&api_key=' + self.api_key, data=json.dumps({"password": "newpassword"}), content_type="application/json"))

        credentials_and_updated_password = credentials
        credentials_and_updated_password.update({"password": "newpassword"})
        resp = self.c.get(check_password_url, credentials_and_updated_password)
        self.assertHttpOK(resp)
        self.assertValidJSONResponse(resp)
        self.assertEqual(self.deserialize(resp)['password_valid'], True)


class DeviceResourceTest(ResourceTestCase):

    def setUp(self):
        super(DeviceResourceTest, self).setUp()

        # Create a user.
        self.username = u'john'
        self.password = u'doe'
        self.email = u'john@example.com'
        self.user = User.objects.create_user(self.username, self.email, self.password)
        self.api_key = self.user.api_key.key
        self.c = Client()
        self.post_data = {
            'category': 'SubDevice',
            'phone_number': '12381294323',
        }
        self.put_data = {
            'phone_number': "4267486238"
        }

        Contributor(name="Tobias", email="tobias@test.de").save()
        self.contributor = Contributor.objects.get(pk=1)

        Device(phone_number="01234567890", category="MainDevice", contributor=self.contributor).save()
        # Fetch the ``Entry`` object we'll use in testing.
        # Note that we aren't using PKs because they can change depending
        # on what other tests are running.
        self.device_1 = Device.objects.get(pk=1)

        # We also build a detail URI, since we will be using it all over.
        # DRY, baby. DRY.
        self.list_url = u'/api/v1/devices/'
        self.detail_url = u'{0}{1}/'.format(self.list_url, self.device_1.pk)
        self.user_url = u'/api/v1/contributors/{0}/'.format(self.contributor.id)

    def get_credentials(self):
        return {"username": self.username, "api_key": self.api_key}

    def test_get_list_unauthorzied(self):
        """Get devices from the API without authenticated"""
        self.assertHttpUnauthorized(self.c.get(self.list_url))

    def test_get_list_json(self):
        """Get devices from the API with authenticated. With checks if all keys are available."""
        resp = self.c.get(self.list_url, self.get_credentials())
        self.assertValidJSONResponse(resp)

        # Scope out the data for correctness.
        self.assertEqual(len(self.deserialize(resp)['objects']), 1)
        # Here, we're checking an entire structure for the expected data.
        self.assertEqual(self.deserialize(resp)['objects'][0], {
            u"category": u"MainDevice",
            u"phone_number": u"01234567890",
            u"resource_uri": self.detail_url,
            u"contributor": self.user_url
        })

    def test_get_detail_unauthenticated(self):
        """Try to Get a single device from the API without authentication"""
        self.assertHttpUnauthorized(self.c.get(self.detail_url))

    def test_get_detail_json(self):
        """Get a single device from the API with authentication. Also checks if all keys are available."""
        resp = self.c.get(self.detail_url, self.get_credentials())
        self.assertValidJSONResponse(resp)

        # We use ``assertKeys`` here to just verify the keys, not all the data.
        self.assertKeys(self.deserialize(resp), ['category', 'phone_number', 'resource_uri', 'contributor'])
        self.assertEqual(self.deserialize(resp)['category'], "MainDevice")

    def test_post_list_unauthenticated(self):
        """Try to Post a single device to the API without authenticated"""
        self.assertHttpUnauthorized(self.c.post(self.list_url, data=self.post_data))

    def test_post_list_without_permissions(self):
        """Try to Post a single device to the API with authenticated and without permission"""
        self.assertHttpUnauthorized(self.c.post(self.list_url + '?username=' + self.username + '&api_key=' + self.api_key, data=json.dumps(self.post_data), content_type="application/json"))

    def test_post_list_with_permissions(self):
        """Post a single device to the API with authenticated and permission"""
        add_device = Permission.objects.get(codename="add_device")
        self.user.user_permissions.add(add_device)
        self.assertEqual(Device.objects.count(), 1)
        self.assertHttpCreated(self.c.post(self.list_url + '?username=' + self.username + '&api_key=' + self.api_key, data=json.dumps(self.post_data), content_type="application/json"))
        self.assertEqual(Device.objects.count(), 2)

    def test_put_detail_unauthenticated(self):
        """Try to Put a single device is not allowed from the API with authenticated"""
        self.assertHttpUnauthorized(self.c.put(self.detail_url))

    def test_put_detail_without_permission(self):
        """Try to Put a single device is not allowed from the API with authenticated and without permission"""
        self.assertHttpUnauthorized(self.c.put(self.detail_url, self.get_credentials()))

    def test_put_detail_with_permission(self):
        """Put a single device is not allowed from the API with authenticated abd permission"""
        change_device = Permission.objects.get(codename="change_device")
        self.user.user_permissions.add(change_device)
        self.assertEqual(Device.objects.count(), 1)
        self.assertHttpAccepted(self.c.put(self.detail_url + '?username=' + self.username + '&api_key=' + self.api_key, data=json.dumps(self.put_data), content_type="application/json"))
        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(Device.objects.get(pk=self.device_1.pk).phone_number, self.put_data.get("phone_number"))

    def test_delete_detail_unauthenticated(self):
        """Delete a single device is not allowed from the API without authenticated"""
        self.assertHttpUnauthorized(self.c.delete(self.detail_url))

    def test_delete_detail_without_permission(self):
        """Delete a single device is not allowed from the API with authenticated and without permission"""
        self.assertHttpUnauthorized(self.c.delete(self.detail_url, self.get_credentials()))

    def test_delete_detail_with_permission(self):
        """Delete a single device is not allowed from the API with authenticated and permission"""
        delete_device = Permission.objects.get(codename="delete_device")
        self.user.user_permissions.add(delete_device)
        self.assertEqual(Device.objects.count(), 1)
        self.assertHttpAccepted(self.c.delete(self.detail_url, self.get_credentials()))
        self.assertEqual(Device.objects.count(), 0)


class MessagingTestCase(unittest.TestCase):
    # We have to run this test only in the complete test env is depends
    # on it or we flush the database if come to this test
    def setUp(self):
        fixtures = ['test_data.json']
        self.register_keyword = "register"
        self.unregister_keyword = "stop"
        self.contribute_keyword = "contribute"

        self.register_test_user_no = "45738710431"

        self.unregister_test_user_name = "testuser"
        self.unregister_test_user_email = "testuser@test.com"
        self.unregister_test_user_password = "testpassword"
        self.unregister_test_user_no = "415738710431"
        self.help_no = "915738710431"

        self.contribute_duration = "60"
        self.contribute_area = Area.objects.all()[0].name

    def test_register(self):
        contributors = Contributor.objects.all()
        nb_contributors = len(contributors)

        devices = Device.objects.all()
        nb_devices = len(devices)
        receive_sms(self.register_test_user_no, self.register_keyword)
        contributors = Contributor.objects.all()
        devices = Device.objects.all()
        self.assertEqual(len(contributors), nb_contributors + 1)

        device = Device.objects.get(phone_number=self.register_test_user_no)
        contributor = Contributor.objects.get(name=self.register_test_user_no)
        self.assertEqual(contributor.refunds, 1)
        self.assertEqual(device.phone_number, self.register_test_user_no)

    def test_unregister(self):
        devices = Device.objects.all()
        nb_devices = len(devices)
        contributors = Contributor.objects.all()
        nb_contributors = len(contributors)

        #Registering a User
        receive_sms(self.unregister_test_user_no, "register")
        devices = Device.objects.all()
        contributors = Contributor.objects.all()
        self.assertEqual(len(devices), nb_devices + 1)
        self.assertEqual(len(contributors), nb_contributors + 1)
        #Unregistering a user
        receive_sms(self.unregister_test_user_no, self.unregister_keyword)

        devices = Device.objects.all()
        contributors = Contributor.objects.all()
        self.assertEqual(len(devices), nb_devices)
        self.assertEqual(len(contributors), nb_contributors)

    def test_help(self):
        devices = Device.objects.all()
        contributors = Contributor.objects.all()
        nb_devices = len(devices)
        nb_contributors = len(contributors)

        contributor = Contributor(name=self.unregister_test_user_name, email=self.unregister_test_user_email, password=self.unregister_test_user_password)
        contributor.save()
        device = Device(phone_number=self.help_no, contributor=contributor)
        device.save()
                            
        receive_sms(self.help_no, "help")
        devices = Device.objects.all()
        contributors = Contributor.objects.all()
        self.assertEqual(len(devices), nb_devices + 1)
        self.assertEqual(len(contributors), nb_contributors + 1)

    def test_invalid(self):
        devices = Device.objects.all()
        nb_devices = len(devices)
        contributors = Contributor.objects.all()
        nb_contributors = len(contributors)

        #English SMS
        receive_sms("889383849", "lkjasdlkajs akjkdlaksjdui akjdlkasd")
        devices = Device.objects.all()
        contributors = Contributor.objects.all()
        self.assertEqual(len(devices), nb_devices + 1)
        self.assertEqual(len(contributors), nb_contributors + 1)

        #French SMS
        nb_messages = len(Message.objects.all())
        receive_sms("789383849", "ça a marché")
        messages = Message.objects.all()
        self.assertEqual(len(messages), nb_messages + 1)
    
    
    def test_sendSMS(self):
        msg = "hi from feowl"
        bad_phone = "915738710431"
        send_sms(bad_phone, msg)

        good_phone = "4915738710431"
        #send_sms(good_phone, "lmt")
        #send_sms(good_phone, "nexmo")


#############################################

    def test_zcontribute(self):
        #contribute_msg = (self.contribute_keyword + " " +
                #self.contribute_area + " " + self.contribute_duration)
        contribute_msg = "pc douala2 100"

        # Missing enquiry - Contribution not accepted
        receive_sms(self.register_test_user_no, self.register_keyword)
        reports = PowerReport.objects.all()
        nb_reports = reports.count()
        receive_sms(self.register_test_user_no, contribute_msg)
        reports = PowerReport.objects.all()
        self.assertEqual(len(reports), nb_reports)

        # With enquiry from today - Contribution accepted
        contributor = Contributor.objects.get(name=self.register_test_user_no)
        contributor.enquiry = datetime.today().date()
        contributor.save()
        
        old_refund = contributor.refunds

        receive_sms(self.register_test_user_no, contribute_msg)
        reports = PowerReport.objects.all()
        self.assertEqual(len(reports), nb_reports + 1)
        contributor = Contributor.objects.get(name=self.register_test_user_no)
        new_refund = contributor.refunds
        #self.assertEqual(new_refund, old_refund + 1)
        report = reports.latest("happened_at")
        self.assertEqual(report.has_experienced_outage, True)

        # Reset the response time in the db
        contributor.response = datetime.today().date() - timedelta(days=1)
        contributor.save()

        # Test the wrong message
        reports = PowerReport.objects.all()
        nb_reports = reports.count()
        receive_sms(self.register_test_user_no, "pc doulan malskd oskjajhads33 d akjs")
        reports = PowerReport.objects.all()
        self.assertEqual(len(reports), nb_reports)
        
        # Reset the response time in the db
        contributor.response = datetime.today().date() - timedelta(days=1)
        contributor.save()
        
        # Multiple message
        multi_contribute_msg = "pc doualaI 29, douala2 400  douala3 10 - alger 403"
        reports = PowerReport.objects.all()
        nb_reports = reports.count()
        contributor = Contributor.objects.get(name=self.register_test_user_no)
        refund = contributor.refunds
        receive_sms(self.register_test_user_no, multi_contribute_msg)
        reports = PowerReport.objects.all()
        self.assertEqual(len(reports), nb_reports + 4)
        print 'Multiple Messages has been contributed'

        contributor = Contributor.objects.get(name=self.register_test_user_no)
        #self.assertEqual(contributor.refunds, refund + 4)
        contributor.response = datetime.today().date() - timedelta(days=1)
        contributor.save()

        # Test the no method if the reports wrong
        nb_reports1 = PowerReport.objects.all().count()
        receive_sms(self.register_test_user_no, "pc no")
        nb_reports2 = PowerReport.objects.all().count()
        self.assertEqual(nb_reports2, nb_reports1 + 1)
        report = reports.latest("happened_at")
        self.assertEqual(report.has_experienced_outage, False)




'''
        # No space after the comma
        multi_contribute_msg = (self.contribute_keyword + " " +
                self.contribute_area + " " + self.contribute_duration + "," +
                self.contribute_area + " " + self.contribute_duration)

        receive_sms(self.register_test_user_no, multi_contribute_msg)
        reports = PowerReport.objects.all()
        self.assertEqual(len(reports), 10)
        contributor = Contributor.objects.get(name=self.register_test_user_no)
        self.assertEqual(contributor.refunds, 4)
'''



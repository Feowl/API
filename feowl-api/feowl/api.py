# -*- encoding:utf-8 -*-
from tastypie import fields
from tastypie.authorization import DjangoAuthorization
#TODO: Should changed back with Version 0.9.12 of tastypie
# from tastypie.authentication import ApiKeyAuthentication
from authentication import ApiKeyAuthentication
from tastypie.resources import Resource, ModelResource, ALL

from django.conf import settings
from django.conf.urls.defaults import url
from django.contrib.auth.hashers import make_password, check_password
from django.core.exceptions import ObjectDoesNotExist

from decimal import *

from forms import PowerReportForm, DeviceForm, ContributorForm, AreaForm
from models import PowerReport, Device, Contributor, Area
from validation import ModelFormValidation
from serializers import CSVSerializer
import sms_helper
import simplejson
import logging

logger = logging.getLogger(__name__)



class ContributorResource(ModelResource):
    class Meta:
        queryset = Contributor.objects.all()
        resource_name = 'contributors'

        authentication = ApiKeyAuthentication()
        authorization = DjangoAuthorization()
        validation = ModelFormValidation(form_class=ContributorForm)

        fields = ['id', 'email', 'password', 'name', 'language', 'frequency', 'response', 'enquiry']

        list_allowed_methods = ['get', 'post']
        detail_allowed_methods = ['get', 'put', 'delete']

        filtering = {
            "credibility": ALL,
            "language": ALL,
            "name": ALL,
            "email": ALL,
        }

    def override_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<pk>\d+?)/check_password/$" % self._meta.resource_name, self.wrap_view('check_password'), name="api_check_password"),
        ]

    def check_password(self, request, **kwargs):
        '''
        method to verify a raw password against the saved encrypted one (only use through SSL!)
        '''
        #TODO: Check the function for a password change with put
        self.method_check(request, allowed=['get'])
        self.is_authenticated(request)
        self.throttle_check(request)

        try:
            obj = self.cached_obj_get(request=request, **self.remove_api_resource_names(kwargs))
        except ObjectDoesNotExist:
            return HttpGone()
        except MultipleObjectsReturned:
            return HttpMultipleChoices("More than one resource is found at this URI.")

        valid = check_password(request.GET.get('password'), obj.password)

        self.log_throttled_access(request)

        bundle = self.build_bundle(obj=obj, request=request)
        bundle = self.full_dehydrate(bundle)
        bundle = self.alter_detail_data_to_serialize(request, bundle)

        #add out result
        bundle.data['password_valid'] = valid
        bundle.data['password'] = settings.DUMMY_PASSWORD
        return self.create_response(request, bundle)

    def hydrate_password(self, bundle):
        """Turn a passed in password into a hash so it is not saved raw."""
        #TODO: If statement should not more needed with the next version of tastypie
        pwd = str(bundle.data.get('password'))
        if not pwd.startswith('pbkdf2_sha256$') and not pwd.endswith('='):
            bundle.data['password'] = make_password(bundle.data.get('password'))
        return bundle

    def dehydrate_password(self, bundle):
        return settings.DUMMY_PASSWORD

    def obj_create(self, bundle, request=None, **kwargs):
        from django.db import IntegrityError
        from tastypie.exceptions import BadRequest
        try:
            bundle = super(ContributorResource, self).obj_create(bundle, request, **kwargs)
        except IntegrityError, e:
            msg = ""
            if e.message.find("name") != -1:
                msg = 'That name already exists'
            elif e.message.find("email") != -1:
                msg = 'That email already exists'
            raise BadRequest(msg)
        return bundle


class DeviceResource(ModelResource):
    contributor = fields.ForeignKey(ContributorResource, 'contributor', null=True)

    class Meta:
        queryset = Device.objects.all()
        resource_name = 'devices'

        authentication = ApiKeyAuthentication()
        authorization = DjangoAuthorization()

        validation = ModelFormValidation(form_class=DeviceForm)

        fields = ['category', 'phone_number', 'contributor']

        list_allowed_methods = ['get', 'post']
        detail_allowed_methods = ['get', 'put', 'delete']

        filtering = {
            'contributor': ALL  # ALL_WITH_RELATIONS ?
        }


class AreaResource(ModelResource):
    class Meta:
        queryset = Area.objects.all()
        resource_name = 'areas'

        authentication = ApiKeyAuthentication()
        authorization = DjangoAuthorization()

        validation = ModelFormValidation(form_class=AreaForm)

        fields = ['id', 'name', 'city', 'country', 'pop_per_sq_km', 'overall_population']

        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']

        #allow filtering on the collection to do things like /api/v1/areas/?name_ilike=douala
        filtering = {
            'name': ALL,
            'country': ALL,
            'overall_population': ALL
        }


class PowerReportResource(ModelResource):
    area = fields.ForeignKey(AreaResource, 'area', null=False)
    contributor = fields.ForeignKey(ContributorResource, 'contributor', null=True)
    device = fields.ForeignKey(DeviceResource, 'device', null=True)

    class Meta:
        queryset = PowerReport.objects.all()
        resource_name = 'reports'

        #see: http://www.infoq.com/news/2010/01/rest-api-authentication-schemes
        authentication = ApiKeyAuthentication()
        authorization = DjangoAuthorization()

        validation = ModelFormValidation(form_class=PowerReportForm)

        serializer = CSVSerializer()

        #whitelist of fields to be public
        fields = ['quality', 'duration', 'happened_at', 'has_experienced_outage', 'location', 'area', 'contributor', 'device']

        list_allowed_methods = ['get', 'post']
        detail_allowed_methods = ['get']

        filtering = {
            'quality': ALL,
            'duration': ALL,
            'happened_at': ALL,
            'area': ALL,
            'contributor': ALL
        }

        ordering = ['quality', 'duration', 'happened_at', 'area', 'contributor']


class GenericResponseObject(object):
    '''
    generic object to represent dict values as attributes (returned as tastypie response object)
    '''
    def __init__(self, initial=None):
        self.__dict__['_data'] = {}

        if hasattr(initial, 'items'):
            self.__dict__['_data'] = initial

    def __getattr__(self, name):
        return self._data.get(name, None)

    def __setattr__(self, name, value):
        self.__dict__['_data'][name] = value

    def to_dict(self):
        return self._data


class PowerReportAggregatedResource(Resource):
    area = fields.ForeignKey(AreaResource, 'area', help_text="The area the data is about")
    avg_duration = fields.DecimalField('avg_duration', help_text="Average duration of a power cut over all power cuts")
    pos_neg_ratio = fields.DecimalField('pos_neg_ratio', help_text="An approximate percentage of the people in the area that are affected by power cuts.")

    nb_reports = fields.DecimalField('nb_reports', help_text="total number of contributions in the given area")
    nb_reports_t0 = fields.DecimalField('nb_reports_t0', help_text="number of contributions with a duration of less than 30min")
    nb_reports_t1 = fields.DecimalField('nb_reports_t1', help_text="number of contributions with a duration between 30 min and 2 h")
    nb_reports_t2 = fields.DecimalField('nb_reports_t2', help_text="number of contributions with a duration between 2 h and 4h")
    nb_reports_t3 = fields.DecimalField('nb_reports_t3', help_text="number of contributions with a duration that is greater than 4 hours")

    class Meta:
        resource_name = 'reports-aggregation'
        object_class = GenericResponseObject
        include_resource_uri = False

        list_allowed_methods = ['get']
        detail_allowed_methods = []

        authentication = ApiKeyAuthentication()
        authorization = DjangoAuthorization()

        #TODO: we need a custom validation class for this as there is no model...
    def dispatch_list_aggregated(self, request, resource_name, **kwargs):
        return self.dispatch_list(request, **kwargs)

#    def obj_get(self, request=None, **kwargs):
#        #tastypie method override
#        return PowerReportResource().obj_get(request, **kwargs)

    def obj_get_list(self, request=None, **kwargs):
        #tastypie method override
        obj_list = PowerReportResource().obj_get_list(request, **kwargs)
        return self.aggregate_reports(obj_list)

    def aggregate_reports(self, filtered_objects):
        result = []

        #get all areas
        areas = Area.objects.all()

        getcontext().prec = 2

        for area in areas:
            #get reports in each area
            area_reports = filtered_objects.filter(area=area.id)
            actual_powercut_reports = filtered_objects.filter(area=area.id, has_experienced_outage=True)

            #average power cut duration
            avg_duration = 0
            if len(actual_powercut_reports):
                for r in actual_powercut_reports:
                    avg_duration += r.duration
                avg_duration = Decimal(avg_duration) / Decimal(len(actual_powercut_reports))

            #ratio of power cut to non-power cut reports
            pos_neg_ratio = 0
            if len(area_reports) and len(actual_powercut_reports):
                pos_neg_ratio = Decimal(len(actual_powercut_reports)) / Decimal(len(area_reports))

            #Total number of reports
            if len(area_reports):
                nb_reports = len(actual_powercut_reports)

            #Number of contributions per duration level
            if len(area_reports) and len(actual_powercut_reports):
                nb_reports_t0 = len(actual_powercut_reports.filter(duration__lt=30))
                nb_reports_t1 = len(actual_powercut_reports.filter(duration__gte=30, duration__lt=120))
                nb_reports_t2 = len(actual_powercut_reports.filter(duration__gte=120, duration__lt=240))
                nb_reports_t3 = len(actual_powercut_reports.filter(duration__gte=240))

            #create aggregate object
            result.append(GenericResponseObject({
            'area': area,
            'avg_duration': avg_duration,
            'pos_neg_ratio': pos_neg_ratio,
            'nb_reports': nb_reports,
            'nb_reports_t0': nb_reports_t0,
            'nb_reports_t1': nb_reports_t1,
            'nb_reports_t2': nb_reports_t2,
            'nb_reports_t3': nb_reports_t3
            }))
        return result


class PowerCutDurations(Resource):
    quintile = fields.IntegerField('quintile', help_text="Average duration of a power cut over all power cuts")
    lower_bound = fields.IntegerField('lower_bound', help_text="An approximate percentage of the people in the area that are affected by power cuts.")
    upper_bound = fields.IntegerField('upper_bound', help_text="An approximate percentage of the people in the area that are affected by power cuts.")
    contributions = fields.IntegerField('contributions', help_text="An approximate percentage of the people in the area that are affected by power cuts.")
    proportion = fields.DecimalField('proportion', help_text="An approximate percentage of the people in the area that are affected by power cuts.")

    class Meta:
        resource_name = 'reports-distribution'
        object_class = GenericResponseObject
        include_resource_uri = False

        list_allowed_methods = ['get']
        detail_allowed_methods = []

        authentication = ApiKeyAuthentication()
        authorization = DjangoAuthorization()

        #TODO: we need a custom validation class for this as there is no model...
    def dispatch_list_aggregated(self, request, resource_name, **kwargs):
        return self.dispatch_list(request, **kwargs)

    def obj_get_list(self, request=None, **kwargs):
        # Tastypie method override
        obj_list = PowerReportResource().obj_get_list(request, **kwargs)
        return self.aggregate_distribution(obj_list)

    def aggregate_distribution(self, filtered_objects):
        from django.db.models import Max, Min
        from math import ceil

        getcontext().prec = 2

        result = []
        buckets = 5
        upper_bound = 0

        min_duration = Decimal(filtered_objects.aggregate(Min('duration')).values()[0])
        max_duration = Decimal(filtered_objects.aggregate(Max('duration')).values()[0])

        width = ceil((max_duration - min_duration) / buckets)
        powercuts = len(filtered_objects)

        for quintile in range(buckets):
            lower_bound = upper_bound
            upper_bound = lower_bound + width

            contributions = 0
            for powercut in filtered_objects:
                if (lower_bound < powercut.duration <= upper_bound):
                    contributions += 1

            proportion = Decimal(contributions) / powercuts

            # create aggregate object
            result.append(GenericResponseObject({'upper_bound': upper_bound, 'lower_bound': lower_bound, 'contributions': contributions, 'proportion': proportion, 'quintile': quintile + 1}))
        return result


class IncomingSmsResource(Resource):
    class Meta:
        resource_name = 'incoming-sms'
        object_class = GenericResponseObject
        #include_resource_uri = False

        list_allowed_methods = ['post', 'get']
        detail_allowed_methods = []

        authentication = ApiKeyAuthentication()
        authorization = DjangoAuthorization()

    def obj_create(self, bundle, request=None, **kwargs):
        self.read_sms_from_url(request)
        bundle.obj = bundle = self.build_bundle(request=request)
        return bundle

    def obj_get_list(self, request=None, **kwargs):
        return self.read_sms_from_url(request)

    def read_sms_from_url(self, request):
        response = []
        request.encoding = 'latin-1'
        msg = request.GET.get('in_message', '')
        try:
            logger.info('Before Request encoding - Type: {0}'.format(type(msg)))
            logger.info('Before Message decoding- Type: {0}'.format(type(msg)))
            msg = msg.encode('latin-1')
            logger.info('After decoding - Type: {0}'.format(type(msg)))
        except Exception, e:
            msg = request.GET.get('in_message', 'no message')
            logger.info('Undecoded Message: {0}'.format(e))
        phone = request.GET.get('mobile_phone', '')
        if (not phone) or (not msg):
            logger.error('Mobile Phone or Message are incorrect. Message is: {0}'.format(msg))
            response.append(GenericResponseObject({'response': 'Mobile Phone or Message are incorrects'}))
            raise ValueError('Mobile Phone or Message are incorrect. Message is: {0}'.format(msg))
        else:
            sms_helper.receive_sms(phone, msg)
            response.append(GenericResponseObject({'response': 'message received succesfully'}))
            logger.info('message received successfully')
        return response

    def get_resource_uri(self, bundle_or_obj):
        return '/api/v1/%s/%s/' % (self._meta.resource_name, bundle_or_obj.obj.id)

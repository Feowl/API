from django.conf.urls import patterns, include, url
from django.contrib import admin
from tastypie.api import Api
from feowl.api import (PowerReportResource, PowerReportAggregatedResource,
    DeviceResource, ContributorResource, AreaResource, PowerCutDurations, IncomingSmsResource)

admin.autodiscover()

# bind all resources together for our API
v1_api = Api(api_name='v1')
v1_api.register(PowerReportResource())
v1_api.register(PowerReportAggregatedResource())
v1_api.register(DeviceResource())
v1_api.register(ContributorResource())
v1_api.register(AreaResource())
v1_api.register(PowerCutDurations())
v1_api.register(IncomingSmsResource())

urlpatterns = patterns('',
    url(r'^grappelli/', include('grappelli.urls')),
    url(r'^api/', include(v1_api.urls)),
    url(r'^admin/translation/', include('rosetta.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^rosetta/', include('rosetta.urls')),
)

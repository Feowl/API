from __future__ import division

from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.contrib.auth.hashers import make_password
from datetime import datetime
from email_helper import send_email
import settings

from tastypie.models import create_api_key
models.signals.post_save.connect(create_api_key, sender=User)

import logging

logger = logging.getLogger(__name__)

SMS = 0
EMAIL = 1
CHANNEL_CHOICES = (
    (SMS, "SMS"),
    (EMAIL, "Email")
)


def get_sentinel_user():
    return Contributor.objects.get_or_create(name=settings.ANONYMOUS_USER_NAME, email=settings.ANONYMOUS_EMAIL)[0]


class Contributor(models.Model):
    """Model for a contributor"""
    OFF = 0
    DAILY = 1
    WEEKLY = 2
    MONTHLY = 3
    FREQUENCY_CHOICES = (
        (OFF, 'Off'),
        (DAILY, 'Daily'),
        (WEEKLY, 'Weekly'),
        (MONTHLY, 'Monthly')
    )
    ACTIVE = 0
    INACTIVE = 1
    UNKNOWN = 2
    STATUS_CHOICES = (
        (ACTIVE, "Active"),
        (INACTIVE, "Inactive "),
        (UNKNOWN, "Unknown")
    )

    name = models.CharField('name', max_length=30, unique=True,
        help_text='Required. 30 characters or fewer. Letters, numbers and '
                    '@/./+/-/_ characters', blank=True)
    password = models.CharField('password', max_length=128, blank=True)
    email = models.EmailField('e-mail address', blank=True, unique=True, editable=False)

    credibility = models.DecimalField(max_digits=3, decimal_places=2, default='1.00', blank=True)
    language = models.CharField(max_length=5, default="EN", blank=True)
    enquiry = models.DateField(null=True, blank=True)
    response = models.DateField(null=True, blank=True)
    frequency = models.PositiveIntegerField(choices=FREQUENCY_CHOICES, default=DAILY, blank=True)
    channel = models.PositiveIntegerField(choices=CHANNEL_CHOICES, default=EMAIL, blank=True)
    refunds = models.PositiveIntegerField(default=0, blank=True)
    status = models.PositiveIntegerField(choices=STATUS_CHOICES, default=ACTIVE, blank=True)

    total_response = models.PositiveIntegerField(default=0, blank=True)
    total_enquiry = models.PositiveIntegerField(default=0, blank=True)

    def get_percentage_of_response(self):
        if self.total_enquiry > 0:
            percentage = self.total_response / self.total_enquiry
            return "{0}%".format(percentage)
        else:
            return "N/A"
    get_percentage_of_response.short_description = "% of Response"

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        created = self.id is not None
        super(Contributor, self).save(*args, **kwargs)
         # Send an email if this are a new contributor
        if not created:
            send_email(self.name, self.email, self.language)


class Device(models.Model):
    """Model for the Device"""

    category = models.CharField(max_length=50, blank=True)
    phone_number = models.CharField(max_length=30, blank=True)
    contributor = models.ForeignKey(Contributor, blank=True, null=True)

    def __unicode__(self):
        if self.contributor:
            return u"{0}'s {1}".format(self.contributor, self.category)
        return u"{0}".format(self.phone_number)


class Area(models.Model):
    """Model for the Area"""

    objects = models.GeoManager()

    name = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    overall_population = models.PositiveIntegerField()
    pop_per_sq_km = models.DecimalField(max_digits=8, decimal_places=2)
    geometry = models.PolygonField()

    def kml(self):
        return self.geometry.kml

    def __unicode__(self):
        return self.name


class PowerReport(models.Model):
    """Model for a power cut report"""

    objects = models.GeoManager()

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    #report_type = models.CharField(max_length=50, null=False, blank=False, choices=(('power', 'Power Cut'), ('other', 'Something else')) )
    #SRID 4326 is WGS84 is lon/lat
    #stay with geometries since they support more postgis functions
    #see: http://postgis.refractions.net/documentation/manual-1.5/ch04.html#PostGIS_GeographyVSGeometry
    quality = models.DecimalField(max_digits=4, decimal_places=2, default='-1.00', blank=True)
    duration = models.PositiveIntegerField(null=False, blank=False, help_text="Duration in minutes")
    happened_at = models.DateTimeField(auto_now=True, null=False, blank=False, help_text="Datetime preferrably with timezone")
    has_experienced_outage = models.BooleanField(null=False, blank=False, default=True, help_text="Boolean that indicates if user reported a power cut.")

    area = models.ForeignKey(Area, blank=False, null=False)
    contributor = models.ForeignKey(Contributor, blank=True, null=True, on_delete=models.SET(get_sentinel_user))
    device = models.ForeignKey(Device, blank=True, null=True)

    deleted = models.BooleanField(default=False)
    flagged = models.BooleanField(default=False)
    location = models.PointField(srid=4326, geography=False, blank=True, null=True, help_text="String in form of POINT(lon, lat)")

    def __unicode__(self):
        if self.contributor:
            return "{0} at {1}".format(self.contributor, self.happened_at)
        else:
            return "{0}".format(self.happened_at)

    def save(self, *args, **kwargs):
        today = datetime.today().date()
        msg = ""
        if self.contributor is None:
            msg = "no contributor"
            logger.error(msg)
        elif (self.contributor.enquiry == today):
                self.contributor.response = today
                self.contributor.total_response = +1
                self.contributor.save()
                super(PowerReport, self).save(*args, **kwargs)
                msg = "PowerReport Saved"
                logger.debug(msg)
        else:
            msg = "PowerReport not saved because the contributor wasn't polled today"
            logger.error(msg)
        return msg


class Message(models.Model):
    YES = 0
    MAYBE = 1
    NO = 2
    SOURCE_CHOICES = (
        (YES, "Yes"),
        (MAYBE, "Maybe"),
        (NO, "No")
    )

    created = models.DateTimeField(auto_now_add=True, null=True)
    modified = models.DateTimeField(auto_now=True, null=True)
    message = models.TextField()
    source = models.PositiveIntegerField(choices=CHANNEL_CHOICES, default=EMAIL)
    parsed = models.PositiveIntegerField(choices=SOURCE_CHOICES, default=NO)
    keyword = models.CharField(max_length=30, default="No Keyword")
    device = models.ForeignKey(Device, null=True)

    def save(self, *args, **kwargs):
        from message_helper import read_message
        created = self.id is not None
         # Send an email if this are a new contributor
        if created:
            # Contribute
            parsed = read_message(self.device.phone_number, self.message, auto_mode=False)
            self.keyword = self.message.split()[0]
            self.parsed = parsed
        super(Message, self).save(*args, **kwargs)

    def manual_parse(self):
        icon = "no"
        if self.parsed == self.YES:
            icon = "yes"
        return """<a href="{0}">{1}<img style="float:right" src="admin/img/icon-{2}.gif"/></a>""".format(self.id, self.SOURCE_CHOICES[self.parsed][1], icon)
    manual_parse.allow_tags = True
    manual_parse.admin_order_field = "parsed"

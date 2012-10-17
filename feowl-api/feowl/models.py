from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.contrib.auth.hashers import make_password

import settings

from tastypie.models import create_api_key
models.signals.post_save.connect(create_api_key, sender=User)

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
                    '@/./+/-/_ characters', blank=True, editable=False)
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

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def __unicode__(self):
        return self.name

    # def save(self):
    #     # Check if it already exist
    #     created = self.id is not None
    #     super(Contributor, self).save()
    #     # Send an email if this are a new contributor
    #     if not created:
    #         from django.core.mail import EmailMultiAlternatives
    #         from django.template import Context
    #         from django.template.loader import get_template
    #         from django.utils.translation import ugettext_lazy as _

    #         plaintext = get_template('email/registration_confirmation.txt')
    #         html = get_template('email/registration_confirmation.html')
    #         subject = _('Welcome to Feowl')

    #         d = Context({'name': self.name, 'email_language': self.language})
    #         text_content = plaintext.render(d)
    #         html_content = html.render(d)

    #         msg = EmailMultiAlternatives(subject, text_content, settings.REGISTRATION_FROM, [self.email])
    #         msg.attach_alternative(html_content, "text/html")
    #         msg.send()


class Device(models.Model):
    """Model for the Device"""

    category = models.CharField(max_length=50, blank=True)
    phone_number = models.CharField(max_length=30, blank=True)
    contributor = models.ForeignKey(Contributor, blank=True, null=True)

    def __unicode__(self):
        if self.contributor:
            return "{0}'s {1}".format(self.contributor, self.category)
        return self.category


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


class Message(models.Model):
    YES = 0
    MAYBE = 1
    NO = 2
    SOURCE_CHOICES = (
        (YES, "Yes"),
        (MAYBE, "Maybe"),
        (NO, "No")
    )

    message = models.TextField()
    source = models.PositiveIntegerField(choices=CHANNEL_CHOICES, default=EMAIL)
    parsed = models.PositiveIntegerField(choices=SOURCE_CHOICES, default=NO)
    keyword = models.CharField(max_length=30, default="No Keyword")

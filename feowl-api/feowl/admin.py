from django.conf.urls import patterns
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.gis import admin as admin_gis
from django.contrib.auth.models import User
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext, ugettext_lazy as _
from django.views.decorators.debug import sensitive_post_parameters

from feowl.models import PowerReport, Area, Device, Contributor, Message
from feowl.forms import ContributorAdminForm, VoucherForm
from feowl.sms_helper import send_sms

from tastypie.admin import ApiKeyInline
from tastypie.models import ApiAccess, ApiKey


class UserModelAdmin(UserAdmin):
    inlines = UserAdmin.inlines + [ApiKeyInline]


class ContributorAdmin(admin.ModelAdmin):
    form = ContributorAdminForm
    change_password_form = AdminPasswordChangeForm
    change_user_password_template = None
    list_display = ('name', 'email', 'channel', 'status', 'enquiry', 'response', 'total_response', 'total_enquiry', 'get_percentage_of_response', 'refunds')

    def get_urls(self):
        return patterns('',
            (r'^(\d+)/password/$',
             self.admin_site.admin_view(self.contributor_change_password))
        ) + super(ContributorAdmin, self).get_urls()

    @sensitive_post_parameters()
    def contributor_change_password(self, request, id, form_url=''):
        if not self.has_change_permission(request):
            raise PermissionDenied
        contributor = get_object_or_404(self.queryset(request), pk=id)
        if request.method == 'POST':
            form = self.change_password_form(contributor, request.POST)
            if form.is_valid():
                form.save()
                msg = ugettext('Password changed successfully.')
                messages.success(request, msg)
                return HttpResponseRedirect('..')
        else:
            form = self.change_password_form(contributor)

        fieldsets = [(None, {'fields': form.base_fields.keys()})]
        adminForm = admin.helpers.AdminForm(form, fieldsets, {})

        context = {
            'title': _('Change password: %s') % escape(contributor.name),
            'adminForm': adminForm,
            'form_url': mark_safe(form_url),
            'form': form,
            'is_popup': '_popup' in request.REQUEST,
            'add': True,
            'change': False,
            'has_delete_permission': False,
            'has_change_permission': True,
            'has_absolute_url': False,
            'opts': self.model._meta,
            'original': contributor,
            'save_as': False,
            'show_save': True,
        }
        return TemplateResponse(request, [
            self.change_user_password_template or
            'admin/auth/user/change_password.html'
        ], context, current_app=self.admin_site.name)


class MessageAdmin(admin.ModelAdmin):
    fields = ('created', 'modified', 'keyword', 'message',)
    list_display = ('message', 'keyword', 'manual_parse', 'source', 'device',)
    list_filter = ('keyword',)
    readonly_fields = ('created', 'modified', 'keyword',)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.parsed == 0:  # editing an existing object
            return self.readonly_fields + ('message',)
        return self.readonly_fields

    def get_urls(self):
        return patterns('',
            (r'^send_voucher/$',
             self.admin_site.admin_view(self.send_voucher))
        ) + super(MessageAdmin, self).get_urls()

    def send_voucher(self, request):
        if request.method == 'POST':  # If the form has been submitted...
            form = VoucherForm(request.POST)  # A form bound to the POST data
            if form.is_valid():  # All validation rules pass
                mobile_numbers = form.cleaned_data['mobile_numbers']
                voucher_text = form.cleaned_data['voucher_text']

                mobile_numbers_list = [x.strip() for x in mobile_numbers.split(',')]

                for number in mobile_numbers_list:
                    send_sms(number, voucher_text)
                return HttpResponseRedirect('..')
        else:
            form = VoucherForm()  # An unbound form

        fieldsets = [(None, {'fields': form.base_fields.keys()})]
        adminForm = admin.helpers.AdminForm(form, fieldsets, {})

        context = {
            'adminForm': adminForm,
            'form': form,
            'is_popup': '_popup' in request.REQUEST,
            'add': True,
            'change': False,
            'has_delete_permission': False,
            'has_change_permission': True,
            'has_absolute_url': False,
            'opts': self.model._meta,
            'save_as': False,
            'show_save': True,
        }
        return TemplateResponse(request, 'admin/send_voucher.html',
            context, current_app=self.admin_site.name)


class PowerReportAdmin(admin.ModelAdmin):
    list_display = ('modified', 'contributor', 'duration', 'happened_at', 'area')
    list_filter = ('contributor', 'area')

admin.site.unregister(User)
admin.site.register(User, UserModelAdmin)

admin.site.register(PowerReport,  PowerReportAdmin)
admin.site.register(Area, admin_gis.OSMGeoAdmin)
admin.site.register(Contributor, ContributorAdmin)
admin.site.register(Device)
admin.site.register(Message, MessageAdmin)

admin.site.register(ApiKey)
admin.site.register(ApiAccess)

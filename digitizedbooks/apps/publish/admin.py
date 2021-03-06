# file digitizedbooks/publication/admin.py
#
#   Copyright 2010 Emory University General Library
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

from django.contrib import admin
from digitizedbooks.apps.publish.models import  Job, KDip, ValidationError
from django.contrib.sites.models import Site
from django import forms

def remove_from_job(modeladmin, request, queryset):
    queryset.update(job=None)
remove_from_job.short_description = "Remove selected k dips from any associated job"

class ValidationErrorInline(admin.TabularInline):
    model = ValidationError
    list_display = ['error', 'error_type']
    readonly_fields = ['error', 'error_type']

    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

class JobAdminForm(forms.ModelForm):
    def clean(self):
        if self.cleaned_data['status'] == 'ready for zephir':
            statuses = self.instance.kdip_set.values_list('status', flat=True)
            if not all(status == 'new' for status in statuses):
                raise forms.ValidationError("All KDips must be valid before submitting to Zephir.")

class KDipAdmin(admin.ModelAdmin):
    list_display = ['kdip_id', 'status', 'note', 'oclc', 'errors', 'accepted_by_ia', 'accepted_by_ht', 'al_ht', 'job',]
    list_link = ['kdip_id']
    list_filter = ['status', 'job', 'accepted_by_ht', 'accepted_by_ia']
    list_editable = ['job', 'note', 'status', 'accepted_by_ia']
    readonly_fields = ['kdip_id', 'reason', 'path', 'oclc', 'mms_id', 'pid', 'create_date', 'errors', 'accepted_by_ht', 'ht_url', 'al_ht']
    search_fields = ['path', 'kdip_id', 'note', 'pid']
    inlines = [ValidationErrorInline]
#    actions = [remove_from_job]

    def has_add_permission(self, request):
        return False

class KDipInline(admin.TabularInline):
    model = KDip
    readonly_fields = ['kdip_id', 'pid', 'status', 'accepted_by_ht', 'accepted_by_ia', 'path', 'oclc', 'mms_id']
    exclude = ['note', 'reason', 'create_date']
    #can_delete = False
    extra = 0

    def has_add_permission(self, request):
        return False


class JobAdmin(admin.ModelAdmin):
    form = JobAdminForm
    inlines = [KDipInline]
    list_display = ['name', 'status', 'volume_count', 'uploaded']
    list_link = ['name']
    readonly_fields = ['volume_count', 'uploaded']


admin.site.register(KDip, KDipAdmin)
admin.site.register(Job, JobAdmin)

admin.site.unregister(Site)

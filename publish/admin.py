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
from publish.models import  Job, KDip, ValidationError
from django.contrib.sites.models import Site
#from taggit.models import Tag

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


class KDipAdmin(admin.ModelAdmin):
    list_display = ['kdip_id', 'status', 'note', 'errors', 'accepted_by_ht', 'job',]
    list_link = ['kdip_id']
    list_filter = ['status', 'job', 'accepted_by_ht', 'accepted_by_ia']
    list_editable = ['job', 'note', 'status']
    readonly_fields = ['kdip_id', 'reason', 'path', 'pid', 'create_date', 'errors', 'accepted_by_ht', 'ht_url']
    search_fields = ['path', 'kdip_id', 'note', 'pid']
    inlines = [ValidationErrorInline]
#    actions = [remove_from_job]

    def has_add_permission(self, request):
        return False

class KDipInline(admin.TabularInline):
    model = KDip
    readonly_fields = ['kdip_id', 'pid', 'status', 'path']
    exclude = ['note', 'reason', 'create_date']
    #can_delete = False
    extra = 0

    def has_add_permission(self, request):
        return False


class JobAdmin(admin.ModelAdmin):
    inlines = [KDipInline]
    list_display = ['name', 'status', 'volume_count']
    list_link = ['name']
    #readonly_fields = ['status']


admin.site.register(KDip, KDipAdmin)
admin.site.register(Job, JobAdmin)

admin.site.unregister(Site)
#admin.site.unregister(Tag)

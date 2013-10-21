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
from digitizedbooks.publish.models import  Job, KDip
from django.contrib.sites.models import Site
from taggit.models import Tag


class KDipAdmin(admin.ModelAdmin):
    list_display = ['kdip_id', 'create_date', 'status', 'note', 'job']
    list_link = ['kdip_id']
    list_editable = ['status', 'job']
    readonly_fields = ['create_date', 'kdip_id']

    def has_add_permission(self, request):
        return False

class KDipInline(admin.TabularInline):
    model = KDip
    readonly_fields = ['create_date', 'kdip_id']
    can_delete = False
    extra = 0

    def has_add_permission(self, request):
        return False


class JobAdmin(admin.ModelAdmin):
    inlines = [KDipInline]
    list_display = ['name', 'status']
    list_link = ['name']
    list_editable = ['status']


admin.site.register(KDip, KDipAdmin)
admin.site.register(Job, JobAdmin)

admin.site.unregister(Site)
admin.site.unregister(Tag)


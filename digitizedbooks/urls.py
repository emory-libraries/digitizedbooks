from django.conf import settings
from django.conf.urls.defaults import patterns, include, url
from django.contrib import admin
from django.views.generic.simple import direct_to_template
from django.contrib.sitemaps import FlatPageSitemap

admin.autodiscover()



urlpatterns = patterns('',
    url(r'^$', 'digitizedbooks.publish.views.site_index',  name='site-index'),
)

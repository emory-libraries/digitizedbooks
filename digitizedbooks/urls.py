from django.conf import settings
from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.views.generic.base import RedirectView

admin.autodiscover()


urlpatterns = patterns('',
    url(r'^$', RedirectView.as_view(url='admin/', permanent=True), name='admin'),
    url(r'^admin/', include(admin.site.urls)),
)

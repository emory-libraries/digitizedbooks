from django.shortcuts import render
from django.http import HttpResponse
from django.views.generic import TemplateView
from django.contrib import auth

class Forbidden(TemplateView):
    template_name = '403.html'

    def get(self, request, *args, **kwargs):

        response = HttpResponse()

        response.status_code = 403
        response.reason_phrase = 'Unauthorized'
        return response

# -*- coding: utf-8 -*-
from django.conf import settings
from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.views.generic import TemplateView

from accounts.forms import UserProfileEditForm

# from django.contrib import admin
# from admin import admin_site
admin.autodiscover()

urlpatterns = patterns('sylva.views',
    # index
    url(r'^$', 'index', name="index"),
    # dashboard
    url(r'^dashboard/$', 'dashboard', name="dashboard"),
    # introductory guide
    url(r'^get-started/$', TemplateView.as_view(template_name="get_started.html"),
        name="get_started"),
    # user guide
    url(r'^guide/$', TemplateView.as_view(template_name="user_guide.html"),
        name="user_guide"),
)

urlpatterns += patterns('',
    # accounts
    url(r'^accounts/(?P<username>[\w-]+)/edit/', "userena.views.profile_edit",
        {'edit_profile_form': UserProfileEditForm}),
    url(r'^accounts/signin/', "sylva.views.signin_redirect", name="signin"),
    url(r'^accounts/signup/', "sylva.views.signup_redirect", name="signup"),
    url(r'^accounts/', include('userena.urls')),

    # python i18n
    url(r'^i18n/', include('django.conf.urls.i18n')),

    # js i18n
    url(r'^jsi18n/$', 'django.views.i18n.javascript_catalog'),

    # messaging
    url(r'^messages/', include('userena.contrib.umessages.urls')),

    # data
    url(r'^data/', include('data.urls')),

    # engines
    url(r'^engines/', include('engines.urls')),

    # graphs
    url(r'^graphs/', include('graphs.urls')),

    # schemas
    url(r'^schemas/', include('schemas.urls')),

    # search
    url(r'^search/', include('search.urls')),

    # tools
    url(r'^tools/', include('tools.urls')),

    # tinyMCE
    url(r'^tinymce/', include('tinymce.urls')),

    # admin_media
    url(r'^admin/', include(admin.site.urls)),

    # payments
    url(r'^payments/', include('payments.urls')),
    url(r'^zebra/', include('zebra.urls', namespace="zebra",
                            app_name='zebra')),
)

urlpatterns += patterns('django.contrib.flatpages.views',
    url(r'^about/$', 'flatpage', {'url': '/about/'}, name='about'),
    url(r'^terms/$', 'flatpage', {'url': '/terms/'}, name='terms'),
    url(r'^privacy/$', 'flatpage', {'url': '/privacy/'}, name='privacy'),
)

if settings.ENABLE_QUERIES:
    urlpatterns += patterns('',
        # queries
        url(r'^queries/', include('queries.urls')),
    )

if settings.ENABLE_REPORTS:
    urlpatterns += patterns('',
        # reports
        url(r'^reports/', include('reports.urls')),
    )

if settings.ENABLE_ANALYTICS:
    urlpatterns += patterns('',
        # analytics
        url(r'^analytics/', include('analytics.urls')),
    )

if settings.DEBUG:
    urlpatterns += patterns('',
        # login as any user
        url(r"^su/", include("django_su.urls")),

        # static server
        url(r'^static/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': settings.STATIC_ROOT, 'show_indexes': True}),

        # static media server
        url(r'^media/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': settings.MEDIA_ROOT}),
    )
    try:
        import debug_toolbar
        urlpatterns += patterns('',
            url(r'^__debug__/', include(debug_toolbar.urls)),
        )
    except ImportError:
        pass

if settings.TEST and not settings.DEBUG:
    urlpatterns += patterns('',
        # static server
        url(r'^static/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': settings.STATIC_ROOT, 'show_indexes': False}),

        # static media server
        url(r'^media/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': settings.MEDIA_ROOT}),
    )

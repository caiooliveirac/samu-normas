from django.conf import settings


def build_metadata(_request):
    return {
        'FB_APP_ID': getattr(settings, 'FB_APP_ID', ''),
        'escala_sso': bool(getattr(settings, 'ESCALA_URL', '') and getattr(settings, 'ESCALA_FEDERACAO_SECRET', '')),
    }

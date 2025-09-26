import json
from pathlib import Path
from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()

# Vite 7 costuma salvar o manifest em "outDir/.vite/manifest.json"
MANIFEST_CANDIDATES = [
    Path(settings.BASE_DIR) / 'static' / 'react' / '.vite' / 'manifest.json',
    Path(settings.BASE_DIR) / 'static' / 'react' / 'manifest.json',
]

def _load_manifest():
    for p in MANIFEST_CANDIDATES:
        if p.exists():
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f)
    raise FileNotFoundError('Vite manifest.json não encontrado')

@register.simple_tag
def vite_asset(entry: str):
    """
    Resolve o caminho do asset a partir do manifest gerado pelo Vite.
    Uso: {% vite_asset 'src/main.jsx' %}
    """
    try:
        manifest = _load_manifest()
        info = manifest.get(entry)
        if not info:
            # Tenta achar por chave que termina com o entry (caso caminhos relativos)
            for k, v in manifest.items():
                if k.endswith(entry):
                    info = v
                    break
        if not info:
            # fallback: retorna algum asset comum se existir
            return static('react/assets/index.js')
        file_path = info.get('file')
        if not file_path:
            return static('react/assets/index.js')
        # base já é /static/react/ no build do Vite
        return f"{settings.STATIC_URL.rstrip('/')}/react/{file_path}"
    except Exception:
        # Fallback caso manifest não exista (primeiro acesso sem build)
        return static('react/assets/index.js')

@register.simple_tag
def vite_css(entry: str):
    """
    Retorna o caminho do CSS gerado para a entrada, se existir.
    Uso: {% vite_css 'src/main.jsx' %}
    """
    try:
        manifest = _load_manifest()
        info = manifest.get(entry)
        if not info:
            for k, v in manifest.items():
                if k.endswith(entry):
                    info = v
                    break
        if not info:
            return ''
        css_files = info.get('css') or []
        if not css_files:
            return ''
        # Pega o primeiro CSS listado
        file_path = css_files[0]
        return f"{settings.STATIC_URL.rstrip('/')}/react/{file_path}"
    except Exception:
        return ''

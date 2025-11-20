from flask import session, request
import os

def get_locale():
    # If user has set a language in session
    if 'lang' in session:
        return session['lang']
    # Otherwise detect from browser
    return request.accept_languages.best_match(['it', 'en', 'de', 'es', 'fr'])

def get_translations(lang=None):
    if not lang:
        lang = get_locale()
    try:
        return getattr(__import__(f'translations.{lang}', fromlist=['translations']), 'translations')
    except ImportError:
        # Fallback to English if requested language is not available
        return getattr(__import__('translations.en', fromlist=['translations']), 'translations')

def get_available_languages():
    return {
        'it': 'Italiano',
        'en': 'English',
        'de': 'Deutsch',
        'es': 'Español',
        'fr': 'Français'
    }

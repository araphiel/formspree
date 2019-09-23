web: gunicorn 'formspree:debuggable_app()'
worker: celery worker --app=formspree.app_globals
release: flask db upgrade

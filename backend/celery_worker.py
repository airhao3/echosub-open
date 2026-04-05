from app.core.tasks import celery_app

'''
This file is used to start the Celery worker.
Usage:
    celery -A celery_worker.celery_app worker --loglevel=info

For development with auto-reload:
    watchmedo auto-restart -d app -p "*.py" -- celery -A celery_worker.celery_app worker --loglevel=info
'''

if __name__ == '__main__':
    celery_app.start()

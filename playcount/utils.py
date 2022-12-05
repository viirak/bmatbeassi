"""
load and process
"""
import os
import tempfile
import shutil
from django.conf import settings
from playcount import settings as default_settings


def save_uploaded_chunks(f):
    handle, fn = tempfile.mkstemp(suffix='.csv')
    with os.fdopen(handle, "wb") as fd:
        for chunk in f.chunks():
            fd.write(chunk)
    return fn


def move_file_to_media_dir(fpath):
    if not settings.configured:
        settings.configure(default_settings, DEBUG=True)
    file_name = os.path.basename(fpath)
    if not os.path.exists(settings.MEDIA_ROOT):
        os.makedirs(settings.MEDIA_ROOT)
    shutil.move(fpath, settings.MEDIA_ROOT)
    # return settings.MEDIA_URL + file_name
    return file_name

def get_media_file(fname):
    path = os.path.join(settings.MEDIA_ROOT, fname)
    return open(path, 'r')

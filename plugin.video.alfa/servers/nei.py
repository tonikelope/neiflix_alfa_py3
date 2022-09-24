# -*- coding: utf-8 -*-

# Versión modificada del conector de MEGA para Noestasinvitado.com

from core import scrapertools
from platformcode import platformtools, logger

files = None


def test_video_exists(page_url):
    from megaserver import Client
    c = Client(url=page_url, is_playing_fnc=platformtools.is_playing)
    global files
    files = c.get_files()
    if isinstance(files, (int, long)):
        return False, "Error codigo %s" % str(files)

    return True, ""


def get_video_url(page_url, premium=False, user="", password="", video_password=""):
    page_url = page_url.replace('/embed#', '/#')
    logger.info("(page_url='%s')" % page_url)
    video_urls = []

    for f in files:
        media_url = f["url"]
        video_urls.append([scrapertools.get_filename_from_url(media_url)[-4:] + " [mega]", media_url])

    return video_urls

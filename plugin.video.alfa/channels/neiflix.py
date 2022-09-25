# -*- coding: utf-8 -*-
# https://github.com/tonikelope/neiflix_alfa

import base64
import hashlib
import json
import math
import os
import pickle
import random
import re
import socket
import urllib.request, urllib.parse, urllib.error

import urllib.request, urllib.error, urllib.parse
import urllib.parse
import xbmc
import xbmcaddon
import xbmcgui
from core import httptools
from core import scrapertools
from core.item import Item
from platformcode import config, logger
from platformcode import platformtools
from collections import OrderedDict

CHECK_MEGA_STUFF_INTEGRITY = True

NEIFLIX_VERSION = "1.34"

NEIFLIX_LOGIN = config.get_setting("neiflix_user", "neiflix")

NEIFLIX_PASSWORD = config.get_setting("neiflix_password", "neiflix")

USE_MEGA_PREMIUM = config.get_setting("neiflix_mega_premium", "neiflix")

MEGA_EMAIL = config.get_setting("neiflix_mega_email", "neiflix")

MEGA_PASSWORD = config.get_setting("neiflix_mega_password", "neiflix")

USE_MC_REVERSE = config.get_setting("neiflix_use_mc_reverse", "neiflix")

KODI_TEMP_PATH = xbmc.translatePath('special://temp/')

KODI_USERDATA_PATH = xbmc.translatePath('special://userdata/')

GITHUB_BASE_URL = "https://raw.githubusercontent.com/tonikelope/neiflix_alfa_py3/master/"

ALFA_URL = "https://raw.githubusercontent.com/tonikelope/neiflix_alfa_py3/master/plugin.video.alfa/"

ALFA_PATH = xbmc.translatePath('special://home/addons/plugin.video.alfa/')

try:
    HISTORY = [line.rstrip('\n') for line in open(KODI_TEMP_PATH + 'kodi_nei_history')]
except:
    HISTORY = []

if USE_MC_REVERSE:

    try:

        MC_REVERSE_PORT = int(config.get_setting("neiflix_mc_reverse_port", "neiflix"))

        if MC_REVERSE_PORT >= 1024 and MC_REVERSE_PORT <= 65535:
            MC_REVERSE_PASS = hashlib.sha1(NEIFLIX_LOGIN.encode('utf-8')).hexdigest()

            MC_REVERSE_DATA = str(MC_REVERSE_PORT) + ":" + base64.b64encode(
                "neiflix:" + MC_REVERSE_PASS)

    except ValueError:
        pass

else:
    MC_REVERSE_DATA = ''
    MC_REVERSE_PORT = None
    MC_REVERSE_PASS = None

UPLOADERS_BLACKLIST = [
    x.strip() for x in config.get_setting(
        "neiflix_blacklist_uploaders",
        "neiflix").split(',')] if config.get_setting(
    "neiflix_blacklist_uploaders",
    "neiflix") else []

TITLES_BLACKLIST = [
    x.strip() for x in config.get_setting(
        "neiflix_blacklist_titles",
        "neiflix").split(',')] if config.get_setting(
    "neiflix_blacklist_titles",
    "neiflix") else []


def login():
    logger.info("channels.neiflix login")

    httptools.downloadpage("https://noestasinvitado.com/login/")

    if NEIFLIX_LOGIN and NEIFLIX_PASSWORD:

        post = "user=" + NEIFLIX_LOGIN + "&passwrd=" + \
               NEIFLIX_PASSWORD + "&cookielength=-1"

        data = httptools.downloadpage(
            "https://noestasinvitado.com/login2/", post=post).data

        return data.find(NEIFLIX_LOGIN) != -1

    else:

        return false


def mega_login(verbose):
    mega_sid = ''

    if USE_MEGA_PREMIUM and MEGA_EMAIL and MEGA_PASSWORD:

        filename_hash = KODI_TEMP_PATH + 'kodi_nei_mega_' + hashlib.sha1((MEGA_EMAIL + MEGA_PASSWORD).encode('utf-8')).hexdigest()

        login_ok = False

        if os.path.isfile(filename_hash):

            try:

                with open(filename_hash, "rb") as file:

                    mega = pickle.load(file)

                    mega.get_user()

                    login_ok = True

            except RequestError:
                pass

        if not login_ok:

            mega = Mega()

            try:

                with open(filename_hash, "wb") as file:

                    mega.login(MEGA_EMAIL, MEGA_PASSWORD)

                    pickle.dump(mega, file)

                    login_ok = True

            except RequestError:
                pass

        if login_ok:

            storage = mega.get_storage_space()

            premium = storage['total'] >= 214748364800

            mega_sid = mega.sid

            logger.info("channels.neiflix LOGIN EN MEGA OK")

            if verbose:
                xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')', "LOGIN EN MEGA OK",
                                              os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media',
                                                           'channels', 'thumb', 'neiflix2_t.png'), 5000)

            if not premium:
                logger.info("channels.neiflix AVISO: CUENTA DE MEGA NO PREMIUM")
                xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')', "AVISO: CUENTA DE MEGA NO PREMIUM",
                                              os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media',
                                                           'channels', 'thumb', 'neiflix2_t.png'), 5000)

        else:

            logger.info("channels.neiflix ERROR AL HACER LOGIN EN MEGA")

            if verbose:
                xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')', "ERROR AL HACER LOGIN EN MEGA",
                                              os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media',
                                                           'channels', 'thumb', 'neiflix2_t.png'), 5000)

    return mega_sid


def mainlist(item):
    logger.info("channels.neiflix mainlist")

    itemlist = []

    if not NEIFLIX_LOGIN:
        xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')', "ERROR AL HACER LOGIN EN NEI",
                                      os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media',
                                                   'channels', 'thumb', 'neiflix2_t.png'), 5000)
        itemlist.append(
            Item(channel=item.channel,
                 title="[COLOR darkorange][B]Habilita tu cuenta de NEI en preferencias.[/B][/COLOR]",
                 action="settings_nei"))
    else:
        if login():
            xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')', "¡Bienvenido " + NEIFLIX_LOGIN + "!",
                                          os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media',
                                                       'channels', 'thumb', 'neiflix2_t.png'), 5000)
            mega_login(True)
            load_mega_proxy('', MC_REVERSE_PORT, MC_REVERSE_PASS)
            itemlist.append(Item(channel=item.channel, title="Películas", action="foro",
                                 url="https://noestasinvitado.com/peliculas/", folder=True, fa=True, fa_genre=""))
            itemlist.append(Item(channel=item.channel, title="Series", action="foro",
                                 url="https://noestasinvitado.com/series/", folder=True, fa=True, fa_genre="TV_SE"))
            itemlist.append(Item(channel=item.channel, title="Documetales", action="foro",
                                 url="https://noestasinvitado.com/documentales/", folder=True))
            itemlist.append(Item(channel=item.channel, title="Vídeos deportivos", action="foro",
                                 url="https://noestasinvitado.com/deportes/", folder=True))
            itemlist.append(Item(channel=item.channel, title="Anime", action="foro",
                                 url="https://noestasinvitado.com/anime/", folder=True))
            if not os.path.exists(KODI_USERDATA_PATH + 'neiflix_xxx'):
                itemlist.append(Item(channel=item.channel, title="\"Guarreridas\"", action="foro",
                                     url="https://noestasinvitado.com/18-15/", folder=True, xxx=True))
            itemlist.append(Item(channel=item.channel, title="Listados alfabéticos", action="indices",
                                 url="https://noestasinvitado.com/indices/", folder=True))
            itemlist.append(
                Item(
                    channel=item.channel,
                    title="[COLOR darkorange][B]Buscar[/B][/COLOR]",
                    action="search"))

            itemlist.append(
                Item(
                    channel=item.channel,
                    title="[B]Preferencias[/B]",
                    action="settings_nei"))

            if not os.path.exists(KODI_USERDATA_PATH + 'neiflix_xxx'):
                itemlist.append(
                    Item(
                        channel=item.channel,
                        title="Desactivar contenido adulto",
                        action="xxx_off"))
            else:
                itemlist.append(
                    Item(
                        channel=item.channel,
                        title="Reactivar contenido adulto",
                        action="xxx_on"))

            itemlist.append(
                Item(
                    channel=item.channel,
                    title="[B]Borrar caché[/B]",
                    action="clean_cache"))

            itemlist.append(
                Item(
                    channel=item.channel,
                    title="[COLOR red][B]Borrar historial[/B][/COLOR]",
                    action="clean_history"))
        else:
            xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')', "ERROR AL HACER LOGIN EN NEI",
                                          os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media',
                                                       'channels', 'thumb', 'neiflix2_t.png'), 5000)
            itemlist.append(
                Item(channel=item.channel,
                     title="[COLOR red][B]ERROR: Usuario y/o password de NEI incorrectos (revisa las preferencias)[/B][/COLOR]",
                     action=""))

            itemlist.append(
                Item(channel=item.channel,
                     title="[COLOR darkorange][B]Habilita tu cuenta de NEI en preferencias.[/B][/COLOR]",
                     action="settings_nei"))

    return itemlist


def settings_nei(item):
    platformtools.show_channel_settings()

    global NEIFLIX_LOGIN, NEIFLIX_PASSWORD, USE_MEGA_PREMIUM, MEGA_EMAIL, MEGA_PASSWORD, USE_MC_REVERSE

    NEIFLIX_LOGIN = config.get_setting("neiflix_user", "neiflix")

    NEIFLIX_PASSWORD = config.get_setting("neiflix_password", "neiflix")

    USE_MEGA_PREMIUM = config.get_setting("neiflix_mega_premium", "neiflix")

    MEGA_EMAIL = config.get_setting("neiflix_mega_email", "neiflix")

    MEGA_PASSWORD = config.get_setting("neiflix_mega_password", "neiflix")

    USE_MC_REVERSE = config.get_setting("neiflix_use_mc_reverse", "neiflix")

    return mainlist(item)


def xxx_off(item):
    if not os.path.exists(KODI_USERDATA_PATH + 'neiflix_xxx'):

        pass_hash = xbmcgui.Dialog().input(
            'Introduce una contraseña por si quieres reactivar el contenido adulto más tarde',
            type=xbmcgui.INPUT_PASSWORD)

        if pass_hash:
            f = open(KODI_USERDATA_PATH + 'neiflix_xxx', "w+")
            f.write(pass_hash)
            f.close()
            xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')', "Porno desactivado",
                                          os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media',
                                                       'channels', 'thumb', 'neiflix2_t.png'), 5000)
            return mainlist(item)
    else:
        return mainlist(item)


def xxx_on(item):
    if os.path.exists(KODI_USERDATA_PATH + 'neiflix_xxx'):
        password = xbmcgui.Dialog().input('Introduce la contraseña', type=xbmcgui.INPUT_ALPHANUM,
                                          option=xbmcgui.ALPHANUM_HIDE_INPUT)

        if password:
            with open(KODI_USERDATA_PATH + 'neiflix_xxx', 'r') as f:
                file_pass = f.read()

            if hashlib.md5(password.encode('utf-8')).hexdigest() == file_pass:
                os.remove(KODI_USERDATA_PATH + 'neiflix_xxx')
                xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')', "Porno reactivado",
                                              os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media',
                                                           'channels', 'thumb', 'neiflix2_t.png'), 5000)
                return mainlist(item)
            else:
                xbmcgui.Dialog().ok('NEIFLIX: reactivar contenido adulto', 'Contraseña incorrecta')
    else:
        return mainlist(item)


def clean_cache(item):
    conta_files = 0

    for file in os.listdir(KODI_TEMP_PATH):
        if file.startswith("kodi_nei_") and file != 'kodi_nei_history':
            os.remove(KODI_TEMP_PATH + file)
            conta_files = conta_files + 1

    xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')',
                                  "¡Caché borrada! (" + str(conta_files) + " archivos eliminados)",
                                  os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels',
                                               'thumb', 'neiflix2_t.png'), 5000)
    platformtools.itemlist_refresh()


def clean_history(item):
    if xbmcgui.Dialog().yesno('NEIFLIX (' + NEIFLIX_VERSION + ')',
                              '¿Estás seguro de que quieres borrar tu historial de vídeos visionados?'):

        try:
            os.remove(KODI_TEMP_PATH + 'kodi_nei_history')
            xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')', "¡Historial borrado!",
                                          os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media',
                                                       'channels', 'thumb', 'neiflix2_t.png'), 5000)
        except:
            pass


def foro(item):
    logger.info("channels.neiflix foro")

    if item.xxx and os.path.exists(KODI_USERDATA_PATH + 'neiflix_xxx'):
        return mainlist(item)

    itemlist = []

    data = httptools.downloadpage(item.url).data

    video_links = False

    final_item = False

    if '<h3 class="catbg">Subforos</h3>' in data:
        # HAY SUBFOROS
        patron = '<a class="subje(.*?)t" href="([^"]+)" name="[^"]+">([^<]+)</a(>)'
        action = "foro"
    elif '"subject windowbg4"' in data:
        patron = '<td class="subject windowbg4">.*?<div *?>.*?<span id="([^"]+)">.*?< *?a +href *?= *?"([^"]+)" *?>([^<]+)</a> ' \
                 '*?</span>.*?"Ver +perfil +de +([^"]+)"'
        final_item = True
        action = "foro"
    else:
        video_links = True
        itemlist = find_video_mega_links(item, data) + find_video_gvideo_links(item, data)

    if not video_links:

        matches = re.compile(patron, re.DOTALL).findall(data)

        for scrapedmsg, scrapedurl, scrapedtitle, uploader in matches:

            url = urllib.parse.urljoin(item.url, scrapedurl)

            if uploader not in UPLOADERS_BLACKLIST and not any(word in scrapedtitle for word in TITLES_BLACKLIST):

                scrapedtitle = scrapertools.htmlclean(scrapedtitle)

                if uploader != '>':
                    title = scrapedtitle + " (" + uploader + ")"
                else:
                    title = scrapedtitle

                thumbnail = ""

                if final_item:

                    parsed_title = parse_title(scrapedtitle)

                    content_title = parsed_title['title']

                    year = parsed_title['year']

                    if item.fa:

                        if item.fa_genre == 'TV_SE':
                            rating = get_filmaffinity_data(content_title)

                            if rating[0] is None:
                                rating = get_filmaffinity_data_advanced(content_title, year, item.fa_genre)
                        else:
                            rating = get_filmaffinity_data_advanced(content_title, year, item.fa_genre)

                        if item.parent_title.startswith('Ultra HD '):
                            quality = 'UHD'
                        elif item.parent_title.startswith('HD '):
                            quality = 'HD'
                        else:
                            quality = 'SD'

                        if rating[0]:
                            if float(rating[0]) >= 7.0:
                                rating_text = "[COLOR green][FA " + \
                                              rating[0] + "][/COLOR]"
                            elif float(rating[0]) < 4.0:
                                rating_text = "[COLOR red][FA " + \
                                              rating[0] + "][/COLOR]"
                            else:
                                rating_text = "[FA " + rating[0] + "]"
                        else:
                            rating_text = "[FA ---]"

                        title = "[COLOR darkorange][B]" + content_title + "[/B][/COLOR] " + (
                            "(" + year + ")" if year else "") + " [" + quality + "] [B]" + \
                                rating_text + "[/B] (" + uploader + ")"

                        if rating[1]:
                            thumbnail = rating[1].replace('msmall', 'large')
                        else:
                            thumbnail = ""

                    item.infoLabels = {'year': year}

                else:
                    item.parent_title = title.strip()
                    content_title = ""
                    matches = re.compile("([^/]+)/$", re.DOTALL).search(url)

                    if matches.group(1) not in ('hd-espanol-59', 'hd-v-o-v-o-s-61', 'hd-animacion-62',
                                                'sd-espanol-53', 'sd-v-o-v-o-s-54', 'sd-animacion',
                                                'seriesovas-anime-espanol', 'seriesovas-anime-v-o-v-o-s'):
                        url = url + "?sort=first_post;desc"

                itemlist.append(item.clone(
                    action=action,
                    title=title,
                    url=url,
                    thumbnail=thumbnail +
                              "|User-Agent=Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/65.0.3163.100 Safari/537.36",
                    folder=True, contentTitle=content_title))

        patron = '\[<strong>[0-9]+</strong>\][^<>]*<a class="navPages" href="([^"]+)">'

        matches = re.compile(patron, re.DOTALL).search(data)

        if matches:
            url = matches.group(1)
            title = "[B]>> Página Siguiente[/B]"
            thumbnail = ""
            plot = ""
            itemlist.append(
                item.clone(
                    action="foro",
                    title=title,
                    url=url,
                    thumbnail=thumbnail,
                    folder=True))

    return itemlist


def search(item, texto):
    itemlist = []

    if texto != "":
        texto = texto.replace(" ", "+")

    post = "advanced=1&search=" + texto + "&searchtype=1&userspec=*&sort=relevance%7Cdesc&subject_only=1&" \
                                          "minage=0&maxage=9999&brd%5B6%5D=6&brd%5B227%5D=227&brd%5B229%5D" \
                                          "=229&brd%5B230%5D=230&brd%5B41%5D=41&brd%5B47%5D=47&brd%5B48%5D" \
                                          "=48&brd%5B42%5D=42&brd%5B44%5D=44&brd%5B46%5D=46&brd%5B218%5D=2" \
                                          "18&brd%5B225%5D=225&brd%5B7%5D=7&brd%5B52%5D=52&brd%5B59%5D=59&b" \
                                          "rd%5B61%5D=61&brd%5B62%5D=62&brd%5B51%5D=51&brd%5B53%5D=53&brd%5" \
                                          "B54%5D=54&brd%5B55%5D=55&brd%5B63%5D=63&brd%5B64%5D=64&brd%5B66%" \
                                          "5D=66&brd%5B67%5D=67&brd%5B65%5D=65&brd%5B68%5D=68&brd%5B69%5D=69" \
                                          "&brd%5B14%5D=14&brd%5B87%5D=87&brd%5B86%5D=86&brd%5B93%5D=93&brd" \
                                          "%5B83%5D=83&brd%5B89%5D=89&brd%5B85%5D=85&brd%5B82%5D=82&brd%5B9" \
                                          "1%5D=91&brd%5B90%5D=90&brd%5B92%5D=92&brd%5B88%5D=88&brd%5B84%5D" \
                                          "=84&brd%5B212%5D=212&brd%5B94%5D=94&brd%5B23%5D=23&submit=Buscar"

    data = httptools.downloadpage(
        "https://noestasinvitado.com/search2/", post=post).data

    patron = '<h5>[^<>]*<a[^<>]+>.*?</a>[^<>]*?<a +href="([^"]+)">(.*?)</a>[^<>]*</h5>[^<>]*<span[^<>]*>.*?' \
             '<a[^<>]*"Ver +perfil +de +([^"]+)"'

    matches = re.compile(patron, re.DOTALL).findall(data)

    for scrapedurl, scrapedtitle, uploader in matches:
        url = urllib.parse.urljoin(item.url, scrapedurl)

        scrapedtitle = scrapertools.htmlclean(scrapedtitle)

        title = scrapedtitle + " [" + uploader + "]"

        thumbnail = ""

        parsed_title = parse_title(scrapedtitle)

        year = parsed_title['year']

        content_title = parsed_title['title']

        item.infoLabels = {'year': year}

        itemlist.append(item.clone(action="foro", title=title, url=url, thumbnail=thumbnail, contentTitle=content_title,
                                   folder=True))

    patron = '\[<strong>[0-9]+</strong>\][^<>]*<a class="navPages" href="([^"]+)">'

    matches = re.compile(patron, re.DOTALL).search(data)

    if matches:
        url = matches.group(1)
        title = "[B]>> Página Siguiente[/B]"
        thumbnail = ""
        plot = ""
        itemlist.append(
            item.clone(
                action="search_pag",
                title=title,
                url=url,
                thumbnail=thumbnail,
                folder=True))

    return itemlist


def search_pag(item):
    itemlist = []

    data = httptools.downloadpage(item.url).data

    patron = '<h5>[^<>]*<a[^<>]+>.*?</a>[^<>]*?<a +href="([^"]+)">(.*?)</a>[^<>]*</h5>[^<>]*<sp' \
             'an[^<>]*>.*?<a[^<>]*"Ver +perfil +de +([^"]+)"'

    matches = re.compile(patron, re.DOTALL).findall(data)

    for scrapedurl, scrapedtitle, uploader in matches:
        url = urllib.parse.urljoin(item.url, scrapedurl)

        scrapedtitle = scrapertools.htmlclean(scrapedtitle)

        title = scrapedtitle + " [" + uploader + "]"

        thumbnail = ""

        parsed_title = parse_title(scrapedtitle)

        year = parsed_title['year']

        content_title = parsed_title['title']

        item.infoLabels = {'year': year}

        itemlist.append(item.clone(action="foro", title=title, url=url, thumbnail=thumbnail, contentTitle=content_title,
                                   folder=True))

    patron = '\[<strong>[0-9]+</strong>\][^<>]*<a class="navPages" href="([^"]+)">'

    matches = re.compile(patron, re.DOTALL).search(data)

    if matches:
        url = matches.group(1)
        title = "[B]>> Página Siguiente[/B]"
        thumbnail = ""
        plot = ""
        itemlist.append(
            item.clone(
                action="search_pag",
                title=title,
                url=url,
                thumbnail=thumbnail,
                folder=True))

    return itemlist


def indices(item):
    itemlist = []

    categories = ['Películas HD Español', 'Películas HD VO', 'Películas SD Español', 'Películas SD VO',
                  'Series HD Español', 'Series HD VO', 'Series SD Español', 'Series SD VO', 'Películas Anime Español',
                  'Películas Anime VO', 'Series Anime Español', 'Series Anime VO', 'Películas clásicas', 'Deportes',
                  'Películas XXX HD', 'Películas XXX SD', 'Vídeos XXX HD', 'Vídeos XXX SD']

    for cat in categories:
        itemlist.append(
            Item(channel=item.channel, title=cat, action="gen_index", url="https://noestasinvitado.com/indices/",
                 folder=True))

    return itemlist


def gen_index(item):
    categories = {'Películas HD Español': 47, 'Películas HD VO': 48, 'Películas SD Español': 44, 'Películas SD VO': 42,
                  'Series HD Español': 59, 'Series HD VO': 61, 'Series SD Español': 53, 'Series SD VO': 54,
                  'Películas Anime Español': 66, 'Películas Anime VO': 67, 'Series Anime Español': 68,
                  'Series Anime VO': 69, 'Películas clásicas': 218, 'Deportes': 23, 'Películas XXX HD': 182,
                  'Películas XXX SD': 183, 'Vídeos XXX HD': 185, 'Vídeos XXX SD': 186}

    letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'Ñ', 'O', 'P', 'Q', 'R', 'S', 'T',
               'U', 'V', 'W', 'X', 'Y', 'Z', '0-9']

    itemlist = []

    start = 1

    for letter in letters:
        itemlist.append(Item(channel=item.channel, title="%s (Letra %s)" % (item.title, letter), action="indice_links",
                             url="https://noestasinvitado.com/indices/?id=%d;start=%d" % (
                                 categories[item.title], start), folder=True))
        start = start + 1

    return itemlist


def get_video_mega_links_group(item):
    mega_sid = mega_login(False)

    itemlist = []

    id = item.mc_group_id

    filename_hash = KODI_TEMP_PATH + 'kodi_nei_mc_' + hashlib.sha1((item.url + id).encode('utf-8')).hexdigest()

    if os.path.isfile(filename_hash) and os.stat(filename_hash).st_size > 0:

        with open(filename_hash, "r") as file:

            i = 1

            for line in file:

                line = line.rstrip()

                if i > 1:

                    url = line

                    url_split = url.split('#')

                    if len(url_split) >= 3:

                        name = url_split[1]

                        size = url_split[2]

                        title = "[MEGA] " + name + ' [' + str(format_bytes(float(size))) + ']'

                        if hashlib.sha1(title.encode("utf-8")).hexdigest() in HISTORY:
                            title = "[COLOR green][B](VISTO)[/B][/COLOR] " + title

                        itemlist.append(
                            Item(channel=item.channel, action="play", server='nei', title=title,
                                 url=url + '#' + MC_REVERSE_DATA + '#' + mega_sid, parentContent=item,
                                 folder=False))

                else:

                    links_hash = line

                    data = httptools.downloadpage(
                        "https://noestasinvitado.com/gen_mc.php?id=" + id + "&raw=1").data

                    patron = '(.*? *?\[[0-9.]+ *?.*?\]) *?(https://megacrypter\.noestasinvitado\.com/.+)'

                    matches = re.compile(patron).findall(data)

                    if matches:

                        hasheable = ""

                        for title, url in matches:
                            hasheable += title

                        links_hash2 = hashlib.sha1(hasheable.encode('utf-8')).hexdigest()

                        if links_hash != links_hash2:
                            os.remove(filename_hash)

                            return get_video_mega_links_group(item)
                    else:

                        return itemlist

                i += 1

        if not itemlist:
            os.remove(filename_hash)
            itemlist.append(Item(channel=item.channel,
                                 title="[COLOR red][B]Ha habido algún error, prueba de nuevo.[/B][/COLOR]",
                                 action="", url="", folder=False))

    else:

        data = httptools.downloadpage(
            "https://noestasinvitado.com/gen_mc.php?id=" + id + "&raw=1").data

        patron = '(.*? *?\[[0-9.]+ *?.*?\]) *?(https://megacrypter\.noestasinvitado\.com/.+)'

        matches = re.compile(patron).findall(data)

        compress_pattern = re.compile('\.(zip|rar|rev)$', re.IGNORECASE)

        if matches:

            hasheable = ""

            for title, url in matches:
                hasheable += title

            links_hash = hashlib.sha1(hasheable.encode('utf-8')).hexdigest()

            with open(filename_hash, "w+", encoding="utf-8") as file:

                file.write((links_hash + "\n"))

                for title, url in matches:

                    url_split = url.split('/!')

                    mc_api_url = url_split[0] + '/api'

                    mc_api_r = {'m': 'info', 'link': url}

                    if USE_MC_REVERSE:
                        mc_api_r['reverse'] = MC_REVERSE_DATA

                    mc_info_res = mc_api_req(
                        mc_api_url, mc_api_r)

                    name = mc_info_res['name'].replace('#', '')

                    size = mc_info_res['size']

                    key = mc_info_res['key']

                    noexpire = mc_info_res['expire'].split('#')[1]

                    compress = compress_pattern.search(name)

                    if compress:

                        itemlist.append(Item(channel=item.channel,
                                             title="[COLOR red][B]ESTE VÍDEO ESTÁ COMPRIMIDO Y NO ES COMPATIBLE "
                                                   "(habla con el uploader para que lo suba sin comprimir).[/B][/COLOR]",
                                             action="", url="", folder=False))

                        break

                    else:

                        title = "[MEGA] " + name + ' [' + str(format_bytes(size)) + ']'

                        if hashlib.sha1(title.encode('utf-8')).hexdigest() in HISTORY:
                            title = "[COLOR green][B](VISTO)[/B][/COLOR] " + title

                        url = url + '#' + name + '#' + str(size) + '#' + key + '#' + noexpire

                        file.write((url + "\n"))

                        itemlist.append(
                            Item(channel=item.channel, action="play", server='nei', title=title,
                                 url=url + '#' + MC_REVERSE_DATA + '#' + mega_sid,
                                 parentContent=item, folder=False))

        else:
            patron_mega = 'https://mega(?:\.co)?\.nz/#[!0-9a-zA-Z_-]+'

            matches = re.compile(patron_mega).findall(data)

            if matches:

                for url in matches:

                    if len(url.split("!")) == 3:
                        file_id = url.split("!")[1]
                        file_key = url.split("!")[2]
                        file = mega_api_req({'a': 'g', 'g': 1, 'p': file_id})
                        key = crypto.base64_to_a32(file_key)
                        k = (key[0] ^ key[4], key[1] ^ key[5], key[2] ^ key[6], key[3] ^ key[7])
                        attributes = crypto.base64_url_decode(file['at'])
                        attributes = crypto.decrypt_attr(attributes, k)
                        title = "[MEGA] " + attributes['n'] + ' [' + str(format_bytes(file['s'])) + ']'
                    else:
                        title = url

                    compress = compress_pattern.search(attributes['n'])

                    if compress:

                        itemlist.append(Item(channel=item.channel,
                                             title="[COLOR red][B]ESTE VÍDEO ESTÁ COMPRIMIDO Y NO ES COMPATIBLE "
                                                   "(habla con el uploader para que lo suba sin comprimir).[/B][/COLOR]",
                                             action="", url="", folder=False))

                        break

                    else:

                        if hashlib.sha1(title.encode('utf-8')).hexdigest() in HISTORY:
                            title = "[COLOR green][B](VISTO)[/B][/COLOR] " + title
                            itemlist.append(
                                Item(channel=item.channel, action="play", server='nei', title=title, url=url,
                                     parentContent=item, folder=False))

    itemlist.append(
                Item(
                    channel=item.channel,
                    title="[B]REFRESCAR CONTENIDO[/B]",
                    action="clean_cache", folder=False))
    return itemlist


def find_video_gvideo_links(item, data):
    msg_id = re.compile('subject_([0-9]+)', re.IGNORECASE).search(data)

    if msg_id:

        thanks_match = re.compile(
            '/\?action=thankyou;msg=' +
            msg_id.group(1),
            re.IGNORECASE).search(data)

        if thanks_match:
            httptools.downloadpage(item.url + thanks_match.group(0))
            data=httptools.downloadpage(item.url).data

    itemlist = []

    patron = "(?:https|http)://(?:docs|drive).google.com/file/d/[^/]+/(?:preview|edit|view)"  # Hay más variantes de enlaces

    matches = re.compile(patron, re.DOTALL).findall(data)

    if matches:

        if len(matches) > 1:

            for url in list(OrderedDict.fromkeys(matches)):
                itemlist.append(
                    Item(channel=item.channel, action="play", server='gvideo', title='[GVIDEO] ' + item.title, url=url,
                         parentContent=item, folder=False))
        else:
            itemlist.append(Item(channel=item.channel, action="play", server='gvideo', title='[GVIDEO] ' + item.title,
                                 url=matches[0], parentContent=item, folder=False))

    return itemlist


def find_video_mega_links(item, data):
    msg_id = re.compile('subject_([0-9]+)', re.IGNORECASE).search(data)

    if msg_id:

        thanks_match = re.compile(
            '/\?action=thankyou;msg=' +
            msg_id.group(1),
            re.IGNORECASE).search(data)

        if thanks_match:
            httptools.downloadpage(item.url + thanks_match.group(0))
            data=httptools.downloadpage(item.url).data


    itemlist = []

    patron = 'id="mc_link_.*?".*?data-id="(.*?)"'

    matches = re.compile(patron, re.DOTALL).findall(data)

    if matches:

        if len(matches) > 1:

            i = 1

            for id in list(OrderedDict.fromkeys(matches)):
                itemlist.append(Item(channel=item.channel, action="get_video_mega_links_group",
                                     title='[' + str(i) + '/' + str(len(matches)) + '] ' + item.title, url=item.url,
                                     mc_group_id=id, folder=True))

                i = i + 1
        else:
            itemlist = get_video_mega_links_group(
                Item(channel=item.channel, action='', title='', url=item.url, mc_group_id=matches[0], folder=True))
    else:

        mega_sid = mega_login(False)

        filename_hash = KODI_TEMP_PATH + 'kodi_nei_mc_' + hashlib.sha1(item.url.encode('utf-8')).hexdigest()

        if os.path.isfile(filename_hash):

            with open(filename_hash, "r") as file:

                i = 1

                for line in file:

                    line = line.rstrip()

                    if i > 1:

                        url = line

                        url_split = url.split('#')

                        name = url_split[1]

                        size = url_split[2]

                        title = name + ' [' + str(format_bytes(float(size))) + ']'

                        itemlist.append(
                            Item(channel=item.channel, action="play", server='nei', title="[MEGA] " + title,
                                 url=url + '#' + MC_REVERSE_DATA + '#' + mega_sid,
                                 parentContent=item, folder=False))

                    else:

                        links_hash = line

                        patron = 'https://megacrypter\.noestasinvitado\.com/[!0-9a-zA-Z_/-]+'

                        matches = re.compile(patron).findall(data)

                        if matches:

                            links_hash2 = hashlib.sha1(
                                "".join(matches).encode('utf-8')).hexdigest()

                            if links_hash != links_hash2:
                                os.remove(filename_hash)

                                return find_video_mega_links(item, data)
                        else:

                            return itemlist

                    i += 1

        else:

            urls = []

            patron_mc = 'https://megacrypter\.noestasinvitado\.com/[!0-9a-zA-Z_/-]+'

            matches = re.compile(patron_mc).findall(data)

            compress_pattern = re.compile(
                '\.(zip|rar|rev)$', re.IGNORECASE)

            if matches:

                with open(filename_hash, "w+", encoding="utf-8") as file:

                    links_hash = hashlib.sha1("".join(matches).encode('utf-8')).hexdigest()

                    file.write((links_hash + "\n"))

                    for url in matches:

                        if url not in urls:

                            urls.append(url)

                            url_split = url.split('/!')

                            mc_api_url = url_split[0] + '/api'

                            mc_api_r = {'m': 'info', 'link': url}

                            if USE_MC_REVERSE:
                                mc_api_r['reverse'] = MC_REVERSE_DATA

                            mc_info_res = mc_api_req(
                                mc_api_url, mc_api_r)

                            name = mc_info_res['name'].replace('#', '')

                            size = mc_info_res['size']

                            key = mc_info_res['key']

                            if mc_info_res['expire']:
                                noexpire = mc_info_res['expire'].split('#')[1]
                            else:
                                noexpire = ''

                            compress = compress_pattern.search(name)

                            if compress:

                                itemlist.append(Item(channel=item.channel,
                                                     title="[COLOR red][B]ESTE VÍDEO ESTÁ COMPRIMIDO Y NO ES COMPATIBLE"
                                                           " (habla con el uploader para que lo suba sin comprimir)."
                                                           "[/B][/COLOR]",
                                                     action="", url="", folder=False))
                                break
                            else:
                                title = name + ' [' + str(format_bytes(size)) + ']'
                                url = url + '#' + name + '#' + str(size) + '#' + key + '#' + noexpire
                                file.write((url + "\n"))
                                itemlist.append(
                                    Item(channel=item.channel, action="play", server='nei', title="[MEGA] " + title,
                                         url=url + '#' + MC_REVERSE_DATA + '#' + mega_sid, parentContent=item,
                                         folder=False))

            else:
                patron_mega = 'https://mega(?:\.co)?\.nz/#[!0-9a-zA-Z_-]+|https://mega(?:\.co)?\.nz/file/[^#]+#[0-9a-zA-Z_-]+'

                matches = re.compile(patron_mega).findall(data)

                if matches:

                    for url in matches:

                        url = re.sub(r"(\.nz/file/)([^#]+)#", r".nz/#!\2!", url)

                        if url not in urls:

                            urls.append(url)

                            if len(url.split("!")) == 3:
                                file_id = url.split("!")[1]
                                file_key = url.split("!")[2]
                                file = mega_api_req({'a': 'g', 'g': 1, 'p': file_id})
                                logger.info("***************************NEI MEGA API RESPONSE -> "+json.dumps(file, indent = 4))
                                key = crypto.base64_to_a32(file_key)
                                k = (key[0] ^ key[4], key[1] ^ key[5], key[2] ^ key[6], key[3] ^ key[7])
                                attributes = crypto.base64_url_decode(file['at'])
                                attributes = crypto.decrypt_attr(attributes, k)
                                title = attributes['n'] + ' [' + str(format_bytes(file['s'])) + ']'
                            else:
                                title = url

                            compress = compress_pattern.search(attributes['n'])

                            if compress:
                                itemlist.append(Item(channel=item.channel,
                                                     title="[COLOR red][B]ESTE VÍDEO ESTÁ COMPRIMIDO Y NO ES COMPATIBLE"
                                                           " (habla con el uploader para que lo suba sin comprimir)."
                                                           "[/B][/COLOR]",
                                                     action="", url="", folder=False))
                                break
                            else:
                                itemlist.append(
                                    Item(channel=item.channel, action="play", server='nei', title="[MEGA] " + title,
                                         url=url, parentContent=item, folder=False))
        itemlist.append(
                Item(
                    channel=item.channel,
                    title="[B]REFRESCAR CONTENIDO[/B]",
                    action="clean_cache", folder=False))

    return itemlist


def indice_links(item):
    itemlist = []

    data = httptools.downloadpage(item.url).data

    patron = '<tr class="windowbg2">[^<>]*<td[^<>]*>[^<>]*<img[^<>]*>[^<>]' \
             '*</td>[^<>]*<td>[^<>]*<a href="([^"]+)">(.*?)</a>[^<>]*</td>[^<>]*<td[^<>]*>[^<>]*<a[^<>]*>([^<>]+)'

    matches = re.compile(patron, re.DOTALL).findall(data)

    for scrapedurl, scrapedtitle, uploader in matches:

        url = urllib.parse.urljoin(item.url, scrapedurl)

        scrapedtitle = scrapertools.htmlclean(scrapedtitle)

        parsed_title = parse_title(scrapedtitle)

        year = parsed_title['year']

        content_title = parsed_title['title']

        if item.title.find('Películas') != -1:

            if item.title.find(' HD ') != -1:
                quality = 'HD'
            else:
                quality = 'SD'

            title = "[COLOR darkorange][B]" + content_title + \
                    "[/B][/COLOR] (" + year + ") [" + quality + \
                    "] (" + uploader + ")"
        else:
            title = scrapedtitle

        thumbnail = ""

        item.infoLabels = {'year': year}

        itemlist.append(item.clone(action="foro", title=title, url=url, thumbnail=thumbnail, folder=True,
                                   contentTitle=content_title))

    return itemlist


def post(url, data):
    import ssl
    from functools import wraps

    def sslwrap(func):
        @wraps(func)
        def bar(*args, **kw):
            kw['ssl_version'] = ssl.PROTOCOL_TLSv1
            return func(*args, **kw)

        return bar

    ssl.wrap_socket = sslwrap(ssl.wrap_socket)

    request = urllib.request.Request(url, data=data.encode("utf-8"), headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_5) AppleWebKit/537.36 (KHTML, "
                      "like Gecko) Chrome/30.0.1599.101 Safari/537.36"})

    contents = urllib.request.urlopen(request).read()

    return contents


def load_mega_proxy(host, port, password):
    if USE_MC_REVERSE:
        try:
            mega_proxy = MegaProxyServer(host, port, password)
            mega_proxy.daemon = True
            mega_proxy.start()
        except socket.error:
            pass


def mc_api_req(api_url, req):
    load_mega_proxy('', MC_REVERSE_PORT, MC_REVERSE_PASS)
    res = post(api_url, json.dumps(req))
    return json.loads(res)


def mega_api_req(req, get=""):
    seqno = random.randint(0, 0xFFFFFFFF)
    url = 'https://g.api.mega.co.nz/cs?id=%d%s' % (seqno, get)
    return json.loads(post(url, json.dumps([req])))[0]


def format_bytes(bytes, precision=2):
    units = ['B', 'KB', 'MB', 'GB', 'TB']

    bytes = max(bytes, 0)

    pow = min(
        math.floor(
            math.log(
                bytes if bytes else 0,
                1024)),
        len(units) -
        1)

    bytes = float(bytes) / (1 << int(10 * pow))

    return str(round(bytes, precision)) + ' ' + units[int(pow)]


def extract_title(title):
    pattern = re.compile('^[^\[\]()]+', re.IGNORECASE)

    res = pattern.search(title)

    if res:

        return res.group(0)

    else:

        return ""


def play(item):
    itemlist = []

    checksum = hashlib.sha1(item.title.replace("[COLOR green][B](VISTO)[/B][/COLOR] ", '').encode('utf-8')).hexdigest()

    if checksum not in HISTORY:
        HISTORY.append(checksum)

        with open(KODI_TEMP_PATH + 'kodi_nei_history', "a+") as file:
            file.write((checksum + "\n"))

    itemlist.append(item)

    return itemlist


def extract_year(title):
    pattern = re.compile('([0-9]{4})[^p]', re.IGNORECASE)

    res = pattern.search(title)

    if res:

        return res.group(1)

    else:

        return ""


def parse_title(title):
    return {'title': extract_title(title), 'year': extract_year(title)}


def get_filmaffinity_data_advanced(title, year, genre):
    url = "https://www.filmaffinity.com/es/advsearch.php?stext=" + title.replace(' ',
                                                                                 '+').replace('?', '') + "&stype%5B%5D" \
                                                                                                         "=title&country=" \
                                                                                                         "&genre=" + genre + \
          "&fromyear=" + year + "&toyear=" + year

    logger.info(url)

    data = httptools.downloadpage(url).data

    res = re.compile(
        "< *?div +class *?= *?\"avgrat-box\" *?> *?([0-9,]+) *?<",
        re.DOTALL).search(data)

    res_thumb = re.compile(
        "https://pics\\.filmaffinity\\.com/[^\"]+-msmall\\.jpg",
        re.DOTALL).search(data)

    if res:
        rate = res.group(1).replace(',', '.')
    else:
        rate = None

    if res_thumb:
        thumb_url = res_thumb.group(0)
    else:
        thumb_url = None

    return [rate, thumb_url]


def get_filmaffinity_data(title):
    url = "https://www.filmaffinity.com/es/search.php?stext=" + title.replace(' ', '+').replace('?', '')

    logger.info(url)

    data = httptools.downloadpage(url).data

    rate_pattern1 = "\"avgrat-box\" *?> *?([0-9,.]+) *?<"

    rate_pattern2 = "itemprop *?= *?\"ratingValue\" *?content *?= *?\"([0-9,.]+)"

    thumb_pattern = "https://pics\\.filmaffinity\\.com/[^\"]+-m[^\"]+\\.jpg"

    res = re.compile(rate_pattern1, re.DOTALL).search(data)

    res_thumb = re.compile(thumb_pattern, re.DOTALL).search(data)

    if res:
        rate = res.group(1).replace(',', '.')
    else:

        res = re.compile(rate_pattern2, re.DOTALL).search(data)

        if res:
            rate = res.group(1).replace(',', '.')
        else:
            rate = None

    if res_thumb:
        thumb_url = res_thumb.group(0).replace('mmed.jpg', 'msmall.jpg')
    else:
        thumb_url = None

    return [rate, thumb_url]


# NEIFLIX uses a modified version of Alfa's MEGA LIB with support for MEGACRYPTER and multi thread
def check_mega_lib_integrity():
    update_url = ALFA_URL + 'lib/megaserver/'

    megaserver_lib_path = ALFA_PATH + 'lib/megaserver/'

    urllib.request.urlretrieve(update_url + 'checksum.sha1', megaserver_lib_path + 'checksum.sha1')

    sha1_checksums = {}

    with open(megaserver_lib_path + 'checksum.sha1') as f:
        for line in f:
            strip_line = line.strip()
            if strip_line:
                parts = re.split(' +', line.strip())
                sha1_checksums[parts[1]] = parts[0]

    modified = False

    if not os.path.exists(megaserver_lib_path):
        os.mkdir(megaserver_lib_path)

    for filename, checksum in sha1_checksums.items():

        if not os.path.exists(megaserver_lib_path + filename):

            urllib.request.urlretrieve(
                update_url + filename,
                megaserver_lib_path + filename)

            modified = True

        else:

            with open(megaserver_lib_path + filename, 'rb') as f:
                file_hash = hashlib.sha1(f.read()).hexdigest()

            if file_hash != checksum:

                os.rename(
                    megaserver_lib_path +
                    filename,
                    megaserver_lib_path +
                    filename +
                    ".bak")

                if os.path.isfile(megaserver_lib_path + filename + "o"):
                    os.remove(megaserver_lib_path + filename + "o")

                urllib.request.urlretrieve(
                    update_url + filename,
                    megaserver_lib_path + filename)

                modified = True

    return modified


# NEIFLIX uses a modified version of Alfa's MEGA connector with support for MEGACRYPTER and multi thread
def check_nei_connector_integrity():
    update_url = ALFA_URL + 'servers/'

    connectors_path = ALFA_PATH + 'servers/'

    urllib.request.urlretrieve(update_url + 'checksum.sha1', connectors_path + 'checksum.sha1')

    sha1_checksums = {}

    with open(connectors_path + 'checksum.sha1') as f:
        for line in f:
            strip_line = line.strip()
            if strip_line:
                parts = re.split(' +', line.strip())
                sha1_checksums[parts[1]] = parts[0]

    modified = False

    for filename, checksum in sha1_checksums.items():

        if not os.path.exists(connectors_path + filename):

            urllib.request.urlretrieve(
                update_url + filename,
                connectors_path + filename)

            modified = True

        else:

            with open(connectors_path + filename, 'rb') as f:
                file_hash = hashlib.sha1(f.read()).hexdigest()

            if file_hash != checksum:

                if os.path.isfile(connectors_path + filename + "o"):
                    os.remove(connectors_path + filename + "o")

                urllib.request.urlretrieve(
                    update_url + filename,
                    connectors_path + filename)

                modified = True

    return modified


if CHECK_MEGA_STUFF_INTEGRITY and check_mega_lib_integrity():
    xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')',
                                  "Librería de MEGA/MegaCrypter reparada/actualizada",
                                  os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels',
                                               'thumb', 'neiflix2_t.png'), 5000)

if CHECK_MEGA_STUFF_INTEGRITY and check_nei_connector_integrity():
    xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')', "Conector de NEI reparado/actualizado",
                                  os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels',
                                               'thumb', 'neiflix2_t.png'), 5000)

from megaserver import Mega, MegaProxyServer, RequestError, crypto

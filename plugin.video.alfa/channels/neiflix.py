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
import xml.etree.ElementTree as ET
import urllib.request, urllib.error, urllib.parse
import xbmc
import xbmcaddon
import xbmcgui
import html
import time
import shutil
from core.item import Item
from core import httptools, scrapertools, tmdb
from platformcode import config, logger, platformtools
from collections import OrderedDict

CHECK_MEGA_STUFF_INTEGRITY = True

NEIFLIX_VERSION = "2.6"

NEIFLIX_LOGIN = config.get_setting("neiflix_user", "neiflix")

NEIFLIX_PASSWORD = config.get_setting("neiflix_password", "neiflix")

USE_MEGA_PREMIUM = config.get_setting("neiflix_mega_premium", "neiflix")

MEGA_EMAIL = config.get_setting("neiflix_mega_email", "neiflix")

MEGA_PASSWORD = config.get_setting("neiflix_mega_password", "neiflix")

USE_MC_REVERSE = config.get_setting("neiflix_use_mc_reverse", "neiflix")

KODI_TEMP_PATH = xbmc.translatePath('special://temp/')

KODI_USERDATA_PATH = xbmc.translatePath('special://userdata/')

NEIFLIX_RESOURCES_URL = "https://noestasinvitado.com/neiflix_resources/"

GITHUB_BASE_URL = "https://raw.githubusercontent.com/tonikelope/neiflix_alfa_py3/master/"

ALFA_URL = "https://raw.githubusercontent.com/tonikelope/neiflix_alfa_py3/master/plugin.video.alfa/"

ALFA_PATH = xbmc.translatePath('special://home/addons/plugin.video.alfa/')

NEIFLIX_PATH = xbmc.translatePath('special://home/addons/plugin.video.neiflix/');

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


def get_neiflix_resource_path(resource):

    if os.path.exists(xbmc.translatePath("special://home/addons/plugin.video.neiflix/resources/"+resource)):
        return "special://home/addons/plugin.video.neiflix/resources/"+resource
    else:
        return NEIFLIX_RESOURCES_URL+resource

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

        pro_account = False

        if os.path.isfile(filename_hash):

            try:

                with open(filename_hash, "rb") as file:

                    mega = pickle.load(file)

                    pro_account = mega.is_pro_account()

                    login_ok = True

            except Exception as ex:
                logger.info("NEIFLIX MEGA LOGIN EXCEPTION")
                logger.info(ex)
                if os.path.isfile(filename_hash):
                    os.remove(filename_hash)

        if not login_ok:

            mega = Mega()

            try:

                with open(filename_hash, "wb") as file:

                    mega.login(MEGA_EMAIL, MEGA_PASSWORD)

                    pro_account = mega.is_pro_account()

                    pickle.dump(mega, file)

                    login_ok = True

            except Exception as ex:
                logger.info("NEIFLIX MEGA LOGIN EXCEPTION")
                logger.info(ex)
                if os.path.isfile(filename_hash):
                    os.remove(filename_hash)

        if login_ok:

            mega_sid = mega.sid

            login_msg = "LOGIN EN MEGA (free) OK!" if not pro_account else "LOGIN EN MEGA (PRO) OK!"

            logger.info("channels.neiflix "+login_msg+" "+MEGA_EMAIL)

            if verbose:
                xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')', login_msg,
                                              os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media',
                                                           'channels', 'thumb', 'neiflix2_t.png'), 5000)
        else:

            logger.info("channels.neiflix ERROR AL HACER LOGIN EN MEGA: " + MEGA_EMAIL)

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
            itemlist.append(Item(channel=item.channel, title="[B]PELÍCULAS[/B]", section="PELÍCULAS", mode="movie", action="foro",
                                 url="https://noestasinvitado.com/peliculas/", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_videolibrary_movie.png"))
            itemlist.append(Item(channel=item.channel, title="[B]SERIES[/B]", section="SERIES", mode="tvshow", action="foro",
                                 url="https://noestasinvitado.com/series/", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_videolibrary_tvshow.png"))
            itemlist.append(Item(channel=item.channel, title="Documetales", section="Documentales", mode="movie", action="foro",
                                 url="https://noestasinvitado.com/documentales/", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_channels_documentary.png"))
            itemlist.append(Item(channel=item.channel, title="Vídeos deportivos", section="Vídeos deportivos", mode="movie", action="foro",
                                 url="https://noestasinvitado.com/deportes/", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_channels_sport.png"))
            itemlist.append(Item(channel=item.channel, title="Anime", action="foro", section="Anime",
                                 url="https://noestasinvitado.com/anime/", mode="movie", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_channels_anime.png"))
            itemlist.append(Item(channel=item.channel, title="Bibliotaku (Akantor)", action="bibliotaku", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.neiflix/resources/akantor.gif"))
            if not os.path.exists(KODI_USERDATA_PATH + 'neiflix_xxx'):
                itemlist.append(Item(channel=item.channel, title="\"Guarreridas\"", mode="movie", section="Guarreridas", action="foro",
                                     url="https://noestasinvitado.com/18-15/", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_channels_adult.png", xxx=True))
            itemlist.append(Item(channel=item.channel, title="Listados alfabéticos", mode="movie", section="Listados", action="indices",
                                 url="https://noestasinvitado.com/indices/", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_channels_movie_az.png"))
            itemlist.append(
                Item(
                    channel=item.channel,
                    title="[COLOR darkorange][B]Buscar[/B][/COLOR]",
                    action="search", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_search.png"))

            itemlist.append(
                Item(
                    channel=item.channel,
                    title="[B]Preferencias[/B]",
                    action="settings_nei", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))

            itemlist.append(
                Item(
                    channel=item.channel,
                    title="[B]Borrar caché[/B]",
                    action="clean_cache", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))

            itemlist.append(
                Item(
                    channel=item.channel,
                    title="[COLOR red][B]Borrar historial[/B][/COLOR]",
                    action="clean_history", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))

            itemlist.append(
                Item(
                    channel=item.channel,
                    title="Regenerar fichero de ajustes avanzados",
                    action="improve_streaming", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))

            itemlist.append(
                Item(
                    channel=item.channel,
                    title="Regenerar miniaturas (todo KODI)",
                    action="thumbnail_refresh", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))


            if not os.path.exists(KODI_USERDATA_PATH + 'neiflix_xxx'):
                itemlist.append(
                    Item(
                        channel=item.channel,
                        title="Desactivar contenido adulto",
                        action="xxx_off", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))
            else:
                itemlist.append(
                    Item(
                        channel=item.channel,
                        title="Reactivar contenido adulto",
                        action="xxx_on", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))
        else:
            xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')', "ERROR AL HACER LOGIN EN NEI",
                                          os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media',
                                                       'channels', 'thumb', 'neiflix2_t.png'), 5000)
            itemlist.append(
                Item(channel=item.channel,
                     title="[COLOR red][B]ERROR: Usuario y/o password de NEI incorrectos (revisa las preferencias)[/B][/COLOR]",
                     action="", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))

            itemlist.append(
                Item(channel=item.channel,
                     title="[COLOR darkorange][B]Habilita tu cuenta de NEI en preferencias.[/B][/COLOR]",
                     action="settings_nei", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_setting_0.png"))

    return itemlist


def thumbnail_refresh(item):

    ret = xbmcgui.Dialog().yesno(xbmcaddon.Addon().getAddonInfo('name'), '¿SEGURO?')

    if ret:

        try:
            os.remove(xbmc.translatePath('special://userdata/Database/Textures13.db'));

            shutil.rmtree(xbmc.translatePath('special://userdata/Thumbnails'))

            xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')', 'Miniaturas regeneradas', os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'neiflix2_t.png'), 5000)

            ret = xbmcgui.Dialog().yesno(xbmcaddon.Addon().getAddonInfo('name'), 'ES NECESARIO REINICIAR KODI PARA QUE TODOS LOS CAMBIOS TENGAN EFECTO.\n\n¿Quieres reiniciar KODI ahora mismo?')

            if ret:
                xbmc.executebuiltin('RestartApp')

        except Exception as e:
            xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')', 'ERROR al intentar regenerar miniaturas', os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'neiflix2_t.png'), 5000)

def improve_streaming(item):

    ret = xbmcgui.Dialog().yesno(xbmcaddon.Addon().getAddonInfo('name'), '¿SEGURO?')

    if ret:
    
        if os.path.exists(xbmc.translatePath('special://userdata/advancedsettings.xml')):
            os.rename(xbmc.translatePath('special://userdata/advancedsettings.xml'), xbmc.translatePath('special://userdata/advancedsettings.xml')+"."+str(int(time.time()))+".bak")
        
        settings_xml = ET.ElementTree(ET.Element('advancedsettings'))

        cache = settings_xml.findall("cache")
        cache = ET.Element('cache')
        memorysize = ET.Element('memorysize')
        memorysize.text = '52428800'
        readfactor = ET.Element('readfactor')
        readfactor.text = '8'
        cache.append(memorysize)
        cache.append(readfactor)
        settings_xml.getroot().append(cache)

        network = settings_xml.findall("network")
        network = ET.Element('network')
        curlclienttimeout = ET.Element('curlclienttimeout')
        curlclienttimeout.text = '60'
        network.append(curlclienttimeout)
        curllowspeedtime = ET.Element('curllowspeedtime')
        curllowspeedtime.text = '60'
        network.append(curllowspeedtime)
        settings_xml.getroot().append(network)

        playlisttimeout = settings_xml.findall('playlisttimeout')
        playlisttimeout = ET.Element('playlisttimeout')
        playlisttimeout.text = '60'
        settings_xml.getroot().append(playlisttimeout)

        settings_xml.write(xbmc.translatePath('special://userdata/advancedsettings.xml'))

        xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')', "Ajustes avanzados regenerados", os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'neiflix2_t.png'), 5000)

        ret = xbmcgui.Dialog().yesno(xbmcaddon.Addon().getAddonInfo('name'), 'ES NECESARIO REINICIAR KODI PARA QUE TODOS LOS CAMBIOS TENGAN EFECTO.\n\n¿Quieres reiniciar KODI ahora mismo?')

        if ret:
            xbmc.executebuiltin('RestartApp')

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
                xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')', "Porno reactivado", os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'neiflix2_t.png'), 5000)
                return mainlist(item)
            else:
                xbmcgui.Dialog().ok('NEIFLIX: reactivar contenido adulto', 'Contraseña incorrecta')
    else:
        return mainlist(item)


def clean_cache(item):
    conta_files = 0

    for file in os.listdir(KODI_TEMP_PATH):
        if file.startswith("kodi_nei_") and not file.startswith('kodi_nei_debrid_') and file != 'kodi_nei_history':
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


def bibliotaku(item):

    itemlist = []

    itemlist.append(Item(channel=item.channel, title="Bibliotaku (PELÍCULAS)", section="PELÍCULAS", mode="movie", action="bibliotaku_pelis",
                                 url="https://noestasinvitado.com/msg.php?m=114128", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_videolibrary_movie.png"))
    itemlist.append(Item(channel=item.channel, title="Bibliotaku (SERIES)", section="SERIES", mode="tvshow", action="bibliotaku_series",
                         url="https://noestasinvitado.com/msg.php?m=114127", fanart="special://home/addons/plugin.video.neiflix/resources/fanart.png", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_videolibrary_tvshow.png"))
    return itemlist


def bibliotaku_series(item):
    data = httptools.downloadpage(item.url).data

    data = re.sub('[–—]', '-', html.unescape(data))

    data = re.sub('[- ]*?(T|S) *?[0-9U]+[- ]*', ' ', data)
    
    data = re.sub(' *?-+ *?[Tt]emporadas?[^-]+-+ *?', ' ', data)

    data = re.sub(' AC3', ' ', data)

    patron = '\[b\](.*?)\[\/b\].*?LINKS\[.*?\[url_mc\]([0-9]+)'

    itemlist = []

    matches = re.compile(patron, re.DOTALL|re.IGNORECASE).findall(data)

    series = {}

    for scrapedtitle, mc_id in matches:

        parsed_title = parse_title(scrapedtitle)

        if parsed_title['title'] in series:
            series[parsed_title['title']].append(mc_id)
        else:
            series[parsed_title['title']]=[mc_id]

            thumbnail = item.thumbnail

            content_serie_name = ""

            content_title = re.sub('^(Saga|Trilog.a|Duolog*a|ESDLA -) ' , '', parsed_title['title'])

            content_type = "tvshow"

            content_serie_name = content_title

            info_labels = {'year': parsed_title['year']}

            quality = parsed_title['quality']

            title = "[COLOR darkorange][B]" + parsed_title['title'] + "[/B][/COLOR] " + ("(" + parsed_title['year'] + ")" if parsed_title['year'] else "") + (" [" + quality + "]" if quality else "")+" ##*NOTA*##"

            itemlist.append(Item(channel=item.channel, parsed_title=parsed_title['title'], parent_title=item.parent_title, mode=item.mode, thumbnail=thumbnail, section=item.section, action="bibliotaku_series_temporadas", title=title, url=item.url, contentTitle=content_title, contentType=content_type, contentSerieName=content_serie_name, infoLabels=info_labels, uploader="Akantor"))

    tmdb.set_infoLabels_itemlist(itemlist, True)

    for i in itemlist:

        i.mc_group_id = series[i.parsed_title]

        if i.infoLabels and 'rating' in i.infoLabels:

            if i.infoLabels['rating'] >= 7.0:
                rating_text = "[B][COLOR lightgreen][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
            elif i.infoLabels['rating'] < 5.0:
                rating_text = "[B][COLOR red][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
            else:
                rating_text = "[B][" + str(round(i.infoLabels['rating'],1)) + "][/B]"

            i.title = i.title.replace('##*NOTA*##', rating_text)
        else:
            i.title = i.title.replace('##*NOTA*##', '')

    return itemlist


def bibliotaku_series_temporadas(item):

    itemlist = []

    if len(item.mc_group_id) == 1:
        item.infoLabels['season']=1

        item.mc_group_id = item.mc_group_id[0]

        itemlist = bibliotaku_series_megacrypter(item)

    else:
        
        i = 1
        
        for mc_id in item.mc_group_id:
            infoLabels=item.infoLabels

            infoLabels['season']=i
            
            itemlist.append(Item(channel=item.channel, action="bibliotaku_series_megacrypter",
                                 title='[' + str(i) + '/' + str(len(item.mc_group_id)) + '] ' + item.title, url=item.url,
                                 mc_group_id=mc_id, infoLabels=infoLabels, mode=item.mode))

            i = i + 1

        if len(itemlist)>0:
            itemlist.append(Item(channel=item.channel, title="[COLOR orange][B]CRÍTICAS DE FILMAFFINITY[/B][/COLOR]", contentPlot="[I]Críticas de: "+(item.contentSerieName if item.mode == "tvshow" else item.contentTitle)+"[/I]", action="leer_criticas_fa", year=item.infoLabels['year'], mode=item.mode, contentTitle=(item.contentSerieName if item.mode == "tvshow" else item.contentTitle), thumbnail="https://www.filmaffinity.com/images/logo4.png"))
        else:
            itemlist.append(Item(channel=item.channel,title="[COLOR white][B]NO HAY ENLACES SOPORTADOS DISPONIBLES (habla con el UPLOADER para que suba el vídeo (SIN COMPRIMIR) a MEGA[/B][/COLOR]", action="", url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))
            

    tmdb.set_infoLabels_itemlist(itemlist, True)

    return itemlist


def bibliotaku_series_megacrypter(item):

    itemlist = get_video_mega_links_group(Item(channel=item.channel, mode=item.mode, action='', title='', url=item.url, mc_group_id=item.mc_group_id, infoLabels=item.infoLabels))

    tmdb.set_infoLabels_itemlist(itemlist, True)

    return itemlist


def bibliotaku_pelis(item):

    data = httptools.downloadpage(item.url).data

    patron = '\[b\](.*?)\[\/b\].*?LINKS\[.*?\[url_mc\]([0-9]+)'

    itemlist = []

    matches = re.compile(patron, re.DOTALL|re.IGNORECASE).findall(data)

    for scrapedtitle, mc_id in matches:

        thumbnail = item.thumbnail

        content_serie_name = ""

        parsed_title = parse_title(scrapedtitle)

        content_title = re.sub('^(Saga|Trilog.a|Duolog*a|ESDLA -) ' , '', parsed_title['title'])

        content_type = "movie"

        info_labels = {'year': parsed_title['year']}

        quality = parsed_title['quality']

        title = "[COLOR darkorange][B]" + parsed_title['title'] + "[/B][/COLOR] " + ("(" + parsed_title['year'] + ")" if parsed_title['year'] else "") + (" [" + quality + "]" if quality else "")+" ##*NOTA*##"

        itemlist.append(Item(channel=item.channel, mc_group_id=mc_id, parent_title=item.parent_title, mode=item.mode, thumbnail=thumbnail, section=item.section, action="bibliotaku_pelis_megacrypter", title=title, url=item.url, contentTitle=content_title, contentType=content_type, contentSerieName=content_serie_name, infoLabels=info_labels, uploader="Akantor"))

    tmdb.set_infoLabels_itemlist(itemlist, True)

    for i in itemlist:
        if i.infoLabels and 'rating' in i.infoLabels:

            if i.infoLabels['rating'] >= 7.0:
                rating_text = "[B][COLOR lightgreen][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
            elif i.infoLabels['rating'] < 5.0:
                rating_text = "[B][COLOR red][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
            else:
                rating_text = "[B][" + str(round(i.infoLabels['rating'],1)) + "][/B]"

            i.title = i.title.replace('##*NOTA*##', rating_text)
        else:
            i.title = i.title.replace('##*NOTA*##', '')

    return itemlist


def bibliotaku_pelis_megacrypter(item):
    infoLabels=item.infoLabels
            
    itemlist = get_video_mega_links_group(Item(channel=item.channel, mode=item.mode, action='', title='', url=item.url, mc_group_id=item.mc_group_id, infoLabels=infoLabels))

    tmdb.set_infoLabels_itemlist(itemlist, True)

    return itemlist


def foro(item):
    logger.info("channels.neiflix foro")

    if item.xxx and os.path.exists(KODI_USERDATA_PATH + 'neiflix_xxx'):
        return mainlist(item)

    itemlist = []

    data = httptools.downloadpage(item.url).data

    video_links = False

    final_item = False

    action=""

    if '<h3 class="catbg">Subforos</h3>' in data:
        # HAY SUBFOROS
        patron = '< *?a +class *?= *?"subje(.*?)t" +href *?= *?"([^"]+)" +name *?= *?"[^"]+" *?>([^<]+)< *?/ *?a *?(>)'
        action = "foro"
    elif '"subject windowbg4"' in data:
        patron = '< *?td +class *?= *?"subject windowbg4" *?>.*?< *?div *?>.*?< *?span +id *?= *?"([^"]+)" ?>.*?< *?a +href *?= *?"([^"]+)" *?>([^<]+)< *?/ *?a *?> *?< *?/ *?span *?>.*?"Ver +perfil +de +([^"]+)"'
        final_item = True
        action = "foro"
    else:
        video_links = True
        itemlist = find_video_mega_links(item, data) + find_video_gvideo_links(item, data)

    if not video_links:

        matches = re.compile(patron, re.DOTALL|re.IGNORECASE).findall(data)

        for scrapedmsg, scrapedurl, scrapedtitle, uploader in matches:

            url = urllib.parse.urljoin(item.url, scrapedurl)

            if uploader not in UPLOADERS_BLACKLIST and not any(word in scrapedtitle for word in TITLES_BLACKLIST) and not ("Filmografías" in scrapedtitle and action == "foro"):

                scrapedtitle = scrapertools.htmlclean(scrapedtitle)

                if uploader != '>':
                    title = scrapedtitle + " (" + uploader + ")"
                else:
                    title = scrapedtitle
                    uploader=""

                thumbnail = item.thumbnail

                content_serie_name = ""

                if final_item:

                    parsed_title = parse_title(scrapedtitle)

                    content_title = re.sub('^(Saga|Trilog.a|Duolog*a) ' , '', parsed_title['title'])

                    if item.mode == "tvshow":
                        content_type = "tvshow"
                        content_serie_name = content_title
                    else:
                        content_type = "movie"

                    info_labels = {'year': parsed_title['year']}

                    if 'Ultra HD ' in item.parent_title:
                        quality = 'UHD'
                    elif 'HD ' in item.parent_title:
                        quality = 'HD'
                    elif 'SD ' in item.parent_title:
                        quality = 'SD'
                    else:
                        quality = parsed_title['quality']

                    title = "[COLOR darkorange][B]" + parsed_title['title'] + "[/B][/COLOR] " + ("(" + parsed_title['year'] + ")" if parsed_title['year'] else "") + (" [" + quality + "]" if quality else "")+" ##*NOTA*## (" + uploader + ")"

                else:
                    
                    if '(Ultra HD)' in item.title or '(Ultra HD)' in title:
                        if 'Español' in item.title or 'Español' in title:
                            thumbnail = get_neiflix_resource_path("series_uhd_es.png" if item.mode == "tvshow" else "pelis_uhd_es.png")
                        else:
                            thumbnail = get_neiflix_resource_path("series_uhd.png" if item.mode == "tvshow" else "pelis_uhd.png")
                    elif '(HD)' in item.title or '(HD)' in title:
                        if 'Español' in item.title or 'Español' in title:
                            thumbnail = get_neiflix_resource_path("series_hd_es.png" if item.mode == "tvshow" else "pelis_hd_es.png")
                        else:
                            thumbnail = get_neiflix_resource_path("series_hd.png" if item.mode == "tvshow" else "pelis_hd.png")

                    title = "["+ item.section + "] " + title
                    
                    item.parent_title = title.strip()

                    content_title = ""

                    content_type = ""

                    info_labels = []
                    
                    matches = re.compile("([^/]+)/$", re.DOTALL).search(url)

                    if matches.group(1) not in ('hd-espanol-59', 'hd-v-o-v-o-s-61', 'hd-animacion-62', 'sd-espanol-53', 'sd-v-o-v-o-s-54', 'sd-animacion', 'seriesovas-anime-espanol', 'seriesovas-anime-v-o-v-o-s'):
                        url = url + "?sort=first_post;desc"

                itemlist.append(Item(channel=item.channel, parent_title=item.parent_title, mode=item.mode, thumbnail=thumbnail, section=item.section, action=action, title=title, url=url, contentTitle=content_title, contentType=content_type, contentSerieName=content_serie_name, infoLabels=info_labels, uploader=uploader))

        patron = '\[<strong>[0-9]+</strong>\][^<>]*<a class="navPages" href="([^"]+)">'

        matches = re.compile(patron, re.DOTALL).search(data)

        if matches:
            url = matches.group(1)
            title = "[B]>> PÁGINA SIGUIENTE[/B]"
            itemlist.append(Item(channel=item.channel, parent_title=item.parent_title, mode=item.mode, section=item.section, action="foro", title=title, url=url))

        tmdb.set_infoLabels_itemlist(itemlist, True)

        for i in itemlist:
            if i.infoLabels and 'rating' in i.infoLabels:

                if i.infoLabels['rating'] >= 7.0:
                    rating_text = "[B][COLOR lightgreen][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
                elif i.infoLabels['rating'] < 5.0:
                    rating_text = "[B][COLOR red][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
                else:
                    rating_text = "[B][" + str(round(i.infoLabels['rating'],1)) + "][/B]"

                i.title = i.title.replace('##*NOTA*##', rating_text)
            else:
                i.title = i.title.replace('##*NOTA*##', '')

    return itemlist


def search(item, texto):
    
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

    data = httptools.downloadpage("https://noestasinvitado.com/search2/", post=post).data

    return search_parse(data, item)


def search_pag(item):
    data = httptools.downloadpage(item.url).data

    return search_parse(data, item)


def search_parse(data, item):
    itemlist=[]

    patron = '<h5>[^<>]*<a[^<>]+>.*?</a>[^<>]*?<a +href="([^"]+)">(.*?)</a>[^<>]*</h5>[^<>]*<sp' \
             'an[^<>]*>.*?<a[^<>]*"Ver +perfil +de +([^"]+)"'

    matches = re.compile(patron, re.DOTALL).findall(data)

    for scrapedurl, scrapedtitle, uploader in matches:
        url = urllib.parse.urljoin(item.url, scrapedurl)

        scrapedtitle = scrapertools.htmlclean(scrapedtitle)

        if uploader != '>':
            title = scrapedtitle + " (" + uploader + ")"
        else:
            title = scrapedtitle

        thumbnail = ""

        content_serie_name = ""

        parsed_title = parse_title(scrapedtitle)

        content_title = re.sub('^(Saga|Trilog.a|Duolog*a) ' , '', parsed_title['title'])

        quality = ""

        section = ""

        if "/hd-espanol-235/" in url or "/hd-v-o-v-o-s-236/" in url or "/uhd-animacion/" in url:
            content_type = "tvshow"
            content_serie_name = content_title
            quality = "UHD"
            section = "SERIES"
        elif "/hd-espanol-59/" in url or "/hd-v-o-v-o-s-61/" in url or "/hd-animacion-62/" in url:
            content_type = "tvshow"
            content_serie_name = content_title
            quality = "HD"
            section = "SERIES"
        elif "/sd-espanol-53/" in url or "/sd-v-o-v-o-s-54/" in url or "/sd-animacion/" in url:
            content_type = "tvshow"
            content_serie_name = content_title
            quality = "SD"
            section = "SERIES"

        if "/ultrahd-espanol/" in url or "/ultrahd-vo/" in url:
            content_type = "movie"
            quality = "UHD"
            section = "PELÍCULAS"
        elif "/hd-espanol/" in url or "/hd-v-o-v-o-s/" in url:
            content_type = "movie"
            quality = "HD"
            section = "PELÍCULAS"
        elif "/sd-espanol/" in url or "/sd-v-o-v-o-s/" in url or "/sd-animacion/" in url or "/3d-/" in url or "/cine-clasico-/" in url :
            content_type = "tvshow"
            content_serie_name = content_title
            quality = "SD"
            section = "PELÍCULAS"
        elif not quality:
            content_type = "movie"
            quality = parsed_title['quality']

        info_labels = {'year': parsed_title['year']}

        title = ("["+section+"] " if section else "")+"[COLOR darkorange][B]" + parsed_title['title'] + "[/B][/COLOR] " + ("(" + parsed_title['year'] + ")" if parsed_title['year'] else "") + (" [" + quality + "]" if quality else "")+" ##*NOTA*## (" + uploader + ")"

        itemlist.append(Item(channel=item.channel, mode=content_type, thumbnail=thumbnail, section=item.section, action="foro", title=title, url=url, contentTitle=content_title, contentType=content_type, contentSerieName=content_serie_name, infoLabels=info_labels, uploader=uploader))

    patron = '\[<strong>[0-9]+</strong>\][^<>]*<a class="navPages" href="([^"]+)">'

    matches = re.compile(patron, re.DOTALL).search(data)

    if matches:
        url = matches.group(1)
        title = "[B]>> PÁGINA SIGUIENTE[/B]"
        thumbnail = ""
        plot = ""
        itemlist.append(Item(channel=item.channel, action="search_pag", title=title, url=url, thumbnail=item.thumbnail))

    tmdb.set_infoLabels_itemlist(itemlist, True)

    for i in itemlist:
        if i.infoLabels and 'rating' in i.infoLabels:

            if i.infoLabels['rating'] >= 7.0:
                rating_text = "[B][COLOR lightgreen][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
            elif i.infoLabels['rating'] < 5.0:
                rating_text = "[B][COLOR red][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
            else:
                rating_text = "[B][" + str(round(i.infoLabels['rating'],1)) + "][/B]"

            i.title = i.title.replace('##*NOTA*##', rating_text)
        else:
            i.title = i.title.replace('##*NOTA*##', '')

    return itemlist



def indices(item):
    itemlist = []

    categories = ['Películas Ultra HD Español', 'Películas Ultra HD VO', 'Películas HD Español', 'Películas HD VO', 'Películas SD Español', 'Películas SD VO',
                  'Series Ultra HD Español', 'Series Ultra HD VO', 'Series HD Español', 'Series HD VO', 'Series SD Español', 'Series SD VO', 'Películas Anime Español',
                  'Películas Anime VO', 'Series Anime Español', 'Series Anime VO', 'Películas clásicas', 'Deportes',
                  'Películas XXX HD', 'Películas XXX SD', 'Vídeos XXX HD', 'Vídeos XXX SD']

    for cat in categories:

        thumbnail = ""

        if 'Ultra HD' in cat:
            if 'Español' in cat:
                thumbnail = get_neiflix_resource_path("series_uhd_es.png" if 'Series' in cat else "pelis_uhd_es.png")
            else:
                thumbnail = get_neiflix_resource_path("series_uhd.png" if 'Series' in cat else "pelis_uhd.png")
        elif 'HD' in cat:
            if 'Español' in cat:
                thumbnail = get_neiflix_resource_path("series_hd_es.png" if 'Series' in cat else "pelis_hd_es.png")
            else:
                thumbnail = get_neiflix_resource_path("series_hd.png" if 'Series' in cat else "pelis_hd.png")
        elif 'Series' in cat:
            thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_videolibrary_tvshow.png"
        else:
            thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_videolibrary_movie.png"

        mode=""

        if 'Películas' in cat:
            mode = "movie"
        elif 'Series' in cat:
            mode="tvshow"
        else:
            thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_videolibrary_movie.png"

        itemlist.append(Item(channel=item.channel, cat=cat, title=cat, mode=mode, action="gen_index", url="https://noestasinvitado.com/indices/", thumbnail=thumbnail))

    return itemlist


def gen_index(item):
    categories = {'Películas Ultra HD Español':229, 'Películas Ultra HD VO': 230, 'Películas HD Español': 47, 'Películas HD VO': 48, 'Películas SD Español': 44, 'Películas SD VO': 42,
                  'Series Ultra HD Español': 235, 'Series Ultra HD VO': 236, 'Series HD Español': 59, 'Series HD VO': 61, 'Series SD Español': 53, 'Series SD VO': 54,
                  'Películas Anime Español': 66, 'Películas Anime VO': 67, 'Series Anime Español': 68,
                  'Series Anime VO': 69, 'Películas clásicas': 218, 'Deportes': 23, 'Películas XXX HD': 182,
                  'Películas XXX SD': 183, 'Vídeos XXX HD': 185, 'Vídeos XXX SD': 186}

    letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'Ñ', 'O', 'P', 'Q', 'R', 'S', 'T',
               'U', 'V', 'W', 'X', 'Y', 'Z', '0-9']

    itemlist = []

    start = 1

    for letter in letters:
        itemlist.append(Item(channel=item.channel, cat=item.cat, mode=item.mode, thumbnail=item.thumbnail, title="%s (Letra %s)" % (item.title, letter), action="indice_links",url="https://noestasinvitado.com/indices/?id=%d;start=%d" % (categories[item.title], start)))
        start = start + 1

    return itemlist


def get_video_mega_links_group(item):

    mega_sid = mega_login(False)

    itemlist = []

    id = item.mc_group_id

    data = httptools.downloadpage(
        "https://noestasinvitado.com/gen_mc.php?id=" + id + "&raw=1").data

    patron = '(.*? *?\[[0-9.]+ *?.*?\]) *?(https://megacrypter\.noestasinvitado\.com/.+)'

    matches = re.compile(patron).findall(data)

    compress_pattern = re.compile('\.(zip|rar|rev)$', re.IGNORECASE)

    if matches:

        i=1

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

                itemlist.append(Item(channel=item.channel,title="[COLOR white][B]NO HAY ENLACES SOPORTADOS DISPONIBLES (habla con el UPLOADER para que suba el vídeo (SIN COMPRIMIR) a MEGA[/B][/COLOR]", action="", url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))
                
                if item.uploader:
                    itemlist.append(Item(channel=item.channel, title="[COLOR yellow][B]IGNORAR TODO EL CONTENIDO DE "+item.uploader+"[/B][/COLOR]", uploader=item.uploader, action="ignore_uploader", url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))

                break

            else:

                title = "[MEGA] " + name + ' [' + str(format_bytes(size)) + ']'

                if hashlib.sha1(title.encode('utf-8')).hexdigest() in HISTORY:
                    title = "[COLOR lightgreen][B](VISTO)[/B][/COLOR] " + title

                url = url + '#' + name + '#' + str(size) + '#' + key + '#' + noexpire

                infoLabels=item.infoLabels

                if item.mode == "tvshow":
                    episode = re.search(r'^.*?[0-9]+ *?[xX] *?0*([0-9]+)', name)
                    
                    if episode:
                        infoLabels['episode'] = int(episode.group(1))
                    else:
                        infoLabels['episode'] = i

                itemlist.append(
                    Item(channel=item.channel, action="play", server='nei', title=title, url=url + '#' + MC_REVERSE_DATA + '#' + mega_sid, thumbnail=get_neiflix_resource_path("megacrypter.png"), mode=item.mode, infoLabels=infoLabels))

            i=i+1

    else:
        patron_mega = 'https://mega(?:\.co)?\.nz/#[!0-9a-zA-Z_-]+|https://mega(?:\.co)?\.nz/file/[^#]+#[0-9a-zA-Z_-]+'

        matches = re.compile(patron_mega).findall(data)

        if matches:
            i=1
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

                    itemlist.append(Item(channel=item.channel,title="[COLOR white][B]NO HAY ENLACES SOPORTADOS DISPONIBLES (habla con el UPLOADER para que suba el vídeo (SIN COMPRIMIR) a MEGA[/B][/COLOR]", action="", url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))
                    
                    if item.uploader:
                        itemlist.append(Item(channel=item.channel, title="[COLOR yellow][B]IGNORAR TODO EL CONTENIDO DE "+item.uploader+"[/B][/COLOR]", uploader=item.uploader, action="ignore_uploader", url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))

                    break

                else:

                    if hashlib.sha1(title.encode('utf-8')).hexdigest() in HISTORY:
                        title = "[COLOR lightgreen][B](VISTO)[/B][/COLOR] " + title
                        
                        infoLabels=item.infoLabels

                        if item.mode == "tvshow":
                            episode = re.search(r'^.*?[0-9]+ *?[xX] *?0*([0-9]+)', name)
                            
                            if episode:
                                infoLabels['episode'] = int(episode.group(1))
                            else:
                                infoLabels['episode'] = i

                        itemlist.append(Item(channel=item.channel, action="play", server='nei', title=title, url=url, mode=item.mode, thumbnail=get_neiflix_resource_path("mega.png"), infoLabels=infoLabels))

                i=i+1

    if len(itemlist)>0:
        itemlist.append(Item(channel=item.channel, title="[COLOR orange][B]CRÍTICAS DE FILMAFFINITY[/B][/COLOR]", contentPlot="[I]Críticas de: "+(item.contentSerieName if item.mode == "tvshow" else item.contentTitle)+"[/I]", action="leer_criticas_fa", year=item.infoLabels['year'], mode=item.mode, contentTitle=(item.contentSerieName if item.mode == "tvshow" else item.contentTitle), thumbnail="https://www.filmaffinity.com/images/logo4.png"))
    else:
        itemlist.append(Item(channel=item.channel,title="[COLOR white][B]NO HAY ENLACES SOPORTADOS DISPONIBLES (habla con el UPLOADER para que suba el vídeo (SIN COMPRIMIR) a MEGA[/B][/COLOR]", action="", url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))
        
        if item.uploader:
            itemlist.append(Item(channel=item.channel, title="[COLOR yellow][B]IGNORAR TODO EL CONTENIDO DE "+item.uploader+"[/B][/COLOR]", uploader=item.uploader, action="ignore_uploader", url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))
    
    tmdb.set_infoLabels_itemlist(itemlist, True)

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
                         mode=item.mode))
        else:
            itemlist.append(Item(channel=item.channel, action="play", server='gvideo', title='[GVIDEO] ' + item.title,
                                 url=matches[0], mode=item.mode))

    return itemlist



def ignore_uploader(item):

    if item.uploader in UPLOADERS_BLACKLIST:
        UPLOADERS_BLACKLIST.remove(item.uploader)

    UPLOADERS_BLACKLIST.append(item.uploader)

    config.set_setting("neiflix_blacklist_uploaders", ",".join(UPLOADERS_BLACKLIST), "neiflix")

    xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')', item.uploader+ " añadid@ a IGNORADOS",
                                  os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels',
                                               'thumb', 'neiflix2_t.png'), 5000)


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

                infoLabels=item.infoLabels

                if item.mode == "tvshow":
                    infoLabels['season']=i
                
                itemlist.append(Item(channel=item.channel, action="get_video_mega_links_group",
                                     title='[' + str(i) + '/' + str(len(matches)) + '] ' + item.title, url=item.url,
                                     mc_group_id=id, infoLabels=infoLabels, mode=item.mode))

                i = i + 1

            if len(itemlist)>0:
                itemlist.append(Item(channel=item.channel, title="[COLOR orange][B]CRÍTICAS DE FILMAFFINITY[/B][/COLOR]", contentPlot="[I]Críticas de: "+(item.contentSerieName if item.mode == "tvshow" else item.contentTitle)+"[/I]", action="leer_criticas_fa", year=item.infoLabels['year'], mode=item.mode, contentTitle=(item.contentSerieName if item.mode == "tvshow" else item.contentTitle), thumbnail="https://www.filmaffinity.com/images/logo4.png"))
            else:
                itemlist.append(Item(channel=item.channel,title="[COLOR white][B]NO HAY ENLACES SOPORTADOS DISPONIBLES (habla con el UPLOADER para que suba el vídeo (SIN COMPRIMIR) a MEGA[/B][/COLOR]", action="", url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))
                
                if item.uploader:
                    itemlist.append(Item(channel=item.channel, title="[COLOR yellow][B]IGNORAR TODO EL CONTENIDO DE "+item.uploader+"[/B][/COLOR]", uploader=item.uploader, action="ignore_uploader", url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))
    
        else:
            infoLabels=item.infoLabels
            
            if item.mode == "tvshow":
                infoLabels['season'] = 1
            
            itemlist = get_video_mega_links_group(Item(channel=item.channel, mode=item.mode, action='', title='', url=item.url, mc_group_id=matches[0], infoLabels=infoLabels))
    else:

        mega_sid = mega_login(False)

        urls = []

        patron_mc = 'https://megacrypter\.noestasinvitado\.com/[!0-9a-zA-Z_/-]+'

        matches = re.compile(patron_mc).findall(data)

        compress_pattern = re.compile(
            '\.(zip|rar|rev)$', re.IGNORECASE)

        if matches:

            i = 1

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

                        itemlist.append(Item(channel=item.channel,title="[COLOR white][B]NO HAY ENLACES SOPORTADOS DISPONIBLES (habla con el UPLOADER para que suba el vídeo (SIN COMPRIMIR) a MEGA[/B][/COLOR]", action="", url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))
                        
                        if item.uploader:
                            itemlist.append(Item(channel=item.channel, title="[COLOR yellow][B]IGNORAR TODO EL CONTENIDO DE "+item.uploader+"[/B][/COLOR]", uploader=item.uploader, action="ignore_uploader", url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))

                        break
                    else:
                        title = name + ' [' + str(format_bytes(size)) + ']'
                        url = url + '#' + name + '#' + str(size) + '#' + key + '#' + noexpire
                        
                        infoLabels=item.infoLabels

                        if item.mode == "tvshow":
                            episode = re.search(r'^.*?[0-9]+ *?[xX] *?0*([0-9]+)', name)
                            
                            if episode:
                                infoLabels['episode'] = int(episode.group(1))
                            else:
                                infoLabels['episode'] = i

                        itemlist.append(
                            Item(channel=item.channel, action="play", server='nei', title="[MEGA] " + title,
                                 url=url + '#' + MC_REVERSE_DATA + '#' + mega_sid, mode=item.mode, thumbnail=get_neiflix_resource_path("megacrypter.png"), infoLabels=infoLabels))

                    i=i+1

        else:
            patron_mega = 'https://mega(?:\.co)?\.nz/#[!0-9a-zA-Z_-]+|https://mega(?:\.co)?\.nz/file/[^#]+#[0-9a-zA-Z_-]+'

            matches = re.compile(patron_mega).findall(data)

            if matches:
                i = 1
                
                for url in matches:

                    url = re.sub(r"(\.nz/file/)([^#]+)#", r".nz/#!\2!", url)

                    if url not in urls:

                        urls.append(url)

                        if len(url.split("!")) == 3:
                            file_id = url.split("!")[1]
                            file_key = url.split("!")[2]
                            file = mega_api_req({'a': 'g', 'g': 1, 'p': file_id})
                            
                            key = crypto.base64_to_a32(file_key)
                            k = (key[0] ^ key[4], key[1] ^ key[5], key[2] ^ key[6], key[3] ^ key[7])
                            attributes = crypto.base64_url_decode(file['at'])
                            attributes = crypto.decrypt_attr(attributes, k)
                            title = attributes['n'] + ' [' + str(format_bytes(file['s'])) + ']'
                        else:
                            title = url

                        compress = compress_pattern.search(attributes['n'])

                        if compress:
                            itemlist.append(Item(channel=item.channel,title="[COLOR white][B]NO HAY ENLACES SOPORTADOS DISPONIBLES (habla con el UPLOADER para que suba el vídeo (SIN COMPRIMIR) a MEGA[/B][/COLOR]", action="", url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))
                            
                            if item.uploader:
                                itemlist.append(Item(channel=item.channel, title="[COLOR yellow][B]IGNORAR TODO EL CONTENIDO DE "+item.uploader+"[/B][/COLOR]", uploader=item.uploader, action="ignore_uploader", url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))

                            break
                        else:
                            infoLabels=item.infoLabels

                            if item.mode == "tvshow":
                                episode = re.search(r'^.*?[0-9]+ *?[xX] *?0*([0-9]+)', name)
                                
                                if episode:
                                    infoLabels['episode'] = int(episode.group(1))
                                else:
                                    infoLabels['episode'] = i
                            
                            itemlist.append(Item(channel=item.channel, action="play", server='nei', title="[MEGA] " + title, url=url, mode=item.mode, thumbnail=get_neiflix_resource_path("mega.png"), infoLabels=infoLabels))
                    
                        i = i+1

        if len(itemlist)>0:
            itemlist.append(Item(channel=item.channel, title="[COLOR orange][B]CRÍTICAS DE FILMAFFINITY[/B][/COLOR]", contentPlot="[I]Críticas de: "+(item.contentSerieName if item.mode == "tvshow" else item.contentTitle)+"[/I]", action="leer_criticas_fa", year=item.infoLabels['year'], mode=item.mode, contentTitle=(item.contentSerieName if item.mode == "tvshow" else item.contentTitle), thumbnail="https://www.filmaffinity.com/images/logo4.png"))
        else:
            itemlist.append(Item(channel=item.channel,title="[COLOR white][B]NO HAY ENLACES SOPORTADOS DISPONIBLES (habla con el UPLOADER para que suba el vídeo (SIN COMPRIMIR) a MEGA[/B][/COLOR]", action="", url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))
            
            if item.uploader:
                itemlist.append(Item(channel=item.channel, title="[COLOR yellow][B]IGNORAR TODO EL CONTENIDO DE "+item.uploader+"[/B][/COLOR]", uploader=item.uploader, action="ignore_uploader", url="", thumbnail="special://home/addons/plugin.video.alfa/resources/media/themes/default/thumb_error.png"))

    tmdb.set_infoLabels_itemlist(itemlist, True)

    return itemlist

def leer_criticas_fa(item):
    
    fa_data = None

    if 'fa_data' in item:
        fa_data = item.fa_data

    if not fa_data:
        fa_data = get_filmaffinity_data_advanced(item.contentTitle, str(item.year), "TV_SE" if item.mode=="tvshow" else "")

    if isinstance(fa_data, list) and len(fa_data)>1:

        itemlist = []

        for item_fa_data in fa_data:
            itemlist.append(Item(channel=item.channel, fa_data=item_fa_data, contentTitle=item_fa_data['fa_title'], contentPlot="[I]Críticas de: "+item_fa_data['fa_title']+"[/I]", title=item_fa_data['fa_title'], action="leer_criticas_fa", thumbnail=item.thumbnail))

        return itemlist

    else:
        
        if isinstance(fa_data, list):

            if len(fa_data) > 0:
                fa_data = fa_data[0]
            else:
                return []

        film_id = fa_data['film_id']

        criticas_url = "https://www.filmaffinity.com/es/reviews2/1/"+film_id+".html"

        data = httptools.downloadpage(criticas_url, ignore_response_code=True, headers={"Referer": criticas_url, "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.101 Safari/537.36"}).data

        criticas_pattern = "revrat\" *?> *?([0-9]+).*?\"rwtitle\".*?href=\"([^\"]+)\" *?>([^<>]+).*?\"revuser\".*?href=\"[^\"]+\" *?>([^<>]+)"

        res = re.compile(criticas_pattern, re.DOTALL).findall(data)
            
        criticas = []

        for critica_nota, critica_url, critica_title, critica_nick in res:
            criticas.append({'nota': critica_nota, 'url': critica_url, 'title': html.unescape(critica_title), 'nick': critica_nick})

        itemlist = []

        if float(fa_data['rate']) >= 7.0:
            rating_text = "[B][COLOR lightgreen]***** NOTA MEDIA: [" + str(fa_data['rate']) + "] *****[/COLOR][/B]"
        elif float(fa_data['rate']) < 5.0:
            rating_text = "[B][COLOR red]***** NOTA MEDIA: [" + str(fa_data['rate']) + "] *****[/COLOR][/B]"
        else:
            rating_text = "[B]***** NOTA MEDIA: [" + str(fa_data['rate']) + "] *****[/B]"

        itemlist.append(Item(channel=item.channel, contentPlot="[I]Críticas de: "+item.contentTitle+"[/I]", title=rating_text, action="", thumbnail=item.thumbnail))

        for critica in criticas:
            if float(critica['nota']) >= 7.0:
                rating_text = "[B][COLOR lightgreen][" + str(critica['nota']) + "][/COLOR][/B]"
                thumbnail = get_neiflix_resource_path("buena.png")
            elif float(critica['nota']) < 5.0:
                rating_text = "[B][COLOR red][" + str(critica['nota']) + "][/COLOR][/B]"
                thumbnail = get_neiflix_resource_path("mala.png")
            else:
                rating_text = "[B][" + str(critica['nota']) + "][/B]"
                thumbnail = get_neiflix_resource_path("neutral.png")

            itemlist.append(Item(channel=item.channel, nota_fa=fa_data['rate'], contentPlot="[I]Crítica de: "+item.contentTitle+"[/I]", thumbnail=thumbnail, title=rating_text+" "+critica['title']+" ("+critica['nick']+")", action="cargar_critica", url=critica['url']))

        return itemlist

def clean_html_tags(data):
    tag_re = re.compile(r'(<!--.*?-->|<[^>]*>)')

    # Remove well-formed tags, fixing mistakes by legitimate users
    no_tags = tag_re.sub('', data)

    return no_tags

def cargar_critica(item):
    data = httptools.downloadpage(item.url, ignore_response_code=True, headers={"Referer": item.url, "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.101 Safari/537.36"}).data

    critica_pattern = "\"review-text1\" *?>(.*?)< *?/ *?div"

    res = re.compile(critica_pattern, re.DOTALL).search(data)

    if res:
        xbmcgui.Dialog().textviewer(item.title, html.unescape(clean_html_tags(res.group(1).replace('<br>', "\n"))))

def indice_links(item):
    itemlist = []

    data = httptools.downloadpage(item.url).data

    patron = '<tr class="windowbg2">[^<>]*<td[^<>]*>[^<>]*<img[^<>]*>[^<>]' \
             '*</td>[^<>]*<td>[^<>]*<a href="([^"]+)">(.*?)</a>[^<>]*</td>[^<>]*<td[^<>]*>[^<>]*<a[^<>]*>([^<>]+)'

    matches = re.compile(patron, re.DOTALL).findall(data)

    for scrapedurl, scrapedtitle, uploader in matches:

        url = urllib.parse.urljoin(item.url, scrapedurl)

        scrapedtitle = scrapertools.htmlclean(scrapedtitle)

        if uploader != '>':
            title = scrapedtitle + " (" + uploader + ")"
        else:
            title = scrapedtitle

        thumbnail = ""

        content_serie_name = ""

        parsed_title = parse_title(scrapedtitle)

        content_title = re.sub('^(Saga|Trilog.a|Duolog*a) ' , '', parsed_title['title'])

        if item.mode == "tvshow":
            content_type = "tvshow"
            content_serie_name = content_title
        else:
            content_type = "movie"

        info_labels = {'year': parsed_title['year']}

        if 'Ultra HD' in item.cat:
            quality = 'UHD'
        elif 'HD' in item.cat:
            quality = 'HD'
        else:
            quality = 'SD'

        title = "[COLOR darkorange][B]" + parsed_title['title'] + "[/B][/COLOR] " + ("(" + parsed_title['year'] + ")" if parsed_title['year'] else "") + " [" + quality + "] ##*NOTA*## (" + uploader + ")"

        itemlist.append(Item(channel=item.channel, mode=item.mode, thumbnail=thumbnail, section=item.section, action="foro", title=title, url=url, contentTitle=content_title, contentType=content_type, contentSerieName=content_serie_name, infoLabels=info_labels, uploader=uploader))

    tmdb.set_infoLabels_itemlist(itemlist, True)

    for i in itemlist:
        if i.infoLabels and 'rating' in i.infoLabels:

            if i.infoLabels['rating'] >= 7.0:
                rating_text = "[B][COLOR lightgreen][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
            elif i.infoLabels['rating'] < 5.0:
                rating_text = "[B][COLOR red][" + str(round(i.infoLabels['rating'],1)) + "][/COLOR][/B]"
            else:
                rating_text = "[B][" + str(round(i.infoLabels['rating'],1)) + "][/B]"

            i.title = i.title.replace('##*NOTA*##', rating_text)
        else:
            i.title = i.title.replace('##*NOTA*##', '')

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

        return res.group(0).strip()

    else:

        return ""

def extract_quality(title):
    patterns = [{'p': '\[[^\[\]()]*(UHD|2160)', 'q': 'UHD'}, {'p': '\[[^\[\]()]*(microHD|720|1080)', 'q': 'HD'}, {'p': '\[[^\[\]()]*(HDrip|DVD)', 'q': 'SD'}]
    
    for p in patterns:
        pattern = re.compile(p['p'], re.IGNORECASE)

        res = pattern.search(title)

        if res:

            return p['q']

    return None

def play(item):
    itemlist = []

    checksum = hashlib.sha1(item.title.replace("[COLOR lightgreen][B](VISTO)[/B][/COLOR] ", '').encode('utf-8')).hexdigest()

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
    return {'title': extract_title(title), 'year': extract_year(title), 'quality': extract_quality(title)}


def get_filmaffinity_data_advanced(title, year, genre):

    title = re.sub('^Saga ' , '', title)
    
    fa_data_filename = KODI_TEMP_PATH + 'kodi_nei_fa_' + hashlib.sha1((title+year+genre).encode('utf-8')).hexdigest()

    if os.path.isfile(fa_data_filename):
        with open(fa_data_filename, "rb") as f:
            return pickle.load(f)

    url = "https://www.filmaffinity.com/es/advsearch.php?stext=" + title.replace(' ',
                                                                                 '+').replace('?', '') + "&stype%5B%5D" \
                                                                                                         "=title&country=" \
                                                                                                         "&genre=" + genre + \
          "&fromyear=" + year + "&toyear=" + year

    logger.info(url)

    data = httptools.downloadpage(url, ignore_response_code=True, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.101 Safari/537.36"}).data

    res = re.compile("title=\"([^\"]+)\"[^<>]+href=\"https://www.filmaffinity.com/es/film([0-9]+)\.html\".*?(https://pics\.filmaffinity\.com/[^\"]+-msmall\.jpg).*?\"avgrat-box\" *?> *?([0-9,]+).*?", re.DOTALL).findall(data)

    fa_data=[]

    for fa_title, film_id, thumb_url, rate in res:

        rate = rate.replace(',', '.')

        fa_data.append({'rate': rate, 'film_id': film_id, 'fa_title': fa_title, 'thumb_url': thumb_url})

    with open(fa_data_filename, 'wb') as f:
        pickle.dump(fa_data, f)

    return fa_data


def check_neiflix_resources():
    if not os.path.exists(NEIFLIX_PATH+"resources/akantor.gif"):
        opener = urllib.request.URLopener()
        opener.addheader('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.101 Safari/537.36')
        filename, headers = opener.retrieve(NEIFLIX_RESOURCES_URL + "akantor.gif", NEIFLIX_PATH+"resources/akantor.gif")

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


check_neiflix_resources()

if CHECK_MEGA_STUFF_INTEGRITY and check_mega_lib_integrity():
    xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')',
                                  "Librería de MEGA/MegaCrypter reparada/actualizada",
                                  os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels',
                                               'thumb', 'neiflix2_t.png'), 5000)

if CHECK_MEGA_STUFF_INTEGRITY and check_nei_connector_integrity():
    xbmcgui.Dialog().notification('NEIFLIX (' + NEIFLIX_VERSION + ')', "Conector de NEI reparado/actualizado",
                                  os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels',
                                               'thumb', 'neiflix2_t.png'), 5000)

from megaserver import Mega, MegaProxyServer, RequestError, crypto #AL FINAL PORQUE SI HEMOS REPARADO LA LIBRERÍA DE MEGA QUEREMOS IMPORTAR LA VERSIÓN BUENA

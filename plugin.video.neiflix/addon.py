# -*- coding: utf-8 -*-
import base64
import json
import os
import xml.etree.ElementTree as ET
import sys
import time
import urllib.parse
import urllib.request
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

TIMEOUT = 120

ALFA_URL = "https://raw.githubusercontent.com/tonikelope/neiflix_alfa_py3/master/plugin.video.alfa/"

ALFA_PATH = xbmcvfs.translatePath('special://home/addons/plugin.video.alfa/')

FILES = ['channels/neiflix.py', 'channels/neiflix.json', 'servers/nei.py', 'servers/nei.json', 'resources/media/channels/banner/neiflix2_b.png', 'resources/media/channels/thumb/neiflix.gif', 'resources/media/channels/fanart/neiflix2_f.png']

def ajustesAvanzados():
    if os.path.exists(xbmcvfs.translatePath('special://userdata/advancedsettings.xml')):
        os.rename(xbmcvfs.translatePath('special://userdata/advancedsettings.xml'), xbmcvfs.translatePath('special://userdata/advancedsettings.xml')+"."+str(int(time.time()))+".bak")
    
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
    curlclienttimeout.text = str(TIMEOUT)
    network.append(curlclienttimeout)
    curllowspeedtime = ET.Element('curllowspeedtime')
    curllowspeedtime.text = str(TIMEOUT)
    network.append(curllowspeedtime)
    settings_xml.getroot().append(network)

    playlisttimeout = settings_xml.findall('playlisttimeout')
    playlisttimeout = ET.Element('playlisttimeout')
    playlisttimeout.text = str(TIMEOUT)
    settings_xml.getroot().append(playlisttimeout)

    settings_xml.write(xbmcvfs.translatePath('special://userdata/advancedsettings.xml'))


def favoritos():
    try:
        if os.path.exists(xbmcvfs.translatePath('special://userdata/favourites.xml')):
            favourites_xml = ET.parse(xbmcvfs.translatePath('special://userdata/favourites.xml'))
        else:
            favourites_xml = ET.ElementTree(ET.Element('favourites'))

        neiflix = favourites_xml.findall("favourite[@name='NEIFLIX']")

        if neiflix:
            for e in neiflix:
                favourites_xml.getroot().remove(e)

        with open(xbmcvfs.translatePath('special://home/addons/plugin.video.neiflix/favourite.json'), 'r') as f:
            favourite = json.loads(f.read())

        favourite['fanart'] = xbmcvfs.translatePath('special://home/addons/plugin.video.alfa' + favourite['fanart'])
        favourite['thumbnail'] = xbmcvfs.translatePath('special://home/addons/plugin.video.alfa' + favourite['thumbnail'])
        neiflix = ET.Element('favourite', {'name': 'NEIFLIX', 'thumb': xbmcvfs.translatePath('special://home/addons/plugin.video.alfa/resources/media/channels/thumb/neiflix.gif')})
        neiflix.text = 'ActivateWindow(10025,"plugin://plugin.video.alfa/?' + urllib.parse.quote(base64.b64encode(json.dumps(favourite).encode('utf-8')))  + '",return)'
        favourites_xml.getroot().append(neiflix)
        favourites_xml.write(xbmcvfs.translatePath('special://userdata/favourites.xml'))
    except:
        pass


if not os.path.exists(xbmcvfs.translatePath('special://home/addons/plugin.video.neiflix/installed')):

    with open(xbmcvfs.translatePath('special://home/addons/plugin.video.neiflix/installed'), 'w+') as f:
        pass

    for f in FILES:
        if not os.path.exists(ALFA_PATH + f):
            try:
                urllib.request.urlretrieve(ALFA_URL + f, ALFA_PATH + f)
            except:
                pass

    ajustesAvanzados()
    
    favoritos()
    
    ret = xbmcgui.Dialog().yesno(xbmcaddon.Addon().getAddonInfo('name'), 'ES NECESARIO REINICIAR KODI PARA QUE TODOS LOS CAMBIOS TENGAN EFECTO.\n\n¿Quieres reiniciar KODI ahora mismo?')

    if ret:
        xbmc.executebuiltin('RestartApp')
else:
    xbmcgui.Dialog().ok('NEIFLIX', 'PARA ENTRAR EN NEIFLIX UTILIZA EL ICONO DE FAVORITOS (el de la estrella) O BIEN BUSCA NEIFLIX EN LA LISTA DE CANALES DE ALFA')
# -*- coding: utf-8 -*-

# Versión modificada del conector de MEGA para noestasinvitado.com
# Soporte para usar MegaCrypter con RealDebrid / Alldebrid
# Soporte para streaming de vídeo de ficheros grandes troceados con MegaBasterd
# y subidos en diferentes cuentas de MEGA


import sys
PY3 = False
if sys.version_info[0] >= 3: PY3 = True; unicode = str; unichr = chr; long = int

if PY3:
    #from future import standard_library
    #standard_library.install_aliases()
    import urllib.parse
else:
    import urllib                                               # Usamos el nativo de PY2 que es más rápido

from core import httptools
from core import scrapertools
from platformcode import config, logger
from platformcode import platformtools

from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request
import time
from socketserver import ThreadingMixIn
import threading
import re
import base64
import hashlib
import xbmc
import xbmcgui
import xbmcaddon
import os
import pickle
import shutil
import json


KODI_TEMP_PATH = xbmc.translatePath('special://temp/')

DEFAULT_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:65.0) Gecko/20100101 Firefox/65.0'}

AD_API = 'https://api.alldebrid.com/v4/'

AGENT_ID = "AlfaAddon"

AD_ERRORS = {  
        'GENERIC': 'Ha ocurrido un error',
        '404': "Error en la url de la api",
        'AUTH_MISSING_APIKEY': 'La Api-Key no fue enviada',
        'AUTH_BAD_APIKEY': 'Autentificación/Api-Key no válida',
        'AUTH_BLOCKED': 'Api-Key con geobloqueo (Deshabilitelo en su cuenta)\n o ip bloqueada',
        'AUTH_USER_BANNED': 'Esta cuenta ha sido baneada',

        'LINK_IS_MISSING': 'No se ha enviadado ningún link',
        'LINK_HOST_NOT_SUPPORTED': 'Servidor o link no soportados',
        'LINK_DOWN': 'Link caido, no disponible',
        'LINK_PASS_PROTECTED': 'Link con contraseña',
        'LINK_HOST_UNAVAILABLE': 'Servidor en mantenimiento o no disponible',
        'LINK_TOO_MANY_DOWNLOADS': 'Demasiadas descargas simultaneas para este Servidor',
        'LINK_HOST_FULL': 'Nuestros servidores están temporalmente ocupados, intentelo más tarde',
        'LINK_HOST_LIMIT_REACHED': "Ha excedido el limite de descarga para este Servidor",
        'LINK_ERROR': 'No se puede convertir este link',

        'FREE_TRIAL_LIMIT_REACHED': 'Ha superado el limite para cuenta de prueba (7 dias // 25GB descargados\n o Servidor inaccesible para cuentas de prueba)',
        'MUST_BE_PREMIUM': "Debe tener cuenta Premium para procesar este link",

        'PIN_ALREADY_AUTHED': "Ya tiene una Api-Key autentificada",
        'PIN_EXPIRED': "El código introducido expiró",
        'PIN_INVALID': "El código introducido no es válido",

        'NO_SERVER': "Los servidores no tienen permitido usar esta opción. \nVisite https://alldebrid.com/vpn si está usando una VPN."}

MEGA_FILES = None

DEBRID_PROXY_HOST = "localhost"
DEBRID_PROXY_PORT = int(config.get_setting("neiflix_debrid_proxy_port", "neiflix").strip())
NEIFLIX_REALDEBRID = config.get_setting("neiflix_realdebrid", "neiflix")
NEIFLIX_ALLDEBRID = config.get_setting("neiflix_alldebrid", "neiflix")

MEGACRYPTER2DEBRID_ENDPOINT='https://noestasinvitado.com/megacrypter2debrid.php'
MEGACRYPTER2DEBRID_TIMEOUT=120 #Cuando aumente la demanda habrá que implementar en el server de NEI un sistema de polling asíncrono
DEBRID_PROXY_FILE_URL=None
DEBRID_PROXY_URL_LOCK = threading.Lock()

CHUNK_SIZE = 5*1024*1024 #COMPROMISO
WORKERS = 4 #Lo mismo, no subir mucho porque PETA
MAX_CHUNKS_IN_QUEUE = 20 #Si sobra la RAM se puede aumentar (este buffer se suma al propio buffer de KODI)

#multi_urls es una lista de tuplas [(absolute_start_offset, absolute_end_offset, url1), (absolute_start_offset, absolute_end_offset, url2)...]
class neiURL():
    def __init__(self, url):
        self.url = url
        self.multi_urls = self.updateMulti()
        self.size = self.updateSize()
        
    def updateMulti(self):
        hash_url = hashlib.sha256(self.url.encode('utf-8')).hexdigest()

        filename_hash = KODI_TEMP_PATH + 'kodi_nei_multi_' + hash_url

        if os.path.isfile(filename_hash):
            with open(filename_hash, "rb") as file:
                try:
                    multi_urls = pickle.load(file)
                    return multi_urls
                except:
                    return None

        return None

    def updateSize(self):

        if self.multi_urls:

            size = 0

            for url in self.multi_urls:
                size+=url[1]-url[0]+1

            return size

        else:
            return self.getUrlSize(self.url)

    def getUrlSize(self, url):
        request = urllib.request.Request(url, method='HEAD')
        response = urllib.request.urlopen(request)

        if 'Content-Length' in response.headers:
            return int(response.headers['Content-Length'])
        else:
            return -1

    def getPartialRanges(self, start_offset, end_offset):
        if self.multi_urls == None:
            return [(start_offset, end_offset, self.url)]
        else:

            inicio = start_offset
            final = end_offset
            u = 0

            while inicio>self.multi_urls[u][1] and u<len(self.multi_urls):
                u+=1

            if u>=len(self.multi_urls):
                return None

            rangos_parciales=[]

            while inicio < final:
                
                rango_absoluto = (inicio, min(final, self.multi_urls[u][1]), self.multi_urls[u][2])

                inicio+=rango_absoluto[1]-rango_absoluto[0]+1

                rango_parcial = (rango_absoluto[0] - self.multi_urls[u][0], rango_absoluto[1] - self.multi_urls[u][0], self.multi_urls[u][2])

                rangos_parciales.append(rango_parcial)

                u+=1

            return rangos_parciales


class DebridProxyChunkWriter():

    def __init__(self, wfile, start_offset, end_offset):
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.output = wfile
        self.queue = {}
        self.cv_queue_full = threading.Condition()
        self.cv_new_element = threading.Condition()
        self.bytes_written = start_offset
        self.exit = False
        self.next_offset_required = start_offset
        self.chunk_offset_lock = threading.Lock()
        self.chunk_queue_lock = threading.Lock()


    def run(self):

        logger.info('CHUNKWRITER '+' ['+str(self.start_offset)+'-] HELLO')

        try:

            while not self.exit and self.bytes_written < self.end_offset:

                while not self.exit and self.bytes_written < self.end_offset and self.bytes_written in self.queue:

                    self.chunk_queue_lock.acquire()

                    current_chunk = self.queue.pop(self.bytes_written)

                    self.chunk_queue_lock.release()

                    self.output.write(current_chunk)

                    #logger.debug('CHUNKWRITER -> '+str(self.bytes_written)+'-'+str(self.bytes_written+len(current_chunk)-1)+' ('+str(len(current_chunk))+' bytes) SENT!')

                    self.bytes_written+=len(current_chunk)

                    with self.cv_queue_full:
                        self.cv_queue_full.notify_all()

                if not self.exit and self.bytes_written < self.end_offset:

                    #logger.debug("CHUNKWRITER me duermo hasta que llegue el offset -> "+str(self.bytes_written))

                    with self.cv_new_element:
                        self.cv_new_element.wait(1)

        except Exception as ex:
            logger.info(ex)

        self.exit = True

        self.chunk_queue_lock.acquire()

        self.queue.clear()

        self.chunk_queue_lock.release()

        logger.info('CHUNKWRITER '+' ['+str(self.start_offset)+'-] BYE')


    def nextOffset(self):
        
        self.chunk_offset_lock.acquire()

        next_offset = self.next_offset_required

        self.next_offset_required = self.next_offset_required + CHUNK_SIZE if self.next_offset_required + CHUNK_SIZE < self.end_offset else -1;

        self.chunk_offset_lock.release()

        return next_offset


class DebridProxyChunkDownloader():
    
    def __init__(self, id, chunk_writer):
        self.id = id
        self.url = DEBRID_PROXY_FILE_URL
        self.exit = False
        self.chunk_writer = chunk_writer

    def run(self):

        logger.info('CHUNKDOWNLOADER ['+str(self.chunk_writer.start_offset)+'-] '+str(self.id)+' HELLO')

        while not self.exit and not self.chunk_writer.exit:

            offset = self.chunk_writer.nextOffset()

            if offset >=0:

                inicio = offset

                final = min(inicio + CHUNK_SIZE - 1, self.chunk_writer.end_offset)

                partial_ranges = self.url.getPartialRanges(inicio, final)

                #logger.debug("CHUNKDOWNLOADER RANGOS PARCIALES")

                #logger.debug(partial_ranges)

                while not self.chunk_writer.exit and not self.exit and len(self.chunk_writer.queue) >= MAX_CHUNKS_IN_QUEUE and offset!=self.chunk_writer.bytes_written:
                    #logger.debug("CHUNKDOWNLOADER %d me duermo porque la cola está llena!" % self.id)
                    with self.chunk_writer.cv_queue_full:
                        self.chunk_writer.cv_queue_full.wait(1)

                if not self.chunk_writer.exit and not self.exit:
                    full_chunk = bytearray()

                    required_full_chunk_size = final-inicio+1

                    full_chunk_error = True

                    while not self.exit and full_chunk_error and not self.chunk_writer.exit:

                        for partial_range in partial_ranges:

                            p_inicio = partial_range[0]

                            p_final = partial_range[1]

                            url = partial_range[2]

                            request_headers = {'Range': 'bytes='+str(p_inicio)+'-'+str(p_final+5)} #Pedimos 5 bytes de más porque a veces RealDebrid devuelve 1 menos

                            error = True

                            while not self.exit and error and not self.chunk_writer.exit:
                                try:

                                    request = urllib.request.Request(url, headers=request_headers)

                                    with urllib.request.urlopen(request) as response:

                                        required_chunk_size = p_final-p_inicio+1

                                        chunk=response.read(required_chunk_size)

                                        if len(chunk) == required_chunk_size:
                                            full_chunk+=chunk
                                            #logger.debug('CHUNKDOWNLOADER '+str(self.id)+' -> '+str(p_inicio)+'-'+str(p_final)+' ('+str(len(chunk))+' bytes) DOWNLOADED PARTIAL CHUNK!')
                                            error = False
                                        else:
                                            logger.debug('CHUNKDOWNLOADER '+str(self.id)+' -> '+str(p_inicio)+'-'+str(p_final)+' ('+str(len(chunk))+' bytes) PARTIAL CHUNK SIZE ERROR!')
                                            time.sleep(5)

                                except Exception as ex:
                                    logger.debug('CHUNKDOWNLOADER '+str(self.id)+' -> '+str(inicio)+'-'+str(final)+' HTTP ERROR!')
                                    time.sleep(5)

                        if not self.exit and not self.chunk_writer.exit:

                            if len(full_chunk) == required_full_chunk_size:

                                self.chunk_writer.chunk_queue_lock.acquire()
                                
                                if not self.exit and not self.chunk_writer.exit:
                                    self.chunk_writer.queue[inicio]=full_chunk

                                self.chunk_writer.chunk_queue_lock.release()

                                #logger.debug('CHUNKDOWNLOADER '+str(self.id)+' -> '+str(inicio)+'-'+str(final)+' ('+str(len(full_chunk))+' bytes) DOWNLOADED FULL CHUNK!')
                            
                                with self.chunk_writer.cv_new_element:
                                    self.chunk_writer.cv_new_element.notify_all()

                                full_chunk_error = False
                            else:
                                logger.debug('CHUNKDOWNLOADER '+str(self.id)+' -> '+str(inicio)+'-'+str(final)+' ('+str(len(full_chunk))+' bytes) CHUNK SIZE ERROR!')
                                time.sleep(5)

            else:
                self.exit = True

        self.exit = True

        logger.info('CHUNKDOWNLOADER ['+str(self.chunk_writer.start_offset)+'-] '+str(self.id)+' BYE')

class DebridProxy(BaseHTTPRequestHandler):

    def do_HEAD(self):

        if self.path.startswith('/isalive'):
            
            self.send_response(200, "OK")

            self.end_headers()

        else:

            self.updateURL()

            if DEBRID_PROXY_FILE_URL.size < 0:
                
                self.send_response(503)
                self.end_headers()

            else:

                self.sendResponseHeaders()

    
    def do_GET(self):
            
        if self.path.startswith('/isalive'):
            
            self.send_response(200, "OK")

            self.end_headers()

        else:

            self.updateURL()

            if DEBRID_PROXY_FILE_URL.size < 0:
                
                self.send_response(503)
                self.end_headers()

            else:

                range_request = self.sendResponseHeaders()
                
                chunk_writer = DebridProxyChunkWriter(self.wfile, int(range_request[0]) if range_request else 0, int(range_request[1]) if (range_request and range_request[1]) else int(DEBRID_PROXY_FILE_URL.size -1))

                chunk_downloaders=[]

                for c in range(0,WORKERS):
                    chunk_downloader = DebridProxyChunkDownloader(c+1, chunk_writer)
                    chunk_downloaders.append(chunk_downloader)
                    t = threading.Thread(target=chunk_downloader.run)
                    t.daemon = True
                    t.start()

                t = threading.Thread(target=chunk_writer.run)
                t.start()
                t.join()

                for downloader in chunk_downloaders:
                    downloader.exit = True

    
    def updateURL(self):
        global DEBRID_PROXY_FILE_URL

        url = urllib.parse.unquote(re.sub(r'^.*?/proxy/', '', self.path))

        logger.debug(url)

        DEBRID_PROXY_URL_LOCK.acquire()
        
        if not DEBRID_PROXY_FILE_URL or DEBRID_PROXY_FILE_URL.url != url:
            
            DEBRID_PROXY_FILE_URL = neiURL(url)
        
        DEBRID_PROXY_URL_LOCK.release()


    def sendResponseHeaders(self):
        range_request = self.parseRequestRanges()

        if not range_request:
            self.sendCompleteResponseHeaders(DEBRID_PROXY_FILE_URL.size)
            return range_request
        else:

            inicio = int(range_request[0])

            final = int(range_request[1]) if range_request[1] else (int(DEBRID_PROXY_FILE_URL.size) - 1)

            self.sendPartialResponseHeaders(inicio, final, int(DEBRID_PROXY_FILE_URL.size))

            return range_request

    
    def parseRequestRanges(self):

        if 'Range' in self.headers:

            m = re.compile("bytes=([0-9]+)-([0-9]+)?", re.DOTALL).search(self.headers['Range'])

            return (m.group(1), m.group(2))

        else:

            return None

    
    def sendPartialResponseHeaders(self, inicio, final, total):

        headers = {'Server':'Neiflix', 'Accept-Ranges':'bytes', 'Content-Length': str(int(final)-int(inicio)+1), 'Content-Range': 'bytes '+str(inicio)+'-'+str(final)+'/'+str(total), 'Content-Disposition':'attachment', 'Content-Type':'application/force-download', 'Connection':'close'}

        self.send_response(206)

        logger.debug('NEIFLIX RESPONSE 206')

        for h in headers:
            self.send_header(h, headers[h])
            logger.debug('NEIFLIX RESPONSE HEADER '+h+' '+headers[h])

        self.end_headers()

    
    def sendCompleteResponseHeaders(self, total):
        headers = {'Server':'Neiflix', 'Accept-Ranges':'bytes', 'Content-Length': str(total), 'Content-Disposition':'attachment', 'Content-Type':'application/force-download', 'Connection':'close'}

        self.send_response(200)

        logger.debug('NEIFLIX RESPONSE 200')

        for h in headers:
            self.send_header(h, headers[h])
            logger.debug('NEIFLIX RESPONSE HEADER '+h+' '+headers[h])

        self.end_headers()



class ThreadingSimpleServer(ThreadingMixIn, HTTPServer):
    pass

try:
    proxy_server = ThreadingSimpleServer((DEBRID_PROXY_HOST, DEBRID_PROXY_PORT), DebridProxy)
except:
    proxy_server = None


def megacrypter2debrid(link, clean=True):

    email = base64.urlsafe_b64encode(config.get_setting("neiflix_debrid_mega_email", "neiflix").encode('utf-8'))
    
    password = base64.urlsafe_b64encode(config.get_setting("neiflix_debrid_mega_password", "neiflix").encode('utf-8'))

    megacrypter_link = link.split('#')

    link_data = re.sub(r'^.*?(!.+)$', r'\1', megacrypter_link[0])

    mega_link_response = httptools.downloadpage(MEGACRYPTER2DEBRID_ENDPOINT+'?c='+('1' if clean else '0')+'&l='+link_data+'&email='+email.decode('utf-8').replace('=','')+'&password='+password.decode('utf-8').replace('=',''), timeout=MEGACRYPTER2DEBRID_TIMEOUT)

    logger.info(MEGACRYPTER2DEBRID_ENDPOINT+'?c='+('1' if clean else '0')+'&l='+link_data+'&email='+email.decode('utf-8').replace('=','')+'&password='+password.decode('utf-8').replace('=',''))

    logger.info(mega_link_response.data)

    json_response = mega_link_response.json

    if 'error' in json_response:
        logger.debug(json_response['error'])
        return None

    if 'link' in json_response and 'fid_hash' in json_response:
        mega_link = json_response['link']
        fid_hash = json_response['fid_hash']
        return (mega_link, fid_hash)
    else:
        return None


def megacrypter2debridHASH(link):
    megacrypter_link = link.split('#')

    link_data = re.sub(r'^.*?(!.+)$', r'\1', megacrypter_link[0])

    mega_link_response = httptools.downloadpage(MEGACRYPTER2DEBRID_ENDPOINT+'?l='+link_data, timeout=MEGACRYPTER2DEBRID_TIMEOUT)

    logger.info(MEGACRYPTER2DEBRID_ENDPOINT+'?l='+link_data)

    logger.info(mega_link_response.data)

    json_response = mega_link_response.json

    if 'error' in json_response:
        logger.debug(json_response['error'])
        return None

    if 'fid_hash' in json_response:
        fid_hash = json_response['fid_hash']
        return fid_hash
    else:
        return None


def test_video_exists(page_url):
    
    if NEIFLIX_REALDEBRID or NEIFLIX_ALLDEBRID:
        return True, ""

    from megaserver import Client
    
    c = Client(url=page_url, is_playing_fnc=platformtools.is_playing)
    
    global MEGA_FILES
    
    MEGA_FILES = c.get_files()
    
    if isinstance(MEGA_FILES, int):
        return False, "Error codigo %s" % str(MEGA_FILES)

    return True, ""


def check_debrid_urls(itemlist):

    try:
        for i in itemlist:
            url = urllib.parse.unquote(re.sub(r'^.*?/proxy/', '', i[1]))
            logger.info(url)
            request = urllib.request.Request(url, method='HEAD')
            response = urllib.request.urlopen(request)

            if response.status != 200 or 'Content-Length' not in response.headers:
                return True
            elif 'Accept-Ranges' in response.headers and response.headers['Accept-Ranges']!='none':
                size = int(response.headers['Content-Length'])
                request2 = urllib.request.Request(url, headers={'Range': 'bytes='+str(size-1)+'-'+str(size-1)})
                response2 = urllib.request.urlopen(request2)

                if response2.status != 206:
                    return True
    except:
        return True

    return False



def pageURL2DEBRIDCheckCache(page_url):
    if 'megacrypter.noestasinvitado' in page_url:

        fid_hash = megacrypter2debridHASH(page_url)

        if not fid_hash:
            return True

        filename_hash = KODI_TEMP_PATH + 'kodi_nei_debrid_' + fid_hash

        if os.path.isfile(filename_hash):
            with open(filename_hash, "rb") as file:
                try:
                    urls = pickle.load(file)
                    logger.info('DEBRID USANDO CACHE -> '+fid_hash)
                except:
                    urls = None

            return not urls or check_debrid_urls(urls)
        else:
            return True
    else:

        fid = re.subr(r'^.*?#F?!(.*?)!.*$', r'\1', page_url)

        fid_hash = hashlib.sha256(fid).hexdigest()

        filename_hash = KODI_TEMP_PATH + 'kodi_nei_debrid_' + fid_hash

        if os.path.isfile(filename_hash):
            with open(filename_hash, "rb") as file:
                try:
                    urls = pickle.load(file)
                    logger.info('DEBRID USANDO CACHE -> '+fid_hash)
                except:
                    urls = None

            return not urls or check_debrid_urls(urls)
        else:
            return True


def pageURL2DEBRID(page_url, clean=True, cache=True, progress_bar=True):

    if progress_bar:
        pdialog = xbmcgui.DialogProgressBG()   
        pdialog.create('NEIFLIX DEBRID', 'Preparando enlace DEBRID...')
    
    if 'megacrypter.noestasinvitado' in page_url:

        fid_hash = megacrypter2debridHASH(page_url)

        if not fid_hash:
            if progress_bar:
                pdialog.update(100)
                pdialog.close()
            xbmcgui.Dialog().notification('NEIFLIX', "ERROR: POSIBLE ENLACE MEGACRYPTER CADUCADO", os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'neiflix.gif'), 5000)
            return [["NEI DEBRID ERROR (posible enlace de MegaCrypter caducado (sal y vuelve a entrar en la carpeta))", ""]]

        filename_hash = KODI_TEMP_PATH + 'kodi_nei_debrid_' + fid_hash

        if cache and os.path.isfile(filename_hash):
            with open(filename_hash, "rb") as file:
                try:
                    urls = pickle.load(file)
                    logger.info('DEBRID USANDO CACHE -> '+fid_hash)
                except:
                    urls = None

            if urls==None or check_debrid_urls(urls):
                os.remove(filename_hash)

        if not cache or not os.path.isfile(filename_hash):
            with open(filename_hash, "wb") as file:

                response = megacrypter2debrid(page_url, clean)

                if not response:
                    if progress_bar:
                        pdialog.update(100)
                        pdialog.close()
                    xbmcgui.Dialog().notification('NEIFLIX', "ERROR: REVISA TU CUENTA DE MEGA AUXILIAR", os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'neiflix.gif'), 5000)
                    return [["NEI DEBRID ERROR (revisa que haya espacio suficiente en tu cuenta de MEGA auxiliar)", ""]]

                page_url = response[0]

                urls = RD_get_video_url(page_url) if NEIFLIX_REALDEBRID else AD_get_video_url(page_url)

                pickle.dump(urls, file)
    else:

        fid = re.subr(r'^.*?#F?!(.*?)!.*$', r'\1', page_url)

        fid_hash = hashlib.sha256(fid).hexdigest()

        filename_hash = KODI_TEMP_PATH + 'kodi_nei_debrid_' + fid_hash

        if cache and os.path.isfile(filename_hash):
            with open(filename_hash, "rb") as file:
                try:
                    urls = pickle.load(file)
                    logger.info('DEBRID USANDO CACHE -> '+fid_hash)
                except:
                    urls = None
       
            if urls==None or check_debrid_urls(urls):
                os.remove(filename_hash)

        if not cache or not os.path.isfile(filename_hash):
            with open(filename_hash, "wb") as file:
                
                urls = RD_get_video_url(page_url) if NEIFLIX_REALDEBRID else AD_get_video_url(page_url)
                
                pickle.dump(urls, file)

    if progress_bar:
        pdialog.update(100)
        pdialog.close()
    
    return urls


def get_video_url(page_url, premium=False, user="", password="", video_password=""):

    logger.info(page_url)

    if proxy_server:
        start_proxy()

    if page_url[0]=='*':
        #ENLACE MULTI (vídeo troceado con MegaBasterd) 

        logger.info(page_url)

        if NEIFLIX_REALDEBRID:

            multi_video_urls=[]

            video_sizes=[]

            page_urls = page_url.split('#')

            pdialog = xbmcgui.DialogProgressBG()

            pdialog.create('NEIFLIX MULTI', 'Preparando enlace MULTI-BASTERD('+str(len(page_urls)-1)+')...')

            pdialog_increment = round(100/(len(page_urls)-1))

            pdialog_tot = 100

            pdialog_counter = 0

            i = 1

            cache_error=False

            while i<len(page_urls) and not cache_error:
                url = base64.b64decode(page_urls[i].encode('utf-8')).decode('utf-8')
                cache_error = pageURL2DEBRIDCheckCache(url)
                i+=1

            i = 1

            use_cache = not cache_error

            megacrypter2debrid_error = False

            while i<len(page_urls) and not megacrypter2debrid_error:
                url = base64.b64decode(page_urls[i].encode('utf-8')).decode('utf-8')
                logger.info(url)

                if 'megacrypter.noestasinvitado' in url:
                    url_parts = url.split('#')
                    video_sizes.append(int(url_parts[2]))
                else:
                    url_parts = url.split('@')
                    video_sizes.append(int(url_parts[1]))

                clean = True if i==1 else False

                debrid_url = pageURL2DEBRID(url, clean=clean, cache=use_cache, progress_bar=False)

                if not debrid_url[0][1] or debrid_url[0][1]=="":
                    megacrypter2debrid_error = True
                else:
                    multi_video_urls.append(debrid_url)

                pdialog_counter+=min(pdialog_increment, 100-pdialog_counter)
                
                pdialog.update(pdialog_counter)

                i+=1

            pdialog.close()

            if not megacrypter2debrid_error:
                logger.info(multi_video_urls)

                multi_urls_ranges=[]

                s=0

                i=0

                for murl in multi_video_urls:
                    multi_urls_ranges.append((s,s+video_sizes[i]-1,urllib.parse.unquote(re.sub(r'^.*?/proxy/', '', murl[0][1]))))
                    s+=video_sizes[i]
                    i+=1

                logger.info(multi_urls_ranges)

                hash_url = hashlib.sha256(urllib.parse.unquote(re.sub(r'^.*?/proxy/', '', multi_video_urls[0][0][1])).encode('utf-8')).hexdigest()

                filename_hash = KODI_TEMP_PATH + 'kodi_nei_multi_' + hash_url

                with open(filename_hash, "wb") as file:
                    pickle.dump(multi_urls_ranges, file)

                video_urls = multi_video_urls[0]

                video_urls=[[re.sub(r'part[0-9]+-[0-9]+', 'MEGA MULTI ', video_urls[0][0]), 'http://localhost:'+str(DEBRID_PROXY_PORT)+'/proxy/'+urllib.parse.quote(urllib.parse.unquote(re.sub(r'^.*?/proxy/', '', video_urls[0][1])))]]

                return video_urls
            else:
                xbmcgui.Dialog().notification('NEIFLIX', "ERROR: REVISA TU CUENTA DE MEGA AUXILIAR", os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'neiflix.gif'), 5000)
                return [["NEI DEBRID ERROR (revisa que haya espacio suficiente en tu cuenta de MEGA auxiliar)", ""]]

        else:
            xbmcgui.Dialog().notification('NEIFLIX', "ERROR: ENLACES MULTI NO SOPORTADOS", os.path.join(xbmcaddon.Addon().getAddonInfo('path'), 'resources', 'media', 'channels', 'thumb', 'neiflix.gif'), 5000)
            return [["NO SOPORTADO", ""]]

    else:

        if NEIFLIX_REALDEBRID or NEIFLIX_ALLDEBRID:
            return pageURL2DEBRID(page_url)

        page_url = page_url.replace('/embed#', '/#')
        
        logger.info("(page_url='%s')" % page_url)
        
        video_urls = []

        for f in MEGA_FILES:
            media_url = f["url"]
            video_urls.append([scrapertools.get_filename_from_url(media_url)[-4:] + " [mega]", media_url])

        return video_urls


def proxy_run():
    logger.info(time.asctime(), "NEI DEBRID PROXY SERVER Starts - %s:%s" % (DEBRID_PROXY_HOST, DEBRID_PROXY_PORT))
    proxy_server.serve_forever()


def start_proxy():
    t = threading.Thread(target=proxy_run)
    t.setDaemon(True)
    t.start()


# Returns an array of possible video url's from the page_url
def RD_get_video_url(page_url, premium=False, user="", password="", video_password=""):

    logger.info("(page_url='%s' , video_password=%s)" % (page_url, video_password))
    page_url = page_url.replace(".nz/embed", ".nz/")
    # Se comprueba si existe un token guardado y sino se ejecuta el proceso de autentificación
    token_auth = config.get_setting("token", server="realdebrid")
    if token_auth is None or token_auth == "":
        if config.is_xbmc():
            token_auth = RD_authentication()
            if token_auth == "":
                return [["NEI REAL-DEBRID: No se ha completado el proceso de autentificación", ""]]
        else:
            return [["Es necesario activar la cuenta. Accede al menú de ayuda", ""]]

    post_link = urllib.parse.urlencode([("link", page_url), ("password", video_password)])
    DEFAULT_HEADERS["Authorization"] = "Bearer %s" % token_auth
    url = "https://api.real-debrid.com/rest/1.0/unrestrict/link"
    data = httptools.downloadpage(url, post=post_link, headers=list(DEFAULT_HEADERS.items())).json
    logger.error(data)

    check = config.get_setting("secret", server="realdebrid")
    #Se ha usado la autentificación por urlresolver (Bad Idea)
    if "error" in data and data["error"] == "bad_token" and not check:
        token_auth = RD_authentication()
        DEFAULT_HEADERS["Authorization"] = "Bearer %s" % token_auth
        data = httptools.downloadpage(url, post=post_link, headers=list(DEFAULT_HEADERS.items())).json

    # Si el token es erróneo o ha caducado, se solicita uno nuevo
    elif "error" in data and data["error"] == "bad_token":
        
        debrid_id = config.get_setting("id", server="realdebrid")
        secret = config.get_setting("secret", server="realdebrid")
        refresh = config.get_setting("refresh", server="realdebrid")

        post_token = urllib.parse.urlencode({"client_id": debrid_id, "client_secret": secret, "code": refresh,
                                       "grant_type": "http://oauth.net/grant_type/device/1.0"})
        renew_token = httptools.downloadpage("https://api.real-debrid.com/oauth/v2/token", post=post_token,
                                                headers=list(DEFAULT_HEADERS.items())).json
        if not "error" in renew_token:
            token_auth = renew_token["access_token"]
            config.set_setting("token", token_auth, server="realdebrid")
            DEFAULT_HEADERS["Authorization"] = "Bearer %s" % token_auth
            data = httptools.downloadpage(url, post=post_link, headers=list(DEFAULT_HEADERS.items())).json
        else:
            token_auth = RD_authentication()
            DEFAULT_HEADERS["Authorization"] = "Bearer %s" % token_auth
            data = httptools.downloadpage(url, post=post_link, headers=list(DEFAULT_HEADERS.items())).json
    if "download" in data:
        return RD_get_enlaces(data)
    else:
        if "error" in data:
            if not PY3:
                msg = data["error"].decode("utf-8", "ignore")
            else:
                msg = data["error"]
            msg = msg.replace("hoster_unavailable", "Servidor no disponible") \
                .replace("unavailable_file", "Archivo no disponible") \
                .replace("hoster_not_free", "Servidor no gratuito") \
                .replace("bad_token", "Error en el token")
            return [["NEI REAL-DEBRID: " + msg, ""]]
        else:
            return [["NEI REAL-DEBRID: No se ha generado ningún enlace", ""]]


def RD_get_enlaces(data):

    itemlist = []
    if "alternative" in data:
        for link in data["alternative"]:
            if not PY3:
                video_url = link["download"].encode("utf-8")
            else:
                video_url = link["download"]
            title = video_url.rsplit(".", 1)[1]
            if "quality" in link:
                title += " (" + link["quality"] + ") [realdebrid]"
            itemlist.append([title, 'http://localhost:'+str(DEBRID_PROXY_PORT)+'/proxy/'+urllib.parse.quote(video_url)])
    else:
        if not PY3:
            video_url = data["download"].encode("utf-8")
        else:
            video_url = data["download"]
        title = video_url.rsplit(".", 1)[1] + " [realdebrid]"
        itemlist.append([title, 'http://localhost:'+str(DEBRID_PROXY_PORT)+'/proxy/'+urllib.parse.quote(video_url)])

    return itemlist


def RD_authentication():
    logger.info()
    try:
        client_id = "YTWNFBIJEEBP6"

        # Se solicita url y código de verificación para conceder permiso a la app
        url = "http://api.real-debrid.com/oauth/v2/device/code?client_id=%s&new_credentials=yes" % (client_id)
        data = httptools.downloadpage(url, headers=list(DEFAULT_HEADERS.items())).json
        verify_url = data["verification_url"]
        user_code = data["user_code"]
        device_code = data["device_code"]
        intervalo = data["interval"]

        dialog_auth = platformtools.dialog_progress(config.get_localized_string(70414),
                                                    config.get_localized_string(60252) % verify_url,
                                                    config.get_localized_string(70413) % user_code,
                                                    config.get_localized_string(60254))

        # Generalmente cada 5 segundos se intenta comprobar si el usuario ha introducido el código
        while True:
            time.sleep(intervalo)
            try:
                if dialog_auth.iscanceled():
                    return ""

                url = "https://api.real-debrid.com/oauth/v2/device/credentials?client_id=%s&code=%s" \
                      % (client_id, device_code)
                data = httptools.downloadpage(url, headers=list(DEFAULT_HEADERS.items())).json
                if "client_secret" in data:
                    # Código introducido, salimos del bucle
                    break
            except:
                pass

        try:
            dialog_auth.close()
        except:
            pass

        debrid_id = data["client_id"]
        secret = data["client_secret"]

        # Se solicita el token de acceso y el de actualización para cuando el primero caduque
        post = urllib.parse.urlencode({"client_id": debrid_id, "client_secret": secret, "code": device_code,
                                 "grant_type": "http://oauth.net/grant_type/device/1.0"})
        data = httptools.downloadpage("https://api.real-debrid.com/oauth/v2/token", post=post,
                                         headers=list(DEFAULT_HEADERS.items())).json

        token = data["access_token"]
        refresh = data["refresh_token"]

        config.set_setting("id", debrid_id, server="realdebrid")
        config.set_setting("secret", secret, server="realdebrid")
        config.set_setting("token", token, server="realdebrid")
        config.set_setting("refresh", refresh, server="realdebrid")

        return token
    except:
        import traceback
        logger.error(traceback.format_exc())
        return ""

def AD_get_video_url(page_url, premium=False, user="", password="", video_password="", retry=True):
    logger.info()
    
    api_key = config.get_setting("api_key", server="alldebrid")

    if not api_key:
        if config.is_xbmc():
            api_key = AD_authentication()
            if not api_key:
                return [["NEI ALL-DEBRID: No se ha podido completar el proceso de autentificación", ""]]
            elif isinstance(api_key, dict):
                error = api_key['error']
                return [['[All-Debrid] %s' % error, ""]]
        else:
            return [["NEI ALL-DEBRID: es necesario activar la cuenta manualmente. Accede al menú de ayuda", ""]]
    
    page_url = urllib.parse.quote(page_url)
    url = "%slink/unlock?agent=%s&apikey=%s&link=%s" % (AD_API, AGENT_ID, api_key, page_url)
    
    dd = httptools.downloadpage(url).json
    dd_data = dd.get('data', '')

    error = dd.get('error', '')
    
    if error:
        code = error.get('code', '')
        if code == 'AUTH_BAD_APIKEY' and retry:
            config.set_setting("api_key", "", server="alldebrid")
            return AD_get_video_url(page_url, premium=premium, retry=False)
        elif code:
            msg = AD_ERRORS.get(code, code)
            logger.error(dd)
            return [['[All-Debrid] %s' % msg, ""]]

    video_urls = AD_get_links(dd_data)
    
    if video_urls:
        return video_urls
    else:
        server_error = "Alldebrid: Error desconocido en la api"
        return server_error


def AD_get_links(dd_data):
    logger.info()
    if not dd_data:
        return False
    video_urls = list()

    link = dd_data.get('link', '')
    streams = dd_data.get('streams', '')
    
    if link:
        extension = dd_data['filename'][-4:]
        video_urls.append(['%s [Original][All-Debrid]' % extension, link])
    
    if streams:
        for info in streams:
            quality = str(info.get('quality', ''))
            if quality:
                quality += 'p'
            ext = info.get('ext', '')
            link = info.get('link', '')
            video_urls.append(['%s %s [All-Debrid]' % (extension, quality), link])

    return video_urls


def AD_authentication():
    logger.info()
    api_key = ""
    try:

        #https://docs.alldebrid.com
        url = "%spin/get?agent=%s" % (AD_API, AGENT_ID)
        data = httptools.downloadpage(url, ignore_response_code=True).json
        json_data = data.get('data','')
        if not json_data:
            return False

        pin = json_data["pin"]
        base_url = json_data["base_url"]
        #check = json_data["check"]
        expires = json_data["expires_in"]
        check_url = json_data["check_url"]

        intervalo = 5

        dialog_auth = platformtools.dialog_progress(config.get_localized_string(70414),
                                                    config.get_localized_string(60252) % base_url,
                                                    config.get_localized_string(70413) % pin,
                                                    config.get_localized_string(60254))

        #Cada 5 segundos se intenta comprobar si el usuario ha introducido el código
        #Si el tiempo que impone alldebrid (10 mins) expira se detiene el proceso
        while expires > 0:
            time.sleep(intervalo)
            expires -= intervalo
            try:
                if dialog_auth.iscanceled():
                    return False

                
                data = httptools.downloadpage(check_url, ignore_response_code=True).json
                check_data = data.get('data','')
                
                if not check_data:
                    code = data['error']['code']
                    msg = AD_ERRORS.get(code, code)
                    return {'error': msg}
                
                if check_data["activated"]:
                    api_key = check_data["apikey"]
                    break
            except:
                pass

        try:
            dialog_auth.close()
        except:
            pass

        if expires <= 0:
            error = "Tiempo de espera expirado. Vuelva a intentarlo"
            return {'error': error}

        if api_key:
            config.set_setting("api_key", api_key, server="alldebrid")
            return api_key
        else:
            return False
    except:
        import traceback
        logger.error(traceback.format_exc())
        return False

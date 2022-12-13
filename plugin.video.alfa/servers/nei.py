# -*- coding: utf-8 -*-

# Versión modificada del conector de MEGA para Noestasinvitado.com
# Soporte (experimental) para usar MegaCrypter con RealDebrid / Alldebrid
# Incluye proxy para parchear al vuelo cabeceras Content-Range defectuosas 
#aleatorias de RealDebrid y poder saltar en el vídeo hacia delante/atrás


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
import os
import pickle

KODI_TEMP_PATH = xbmc.translatePath('special://temp/')

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:65.0) Gecko/20100101 Firefox/65.0'}

AD_API = 'https://api.alldebrid.com/v4/'

agent_id = "AlfaAddon"

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

files = None

hostName = "localhost"

hostPort = int(config.get_setting("neiflix_debrid_proxy_port", "neiflix").strip())

NEIFLIX_REALDEBRID = config.get_setting("neiflix_realdebrid", "neiflix")

NEIFLIX_ALLDEBRID = config.get_setting("neiflix_alldebrid", "neiflix")

file_url=None
file_size=0
lock = threading.Lock()

class DebridProxy(BaseHTTPRequestHandler):

    def update_file_size(self, url):
        request_headers={}
        request_headers['Range']='bytes=0-'
        request = urllib.request.Request(url, headers=request_headers, method='HEAD')
        response = urllib.request.urlopen(request)
        headers = response.getheaders()

        for header in headers:
            if header[0] == 'Content-Length':
                return int(header[1])

        return 0

    def do_HEAD(self):

        if self.path.startswith('/isalive'):
            
            self.send_response(200, "OK")

            self.end_headers()

        else:

            global file_url, file_size

            url = urllib.parse.unquote(re.sub(r'^.*?/proxy/', '', self.path))

            logger.info(url)

            lock.acquire()
            if file_url!=url:
                file_url = url
                file_size=self.update_file_size(file_url)
            lock.release()

            request_headers={}

            for h in self.headers:
                if h != 'Host':
                    request_headers[h]=self.headers[h]
                    logger.info('do_HEAD HEADER '+h+' '+self.headers[h])

            request = urllib.request.Request(url, headers=request_headers, method='HEAD')
            
            response = urllib.request.urlopen(request)
            
            headers = response.getheaders()
            
            self.send_response(response.status)

            good_headers={}

            size=0

            for header in headers:
                good_headers[header[0]]=header[1]

            for h in good_headers:
                self.send_header(h, good_headers[h])
                logger.info('GH '+h+' '+good_headers[h])

            self.end_headers()

            chunk = response.read(4096)
            
            try:
                while chunk:
                    self.wfile.write(chunk)
                    chunk = response.read(4096)
            except:
                pass


    def do_GET(self):
            
        if self.path.startswith('/isalive'):
            
            self.send_response(200, "OK")

            self.end_headers()

        else:

            global file_url, file_size

            url = urllib.parse.unquote(re.sub(r'^.*?/proxy/', '', self.path))

            logger.info(url)

            lock.acquire()
            if file_url!=url:
                file_url = url
                file_size=self.update_file_size(file_url)
            lock.release()

            request_headers={}

            for h in self.headers:
                if h != 'Host':
                    request_headers[h]=self.headers[h]
                    logger.info('do_GET HEADER '+h+' '+self.headers[h])

            request = urllib.request.Request(url, headers=request_headers)
            
            response = urllib.request.urlopen(request)
            
            headers = response.getheaders()
            
            self.send_response(response.status)

            good_headers={}

            range_size=0

            for header in headers:

                if header[0] == 'Content-Length':
                    range_size = int(header[1])
                    good_headers[header[0]]=header[1]
             
            for header in headers:

                if header[0] == 'Content-Range':
                    inicio = int(re.sub(r'^.*?bytes *?([0-9]+).+$', r'\1', header[1]))
                    final = inicio + range_size - 1
                    good_headers[header[0]]='bytes '+str(inicio)+'-'+str(final)+'/'+str(file_size)
                else:
                    good_headers[header[0]]=header[1]

            for h in good_headers:
                self.send_header(h, good_headers[h])
                logger.info('GH '+h+' '+good_headers[h])

            self.end_headers()

            #¿HILOS AQUI?

            chunk = response.read(4096)
            
            try:
                while chunk:
                    self.wfile.write(chunk)
                    chunk = response.read(4096)
            except:
                pass

class ThreadingSimpleServer(ThreadingMixIn, HTTPServer):
    pass

try:
    proxy_server = ThreadingSimpleServer((hostName, hostPort), DebridProxy)
except:
    proxy_server = None



def megacrypter2debrid(link):

    email = base64.urlsafe_b64encode(config.get_setting("neiflix_debrid_mega_email", "neiflix").encode('utf-8'))
    
    password = base64.urlsafe_b64encode(config.get_setting("neiflix_debrid_mega_password", "neiflix").encode('utf-8'))

    megacrypter_link = link.split('#')

    link_data = re.sub(r'^.*?(!.+)$', r'\1', megacrypter_link[0])

    logger.info('https://noestasinvitado.com/megacrypter2debrid.php?l='+link_data+'&email='+email.decode('utf-8').replace('=','')+'&password='+password.decode('utf-8').replace('=',''))

    mega_link_response = httptools.downloadpage('https://noestasinvitado.com/megacrypter2debrid.php?l='+link_data+'&email='+email.decode('utf-8').replace('=','')+'&password='+password.decode('utf-8').replace('=',''), timeout=60)

    mega_link = re.sub(r'^.*?(http.+)$', r'\1', mega_link_response.data)

    fid_hash = re.sub(r'^.*?@(.*?)#.*$', r'\1', mega_link_response.data)

    return (mega_link.strip(), fid_hash.strip()) if 'httpERROR' not in mega_link else None


def megacrypter2debridHASH(link):
    megacrypter_link = link.split('#')

    link_data = re.sub(r'^.*?(!.+)$', r'\1', megacrypter_link[0])

    mega_link_response = httptools.downloadpage('https://noestasinvitado.com/megacrypter2debrid.php?l='+link_data, timeout=60)

    fid_hash = re.sub(r'^.*?@(.*?)#.*$', r'\1', mega_link_response.data)

    return fid_hash.strip() if 'hashERROR' not in fid_hash else None


def test_video_exists(page_url):
    
    if NEIFLIX_REALDEBRID or NEIFLIX_ALLDEBRID:
        return True, ""

    from megaserver import Client
    c = Client(url=page_url, is_playing_fnc=platformtools.is_playing)
    global files
    files = c.get_files()
    if isinstance(files, int):
        return False, "Error codigo %s" % str(files)

    return True, ""


def check_debrid_urls(itemlist):

    try:
        for i in itemlist:
            url = urllib.parse.unquote(re.sub(r'^.*?/proxy/', '', i[1]))
            logger.info(url)
            request = urllib.request.Request(url, method='HEAD')
            response = urllib.request.urlopen(request)

            if response.status != 200:
                return True
    except:
        return True

    return False

def get_video_url(page_url, premium=False, user="", password="", video_password=""):

    logger.info(page_url)

    if NEIFLIX_REALDEBRID:

        if proxy_server:
            start_proxy()
    
        if 'megacrypter.noestasinvitado' in page_url:

            fid_hash = megacrypter2debridHASH(page_url)

            filename_hash = KODI_TEMP_PATH + 'kodi_nei_debrid_' + fid_hash

            if os.path.isfile(filename_hash):
                with open(filename_hash, "rb") as file:
                    try:
                        urls = pickle.load(file)
                        logger.info('DEBRID USANDO CACHE -> '+fid_hash)
                    except:
                        urls = None

                if urls==None or check_debrid_urls(urls):
                    os.remove(filename_hash)

            if not os.path.isfile(filename_hash):
                with open(filename_hash, "wb") as file:

                    response = megacrypter2debrid(page_url)

                    if not response:
                        return [["NEI DEBRID: revisa los datos de tu cuenta auxiliar de MEGA", ""]]

                    page_url = response[0]

                    urls = RD_get_video_url(page_url)

                    pickle.dump(urls, file)
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
           
                if urls==None or check_debrid_urls(urls):
                    os.remove(filename_hash)

            if os.path.isfile(filename_hash):
                with open(filename_hash, "wb") as file:
                    urls = RD_get_video_url(page_url)
                    pickle.dump(urls, file)

        return urls

    if NEIFLIX_ALLDEBRID:
    
        if 'megacrypter.noestasinvitado' in page_url:

            fid_hash = megacrypter2debridHASH(page_url)

            filename_hash = KODI_TEMP_PATH + 'kodi_nei_debrid_' + fid_hash

            if os.path.isfile(filename_hash):
                with open(filename_hash, "rb") as file:
                    try:
                        urls = pickle.load(file)
                        logger.info('DEBRID USANDO CACHE -> '+fid_hash)
                    except:
                        urls = None

                if urls==None or check_debrid_urls(urls):
                    os.remove(filename_hash)

            if not os.path.isfile(filename_hash):
                with open(filename_hash, "wb") as file:

                    response = megacrypter2debrid(page_url)

                    if not response:
                        return [["NEI DEBRID: revisa los datos de tu cuenta auxiliar de MEGA", ""]]

                    page_url = response[0]

                    urls = AD_get_video_url(page_url)

                    pickle.dump(urls, file)
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
           
                if urls==None or check_debrid_urls(urls):
                    os.remove(filename_hash)

            if os.path.isfile(filename_hash):
                with open(filename_hash, "wb") as file:
                    urls = AD_get_video_url(page_url)
                    pickle.dump(urls, file)

        return urls

    page_url = page_url.replace('/embed#', '/#')
    logger.info("(page_url='%s')" % page_url)
    video_urls = []

    for f in files:
        media_url = f["url"]
        video_urls.append([scrapertools.get_filename_from_url(media_url)[-4:] + " [mega]", media_url])

    return video_urls

def proxy_run():
    logger.info(time.asctime(), "NEI DEBRID PROXY SERVER Starts - %s:%s" % (hostName, hostPort))
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
    headers["Authorization"] = "Bearer %s" % token_auth
    url = "https://api.real-debrid.com/rest/1.0/unrestrict/link"
    data = httptools.downloadpage(url, post=post_link, headers=list(headers.items())).json
    logger.error(data)

    check = config.get_setting("secret", server="realdebrid")
    #Se ha usado la autentificación por urlresolver (Bad Idea)
    if "error" in data and data["error"] == "bad_token" and not check:
        token_auth = RD_authentication()
        headers["Authorization"] = "Bearer %s" % token_auth
        data = httptools.downloadpage(url, post=post_link, headers=list(headers.items())).json

    # Si el token es erróneo o ha caducado, se solicita uno nuevo
    elif "error" in data and data["error"] == "bad_token":
        
        debrid_id = config.get_setting("id", server="realdebrid")
        secret = config.get_setting("secret", server="realdebrid")
        refresh = config.get_setting("refresh", server="realdebrid")

        post_token = urllib.parse.urlencode({"client_id": debrid_id, "client_secret": secret, "code": refresh,
                                       "grant_type": "http://oauth.net/grant_type/device/1.0"})
        renew_token = httptools.downloadpage("https://api.real-debrid.com/oauth/v2/token", post=post_token,
                                                headers=list(headers.items())).json
        if not "error" in renew_token:
            token_auth = renew_token["access_token"]
            config.set_setting("token", token_auth, server="realdebrid")
            headers["Authorization"] = "Bearer %s" % token_auth
            data = httptools.downloadpage(url, post=post_link, headers=list(headers.items())).json
        else:
            token_auth = RD_authentication()
            headers["Authorization"] = "Bearer %s" % token_auth
            data = httptools.downloadpage(url, post=post_link, headers=list(headers.items())).json
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
            itemlist.append([title, 'http://localhost:'+str(hostPort)+'/proxy/'+urllib.parse.quote(video_url)])
    else:
        if not PY3:
            video_url = data["download"].encode("utf-8")
        else:
            video_url = data["download"]
        title = video_url.rsplit(".", 1)[1] + " [realdebrid]"
        itemlist.append([title, 'http://localhost:'+str(hostPort)+'/proxy/'+urllib.parse.quote(video_url)])

    return itemlist


def RD_authentication():
    logger.info()
    try:
        client_id = "YTWNFBIJEEBP6"

        # Se solicita url y código de verificación para conceder permiso a la app
        url = "http://api.real-debrid.com/oauth/v2/device/code?client_id=%s&new_credentials=yes" % (client_id)
        data = httptools.downloadpage(url, headers=list(headers.items())).json
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
                data = httptools.downloadpage(url, headers=list(headers.items())).json
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
                                         headers=list(headers.items())).json

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
    #page_url = correct_url(page_url)
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
    url = "%slink/unlock?agent=%s&apikey=%s&link=%s" % (AD_API, agent_id, api_key, page_url)
    
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


# def correct_url(url):
#     if "uptostream.com" in url:
#         url = url.replace("uptostream.com/iframe/", "uptobox.com/")
#     return url

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
        url = "%spin/get?agent=%s" % (AD_API, agent_id)
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

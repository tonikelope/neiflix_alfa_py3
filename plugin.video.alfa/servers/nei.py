# -*- coding: utf-8 -*-

# Versión modificada del conector de MEGA para Noestasinvitado.com
# Soporte (experimental) para usar MegaCrypter con RealDebrid 
# Incluye proxy para parchear al vuelo cabeceras Content-Range defectuosas aleatorias de realdebrid y poder saltar en el vídeo hacia delante/atrás


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

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:65.0) Gecko/20100101 Firefox/65.0'}

files = None

hostName = "localhost"

hostPort = int(config.get_setting("neiflix_realdebrid_proxy_port", "neiflix").strip())

file_size = None

NEIFLIX_REALDEBRID = config.get_setting("neiflix_realdebrid", "neiflix")

class DebridProxy(BaseHTTPRequestHandler):

    def do_HEAD(self):

        if self.path.startswith('/isalive'):
            
            self.send_response(200, "OK")

            self.end_headers()

        else:

            global file_size

            file_size = None

            url = urllib.parse.unquote(re.sub(r'^.*?/proxy/', '', self.path))

            print(url)

            request_headers={}

            for h in self.headers:
                if h != 'Host':
                    request_headers[h]=self.headers[h]
                    print('do_HEAD HEADER '+h+' '+self.headers[h])

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
                print('GH '+h+' '+good_headers[h])

            self.end_headers()

            chunk = response.read(8192)
            
            try:
                while chunk:
                    self.wfile.write(chunk)
                    chunk = response.read(8192)
            except:
                pass


    def do_GET(self):
            
        if self.path.startswith('/isalive'):
            
            self.send_response(200, "OK")

            self.end_headers()

        else:

            global file_size

            url = urllib.parse.unquote(re.sub(r'^.*?/proxy/', '', self.path))

            print(url)

            request_headers={}

            for h in self.headers:
                if h != 'Host':
                    request_headers[h]=self.headers[h]
                    print('do_GET HEADER '+h+' '+self.headers[h])

            request = urllib.request.Request(url, headers=request_headers)
            
            response = urllib.request.urlopen(request)
            
            headers = response.getheaders()
            
            self.send_response(response.status)

            good_headers={}

            size=0

            for header in headers:

                if header[0] == 'Content-Length':
                    size = header[1]
                    good_headers[header[0]]=header[1]
                elif header[0] == 'Content-Range':
                    inicio = re.sub(r'^.*?bytes *?([0-9]+).+$', r'\1', header[1])

                    if inicio == '0' and file_size == None and self.headers['Range'] == 'bytes=0-':
                        file_size = size

                    final = int(inicio) + int(size) - 1

                    good_headers[header[0]]='bytes '+str(inicio)+'-'+str(final)+'/'+str(file_size)
                else:
                    good_headers[header[0]]=header[1]

            for h in good_headers:
                self.send_header(h, good_headers[h])
                print('GH '+h+' '+good_headers[h])

            self.end_headers()

            chunk = response.read(8192)
            
            try:
                while chunk:
                    self.wfile.write(chunk)
                    chunk = response.read(8192)
            except:
                pass

class ThreadingSimpleServer(ThreadingMixIn, HTTPServer):
    pass

try:
    proxy_server = ThreadingSimpleServer((hostName, hostPort), DebridProxy)
except:
    proxy_server = None



def megacrypter2debrid(link):

    email = base64.urlsafe_b64encode(config.get_setting("neiflix_realdebrid_mega_email", "neiflix").encode('utf-8'))
    
    password = base64.urlsafe_b64encode(config.get_setting("neiflix_realdebrid_mega_password", "neiflix").encode('utf-8'))

    megacrypter_link = link.split('#')

    link_data = re.sub(r'^.*?(!.+)$', r'\1', megacrypter_link[0])

    logger.info('https://noestasinvitado.com/megacrypter2debrid.php?l='+link_data+'&email='+email.decode('utf-8').replace('=','')+'&password='+password.decode('utf-8').replace('=',''))

    mega_link_response = httptools.downloadpage('https://noestasinvitado.com/megacrypter2debrid.php?l='+link_data+'&email='+email.decode('utf-8').replace('=','')+'&password='+password.decode('utf-8').replace('=',''))

    mega_link = re.sub(r'^.*?(http.+)$', r'\1', mega_link_response.data)

    return mega_link.strip() if 'httpERROR' not in mega_link else None


def test_video_exists(page_url):
    
    if NEIFLIX_REALDEBRID:
        return True, ""

    from megaserver import Client
    c = Client(url=page_url, is_playing_fnc=platformtools.is_playing)
    global files
    files = c.get_files()
    if isinstance(files, int):
        return False, "Error codigo %s" % str(files)

    return True, ""


def get_video_url(page_url, premium=False, user="", password="", video_password=""):

    logger.info(page_url)

    if NEIFLIX_REALDEBRID:
    
        if 'megacrypter.noestasinvitado' in page_url:
            page_url = megacrypter2debrid(page_url)

            if not page_url:
                return [["NEI REAL-DEBRID: revisa los datos de tu cuenta auxiliar de MEGA", ""]]

        return RD_get_video_url(page_url)

    page_url = page_url.replace('/embed#', '/#')
    logger.info("(page_url='%s')" % page_url)
    video_urls = []

    for f in files:
        media_url = f["url"]
        video_urls.append([scrapertools.get_filename_from_url(media_url)[-4:] + " [mega]", media_url])

    return video_urls

def proxy_run():
    global proxy_server, hostName, hostPort
    logger.info(time.asctime(), "NEI DEBRID PROXY SERVER Starts - %s:%s" % (hostName, hostPort))
    proxy_server.serve_forever()

def start_proxy():
    t = threading.Thread(target=proxy_run)
    t.setDaemon(True)
    t.start()

# Returns an array of possible video url's from the page_url
def RD_get_video_url(page_url, premium=False, user="", password="", video_password=""):

    global proxy_server

    if proxy_server:
        start_proxy()

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
    global hostPort
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


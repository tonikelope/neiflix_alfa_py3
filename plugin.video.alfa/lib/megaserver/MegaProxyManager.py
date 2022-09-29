# -*- coding: utf-8 -*-
# tonikelope para NEIFLIX

import urllib.request, urllib.error, urllib.parse
import collections
import time
import threading
from platformcode import config,logger

PROXY_LIST_URL='https://raw.githubusercontent.com/tonikelope/megabasterd/proxy_list/proxy.txt'
PROXY_BLOCK_TIME = 180

def synchronized_with_attr(lock_name):
    
    def decorator(method):
        
        def synced_method(self, *args, **kws):
            lock = getattr(self, lock_name)
            with lock:
                return method(self, *args, **kws)
                
        return synced_method

    return decorator

class MegaProxyManager():

    def __init__(self):
        self.proxy_list=collections.OrderedDict()
        self.proxy_list_url=PROXY_LIST_URL
        self.lock = threading.RLock()

        custom_proxy_list = config.get_setting("neiflix_mega_proxy_list", "neiflix")

        if custom_proxy_list:
            self.proxy_list_url=custom_proxy_list
            logger.info("USANDO LISTA DE PROXYS PARA MEGA: "+self.proxy_list_url)

    @synchronized_with_attr("lock")
    def refresh_proxy_list(self):

        self.proxy_list.clear()
        
        try:
            logger.info(self.proxy_list_url)

            req = urllib.request.Request(self.proxy_list_url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.101 Safari/537.36"})

            proxy_data = urllib.request.urlopen(req).read().decode("utf-8")

            for p in proxy_data.split('\n'):
                self.proxy_list[p]=time.time()
                logger.info(p)

        except Exception as ex:
            logger.info(ex)
            logger.info("ERROR "+self.proxy_list_url)

    @synchronized_with_attr("lock")
    def get_next_proxy(self):

        if len(self.proxy_list) == 0:
            self.refresh_proxy_list()
            return next(iter(self.proxy_list.items()))[0] if len(self.proxy_list) > 0 else None
        else:
            for proxy, timestamp in self.proxy_list.items():
                if time.time() > timestamp:
                    return proxy

            self.refresh_proxy_list()

            return next(iter(self.proxy_list.items()))[0] if len(self.proxy_list) > 0 else None

    @synchronized_with_attr("lock")
    def block_proxy(self,proxy):

        if proxy in self.proxy_list:
            self.proxy_list[proxy] = time.time() + PROXY_BLOCK_TIME

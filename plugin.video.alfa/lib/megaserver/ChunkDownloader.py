# -*- coding: utf-8 -*-
# tonikelope MULTI-THREAD para NEIFLIX

import threading
import urllib.request, urllib.error, urllib.parse
from . import Chunk
import time
from platformcode import logger

MAX_CHUNK_BUFFER_SIZE = 20
BLOCK_SIZE = 16*1024
SOCKET_TIMEOUT = 15
FORCE_PROXY_MODE = False

class ChunkDownloader():

	def __init__(self, id, cursor):
		self.id = id
		self.cursor = cursor
		self.chunk_writer = cursor.chunk_writer
		self.proxy_manager = cursor.proxy_manager
		self.url = self.chunk_writer.cursor._file.url
		self.proxy = None
		self.exit = False


	def run(self):

		logger.info("ChunkDownloader [%d] HELLO!" % self.id)

		error = False

		error509 = False

		offset = -1

		while not self.chunk_writer.exit and not self.exit:

			try:

				while not self.chunk_writer.exit and not self.exit and len(self.chunk_writer.queue) >= MAX_CHUNK_BUFFER_SIZE:
					logger.info("ChunkDownloader %d me duermo porque la cola está llena!" % self.id)
					with self.chunk_writer.cv_queue_full:
						self.chunk_writer.cv_queue_full.wait(1)

				if not self.chunk_writer.exit and not self.exit:

					if error509 or FORCE_PROXY_MODE:

						if self.proxy and error509:
							logger.info("ChunkDownloader[%d] bloqueando proxy %s" % (self.id, self.proxy))
							self.proxy_manager.block_proxy(self.proxy)

						self.proxy = self.proxy_manager.get_fastest_proxy()

					if offset<0 or not error:
						offset = self.chunk_writer.nextOffset()

					error = False

					error509 = False

					if offset >= 0:

						chunk = Chunk.Chunk(offset, self.chunk_writer.calculateChunkSize(offset))

						logger.info("ChunkDownloader[%d] leyendo CHUNK %d" % (self.id, offset))

						try:

							logger.info("ChunkDownloader[%d] leyendo %s" % (self.id, self.url+('/%d-%d' % (int(offset), int(offset)+chunk.size-1))))

							req = urllib.request.Request(self.url+('/%d-%d' % (int(offset), int(offset)+chunk.size-1)))

							if self.proxy:
								req.set_proxy(self.proxy, 'http')
								logger.info("ChunkDownloader[%d] usando proxy %s" % (self.id, self.proxy))

							connection = urllib.request.urlopen(req, timeout=SOCKET_TIMEOUT)

							bytes_read = 0

							chunk.data = bytearray()

							while bytes_read < chunk.size and not self.chunk_writer.exit and not self.exit:
								to_read = min(BLOCK_SIZE, chunk.size - bytes_read)

								try:
									chunk.data+=connection.read(to_read)
									bytes_read+=to_read
								except Exception:
									pass

							if not self.chunk_writer.exit and not self.exit:

								if len(chunk.data) != chunk.size:
									error = True
								else:
									self.chunk_writer.queue[chunk.offset]=chunk
									with self.chunk_writer.cv_new_element:
										self.chunk_writer.cv_new_element.notifyAll()

						except urllib.error.HTTPError as err:
							logger.info("ChunkDownloader[%d] HTTP ERROR %d" % (self.id, err.code))

							error = True

							if offset >= 0:
								self.chunk_writer.offset_rejected.put(offset)
								offset=-1

							if err.code == 509:
								error509 = True
							elif err.code == 403:
								self.url = self.chunk_writer.cursor._file.refreshMegaDownloadUrl()

						except urllib.error.URLError as err:
							logger.info("ChunkDownloader[%d] URL ERROR %d" % (self.id, err.reason))

							error = True

							if offset >= 0:
								self.chunk_writer.offset_rejected.put(offset)
								offset=-1

							if err.code == 509:
								error509 = True
							elif err.code == 403:
								self.url = self.chunk_writer.cursor._file.refreshMegaDownloadUrl()
								
						except urllib2.socket.timeout:
							logger.info("ChunkDownloader[%d] socket timeout" % self.id)

							error = True

							if offset >= 0:
								self.chunk_writer.offset_rejected.put(offset)
								offset=-1

							if not self.proxy:
								self.url = self.chunk_writer.cursor._file.refreshMegaDownloadUrl()
					else:
						logger.info("ChunkDownloader[%d] END OFFSET" % self.id)
						self.exit = True

			except Exception as e:
				logger.info("ChunkDownloader[%d] %s" % (self.id, str(e)))
				
				if offset >= 0:
					self.chunk_writer.offset_rejected.put(offset)
				
				self.exit = True

		logger.info("ChunkDownloader [%d] BYE BYE" % self.id)


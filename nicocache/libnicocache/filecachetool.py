# -*- coding: utf-8 -
import logging as _logging

logger = _logging.getLogger(__name__)


class CachingReader(object):

    def __init__(self, cachefile, originalfile, length,
                 complete_cache=False, logger=logger):
        """
        cachefile must be opened read/write able mode.
        if complete_cache: when CachingReader.close() called, complete cache.
        length is length of whole data.
        """
        self._cachefile = cachefile
        self._originalfile = originalfile
        self._complete_cache = complete_cache

        self._logger = logger

        self._read_from_cachefile = True
        self._length = length
        self._left_size = length
        self._closed = False

    def read(self, size=-1):
        # jp!!!返るデータの大きさがsizeであることは(もしくはEOFまで読み込んでいることは)下位のread()関数が保証している(多分)
        if self._left_size == 0:
            self._logger.debug("CachingReader.read(): left size is 0. EOF")
            return ""

        if size < 0:
            self._logger.debug("CachingReader.read(): read all.")
            return self.read(self._left_size)

        else:
            self._logger.debug(
                "CachingReader.read(): start read(). left size is %d byte", self._left_size)
            self._logger.debug(
                "CachingReader.read(): requested size to read is %d byte", size)
            data = ''

            if self._read_from_cachefile:
                data_from_cache = self._cachefile.read(size)
                # jp!!!"このメソッドは、 size バイトに可能な限り近くデータを取得するために、背後の C 関数 fread() を 1 度以上呼び出すかもしれないので注意してください。"
                # とライブラリリファレンスにあるので、len(data_from_cache) == sizeは保証されている
                self._logger.debug(
                    "CachingReader.read(): read %d byte from cache file", len(data_from_cache))
                data = data_from_cache

                if len(data_from_cache) < size:
                    # jp!!!キャッシュのデータでは足りないので、残りは下でオリジナルから読み出す
                    self._read_from_cachefile = False
                    size -= len(data_from_cache)

            if not self._read_from_cachefile:
                data_from_orig = self._originalfile.read(size)
                self._logger.debug(
                    "CachingReader.read(): read %d byte from original file", len(data_from_orig))
                self._cachefile.write(data_from_orig)
                self._logger.debug(
                    "CachingReader.read(): write %d byte to cache file", len(data_from_orig))

                if len(data) > 0:
                    # jp!!!すでにcachefileから読まれたデータがあるとき
                    data = b''.join((data, data_from_orig))
                else:
                    data = data_from_orig

            self._left_size -= len(data)
            self._logger.debug("CachingReader.read(): read %d byte", len(data))
            self._logger.debug(
                "CachingReader.read(): end read(). left size is %d byte", self._left_size)
            return data

    @property
    def closed(self):
        return self._closed

    def close(self):
        if self._complete_cache:
            self._logger.debug(
                "CachingReader.close(): start completing cache. left size is %d byte. seek to end of cache file", self._left_size)
            self._cachefile.seek(0, 2)
            self._left_size = self._length - self._cachefile.tell()
            self._read_from_cachefile = False
            self._logger.debug(
                "CachingReader.close(): left size is %d byte (only original file). start appending to cache file", self._left_size)

            # read(self._left_size) is not good when self._left_size is too
            # large
            while True:
                data = self.read(8192)
                if len(data) < 8192:
                    break
            self._logger.debug(
                "CachingReader.close(): left size is %d byte. end completing cache.", self._left_size)
        self._cachefile.close()
        self._originalfile.close()  # fixme!!!例外安全じゃない
        self._cachefile = None
        self._originalfile = None
        self._closed = True

    def __del__(self):
        try:
            if not self._closed:
                try:
                    self._logger.error(
                        "CachingReader was closed by GC! Resource leaking!")
                    self._logger.error(object.__repr__(self))
                except:
                    pass

                try:
                    self.close()
                except:
                    pass
        except:
            pass

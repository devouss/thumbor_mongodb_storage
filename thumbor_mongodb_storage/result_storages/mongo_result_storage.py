# -*- coding: utf-8 -*-
# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license
# Copyright (c) 2019 HZ HZ@blackhand.org

import time
import urllib
from datetime import datetime, timedelta
from io import StringIO
from pymongo import MongoClient
from thumbor.result_storages import BaseStorage
from thumbor.utils import logger
import bson
import re
from bson.binary import Binary

class Storage(BaseStorage):

    def __conn__(self):
        password = urllib.quote_plus(self.context.config.MONGO_RESULT_STORAGE_SERVER_PASSWORD)
        user = self.context.config.MONGO_RESULT_STORAGE_SERVER_USER
        if not self.context.config.MONGO_RESULT_STORAGE_SERVER_REPLICASET:
          uri = 'mongodb://'+ user +':' + password + '@' + self.context.config.MONGO_RESULT_STORAGE_SERVER_HOST + '/?authSource=' + self.context.config.MONGO_RESULT_STORAGE_SERVER_DB
        else:
          uri = 'mongodb://'+ user +':' + password + '@' + self.context.config.MONGO_RESULT_STORAGE_SERVER_HOST + '/?authSource=' + self.context.config.MONGO_RESULT_STORAGE_SERVER_DB + "&replicaSet=" + self.context.config.MONGO_RESULT_STORAGE_SERVER_REPLICASET + "&readPreference=" + self.context.config.MONGO_RESULT_STORAGE_SERVER_READ_PREFERENCE + "&maxStalenessSeconds=120"
        client = MongoClient(uri)
        db = client[self.context.config.MONGO_RESULT_STORAGE_SERVER_DB]
        storage = db[self.context.config.MONGO_RESULT_STORAGE_SERVER_COLLECTION]
        return client, db, storage

    def get_max_age(self):
        '''Return the TTL of the current request.
        :returns: The TTL value for the current request.
        :rtype: int
        '''

        default_ttl = self.context.config.RESULT_STORAGE_EXPIRATION_SECONDS
        if self.context.request.max_age == 0:
            return self.context.request.max_age

        return default_ttl


    def get_key_from_request(self):
        '''Return a key for the current request url.
        :return: The storage key for the current url
        :rettype: string
        '''
        path = "result:%s" % self.context.request.url

        #if self.is_auto_webp():
        #    path += '/webp'
        return path


    def put(self, bytes):
        connection, db, storage = self.__conn__()
        key = self.get_key_from_request()
        max_age = self.get_max_age()
        result_ttl = self.get_max_age()
        ref_img = re.findall(r'/[a-zA-Z0-9]{24}(?:$|/)', key)
        if ref_img:
            ref_img2 = ref_img[0].replace('/','')
        else:
            ref_img2 = 'undef'
        doc = {
            'path': key,
            'created_at': datetime.utcnow(),
            'data': Binary(bytes),
            'ref_id': ref_img2
            }
        doc_cpm = dict(doc)

        if result_ttl > 0:
                ref = datetime.utcnow() + timedelta(
                    seconds=result_ttl
                )
                doc_cpm['expire'] = ref

        storage.insert(doc_cpm)

        return key



    def get(self):
        '''Get the item .'''
        connection, db, storage = self.__conn__()
        key = self.get_key_from_request()
        result = storage.find_one({"path": key})

        if not result: # or self.__is_expired(result):
            return None
        if result and  self.__is_expired(result):
            ttl = result.get('path')
            self.remove(ttl)
            return None

        tosend = result['data']
        return tosend


    def remove(self, path):
        #if not self.exists(path):
        #    return

        connection, db, storage = self.__conn__()
        try:        
            storage.remove({'path': path})
        except:
            return


    def __is_expired(self, result):
        timediff = datetime.utcnow() - result.get('created_at')
        return timediff > timedelta(seconds=self.context.config.RESULT_STORAGE_EXPIRATION_SECONDS)
        '''future => db.log_events.createIndex( { "createdAt": 1 }, { expireAfterSeconds: 3600 } )
        db.runCommand( { collMod: <collection or view>, <option1>: <value1>, <option2>: <value2> ... } )
        {keyPattern: <index_spec> || name: <index_name>, expireAfterSeconds: <seconds> }       
        {getParameter:1, expireAfterSeconds: 1}      
        '''
        




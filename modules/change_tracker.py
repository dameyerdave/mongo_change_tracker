import sys
import pymongo
import threading
import time
import traceback
import hashlib
from os.path import join
from os import environ
from pathlib import Path

from models.change import Change
from friendlylog import colored_logger as log
import re
from queue import Queue
from models.helper import flatten_json


class ChangeTracker:
    CHANGES_TIMEOUT = 5
    BULK_SIZE = 100000
    # TODO: change to 4
    NUM_FLUSHERS = 8

    class __ChangeTracker(threading.Thread):

        class Flusher(threading.Thread):
            def __init__(self, id, changesQ):
                super().__init__(daemon=True)
                self.id = id
                self.__status = 'idle'
                self.changesQ = changesQ

            def __handleQ(self, empty=False):
                # log.debug(f"[{self.id}] Handling change queue...")
                if not self.changesQ.empty():
                    changes = []
                    size = 0
                    while not self.changesQ.empty():
                        changes += self.changesQ.get()
                        if not empty:
                            if size > ChangeTracker.BULK_SIZE:
                                break
                        size += 1
                    self.__status = 'flushing'
                    log.info(f"[{self.id}] Flushing {len(changes)} changes...")
                    Change.objects.insert(changes)
                    log.info(f"[{self.id}] Flushed {len(changes)} changes.")
                    self.__status = 'idle'

            def run(self):
                try:
                    log.debug(f"[{self.id}] Flusher started.")
                    self.running = True
                    while(self.running):
                        self.__handleQ()
                        time.sleep(ChangeTracker.CHANGES_TIMEOUT)
                    log.debug(f"[{self.id}] Flusher stopped.")
                except Exception as ex:
                    log.error(ex)
                    traceback.print_exc(file=sys.stdout)

            def kill(self):
                self.running = False
                self.__status = 'dieing'
                log.info(f"[{self.id}] Waiting for flush...")
                self.join()
                self.__handleQ(True)
                log.info(f"[{self.id}] Final flush done.")
                self.__status = 'dead'

            def get_status(self):
                return self.__status

            def id(self):
                return self.id

        def __init__(self, mongo_uri, collections, fields):
            super().__init__(daemon=True)
            self.mongo_uri = mongo_uri
            self.collections = collections
            self.fields = fields
            self.changesQ = Queue()
            self.flushers = [self.Flusher(i, self.changesQ)
                             for i in range(ChangeTracker.NUM_FLUSHERS)]
            self.__status = 'idle'

        def kill(self):
            self.running = False
            self.__status = 'dieing'
            for flusher in self.flushers:
                flusher.kill()
            self.__status = 'dead'

        def get_status(self):
            status = {}
            status['status'] = self.__status
            status['queue_size'] = self.changesQ.qsize()
            status['flushers'] = {}
            for flusher in self.flushers:
                status['flushers'][flusher.id] = flusher.get_status()
            return status

        def __match(self, field):
            for regex in self.fields:
                if re.match(regex, field):
                    return True
            return False

        def __add(self, change):
            _changes = Change.from_change(change)
            self.changesQ.put(_changes)

        def run(self):
            if self.mongo_uri is None:
                return
            db = pymongo.MongoClient(self.mongo_uri).get_database()
            pipeline = [
                {
                    "$match": {
                        "ns.coll": {"$in": self.collections}
                    }
                }, {
                    "$set": {
                        "timestamp": "$clusterTime",
                        "user": f"$fullDocument.{environ.get('CT_USER_FIELD')}",
                        "db": "$ns.db",
                        "coll": "$ns.coll",
                        "doc_id": "$fullDocument._id",
                        "type": "$operationType",
                        "updatedFields": "$updateDescription.updatedFields",
                        "removedFields": "$updateDescription.removedFields",
                        "fullDocument": "$fullDocument"
                    }
                }, {
                    "$project": {
                        "timestamp": 1,
                        "user": 1,
                        "db": 1,
                        "coll": 1,
                        "type": 1,
                        "doc_id": 1,
                        "updatedFields": 1,
                        "removedFields": 1,
                        "fullDocument": 1
                    }
                }
            ]
            resume_token = None
            self.running = True
            for flusher in self.flushers:
                flusher.start()
            self.__status = 'running'
            while self.running:
                try:
                    with db.watch(pipeline, 'updateLookup', resume_after=resume_token) as stream:
                        if not self.running:
                            log.debug("Closeing stream...")
                            stream.close()
                        for change in stream:
                            if not self.running:
                                break
                            createDoc = False
                            ignoredFields = []

                            # General changes
                            change['timestamp'] = change['timestamp'].as_datetime().strftime(
                                '%Y-%m-%dT%H:%M:%S.%f')
                            if 'user' not in change:
                                change['user'] = 'unknown'
                            else:
                                change['user'] = change['user']

                            # Type specific changes
                            if change['type'] == 'insert':
                                change['fullDocument'] = change['fullDocument']
                                createDoc = True
                                if environ.get('CT_DEBUG'):
                                    log.debug(
                                        "{timestamp}: user={user} db={db} coll={coll} type={type} doc_id={doc_id}".format(**change))
                            elif change['type'] == 'update':
                                updatedFields = {}
                                removedFields = []
                                for field, value in change['updatedFields'].items():
                                    if self.__match(field):
                                        # json_value = json.loads(value)
                                        if isinstance(value, (dict, list)):
                                            flat_value = flatten_json(value)
                                            for _field, _value in flat_value.items():
                                                updatedFields[f"{field}.{_field}"] = _value
                                        else:
                                            updatedFields[field] = value
                                        createDoc = True
                                    else:
                                        ignoredFields.append(field)
                                for field in change['removedFields']:
                                    if self.__match(field):
                                        removedFields.append(field)
                                        createDoc = True
                                    else:
                                        ignoredFields.append(field)

                                change['updatedFields'] = updatedFields
                                change['removedFields'] = removedFields
                                del change['fullDocument']
                                if environ.get('CT_DEBUG'):
                                    log_msg = "{timestamp}: user={user} db={db} coll={coll} type={type} doc_id={doc_id} updatedFields={updatedFields} removedFields={removedFields}".format(
                                        **change)
                                    log_msg = (
                                        log_msg[:500] + '...') if len(log_msg) > 500 else log_msg
                                    log.debug(log_msg)

                            # If we need to create a change entry
                            if createDoc:
                                self.__add(change)
                            else:
                                if change['type'] in ['insert', 'update']:
                                    log.debug("Not tracking change for: {timestamp}: user={user} db={db} coll={coll} type={type} doc_id={doc_id} ignoredFields={ignoredFields}".format(
                                        **change, ignoredFields=ignoredFields))
                                else:
                                    log.warning(
                                        "Not tracking change for: {0}".format(change))
                            resume_token = stream.resume_token
                except Exception as ex:
                    self.__status = 'error'
                    log.error(ex)
                    traceback.print_exc(file=sys.stdout)
                    pass

    trackers = {}

    @staticmethod
    def __hide_pw(mongo_uri):
        REDACT = re.compile(r'([^:]+:\/\/[^:]+:)([^@]+)(@.*)')
        return REDACT.sub(r'\1<hidden>\3', mongo_uri)

    def __new__(cls, mongo_uri, collections, fields):
        hash = hashlib.md5(
            (mongo_uri + ''.join(collections)).encode('utf-8')).hexdigest()
        lockFile = join('temp', hash + '.lock')
        Path(lockFile).mkdir(parents=True, exist_ok=True)
        if not Path(lockFile).is_file():
            Path(lockFile).touch()
            if hash not in cls.trackers:
                log.info(
                    f"Start change tracker '{hash}' for {cls.__hide_pw(mongo_uri)}, collections=[{', '.join(collections)}] fields=[{', '.join(fields)}]")
                cls.trackers[hash] = cls.__ChangeTracker(
                    mongo_uri, collections, fields)
            return cls.trackers[hash]
        else:
            log.warn(
                f"Change tracker '{hash}'' seams to be already started for {cls.__hide_pw(mongo_uri)}, collections=[{', '.join(collections)}] fields=[{', '.join(fields)}]")
            return cls.__ChangeTracker(None, None)

    @classmethod
    def destroy(cls):
        for hash in cls.trackers:
            log.info(
                f"Killing tracker {hash}.")
            cls.trackers[hash].kill()
            lockFile = join('temp', hash + '.lock')
            if Path(lockFile).is_file():
                Path(lockFile).unlink()

    @classmethod
    def get_status(cls):
        status = {}
        for hash in cls.trackers:
            status[hash] = cls.trackers[hash].get_status()
        return status

import sys
import pymongo
import threading
import traceback
import hashlib
from os.path import join
from os import environ
from pathlib import Path
from models.change import Change
from friendlylog import colored_logger as log


class ChangeTracker:
    class __ChangeTracker(threading.Thread):
        def __init__(self, mongo_uri, collections):
            super(ChangeTracker.__ChangeTracker, self).__init__(daemon=True)
            self.mongo_uri = mongo_uri
            self.collections = collections

        def kill(self):
            self.running = False

        def run(self):
            if self.mongo_uri is None:
                return

            self.running = True
            db = pymongo.MongoClient(self.mongo_uri)
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
            while self.running:
                try:
                    with db.watch(pipeline, 'updateLookup', resume_after=resume_token) as stream:
                        for change in stream:
                            change['timestamp'] = change['timestamp'].as_datetime().strftime(
                                    '%Y-%m-%dT%H:%M:%S')
                            if 'user' not in change:
                                change['user'] = 'unknown'
                            if environ.get('CT_DEBUG'):        
                              if change['type'] == 'update':
                                log.debug("{timestamp}: user={user} db={db} coll={coll} type={type} doc_id={doc_id} updatedFields={updatedFields} removedFields={removedFields}".format(**change) )
                              else:
                                log.debug("{timestamp}: user={user} db={db} coll={coll} type={type} doc_id={doc_id}".format(**change) )
                            Change.from_change(change)
                            resume_token = stream.resume_token
                except Exception as ex:
                    log.error('!!! ChangeTracker Error !!!')
                    log.error(ex)
                    traceback.print_exc(file=sys.stdout)
                    pass

    trackers = {}

    def __new__(cls, mongo_uri, collections):
        hash = hashlib.md5(
            (mongo_uri + ''.join(collections)).encode('utf-8')).hexdigest()
        lockFile = join('temp', hash + '.lock')
        Path(lockFile).mkdir(parents=True, exist_ok=True)
        if not Path(lockFile).is_file():
            Path(lockFile).touch()
            if hash not in cls.trackers:
                log.info(
                    f"Start change tracker '{hash}' for {mongo_uri}, {', '.join(collections)}")
                cls.trackers[hash] = cls.__ChangeTracker(
                    mongo_uri, collections)
            return cls.trackers[hash]
        else:
            log.warn(
                f"Change tracker '{hash}'' seams to be already started for {mongo_uri}, {', '.join(collections)}")
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

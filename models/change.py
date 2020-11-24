from os import environ
from mongoengine import Document, StringField, DateTimeField
from datetime import timezone
import hashlib


class Change(Document):
    change_key = StringField(primary_key=True)
    timestamp = DateTimeField()
    user = StringField(default='unknown')
    db = StringField()
    coll = StringField()
    doc_id = StringField()
    type = StringField()
    field = StringField()
    value = StringField()

    meta = {
        'collection': environ.get('CT_COLLECTION'),
        'indexes': [
            'user',
            'db',
            'coll',
            'doc_id',
            'type',
            'field'
        ]
    }

    ignore_fields = ['modified_ts', 'created_ts', 'last_modify_user']

    @staticmethod
    def flatten_json(y):
        out = {}

        def flatten(x, name=''):
            if type(x) is dict:
                for a in x:
                    flatten(x[a], name + a + '.')
            elif type(x) is list:
                i = 0
                for a in x:
                    flatten(a, name + str(i) + '.')
                    i += 1
            else:
                out[name[:-1]] = x

        flatten(y)
        return out

    @classmethod
    def from_change(cls, _change):
        if _change['type'] == 'insert':
            if 'fullDocument' in _change:
                flattenFullDocument = Change.flatten_json(
                    _change['fullDocument'])
                changes = []
                for field, value in flattenFullDocument.items():
                    if field not in cls.ignore_fields:
                        changes.append(
                            cls(
                                # .replace(tzinfo=timezone.utc).astimezone(tz=None)
                                timestamp=_change['timestamp'],
                                user=_change['user'],
                                db=_change['db'],
                                coll=_change['coll'],
                                doc_id=_change['doc_id'],
                                type=_change['type'],
                                field=field,
                                value=str(value)
                            )
                        )
                if len(changes) > 0:
                    Change.objects.insert(changes)
        elif _change['type'] == 'update':
            if 'updatedFields' in _change:
                changes = []
                for field, value in _change['updatedFields'].items():
                    if field not in cls.ignore_fields:
                        changes.append(
                            cls(
                                timestamp=_change['timestamp'],
                                user=_change['user'],
                                db=_change['db'],
                                coll=_change['coll'],
                                doc_id=_change['doc_id'],
                                type=_change['type'],
                                field=field,
                                value=str(value)
                            )
                        )
                if len(changes) > 0:
                    Change.objects.insert(changes)
            if 'removedFields' in _change:
                changes = []
                for field in _change['removedFields']:
                    if field not in cls.ignore_fields:
                        changes.append(
                            cls(
                                timestamp=_change['timestamp'],
                                user=_change['user'],
                                db=_change['db'],
                                coll=_change['coll'],
                                doc_id=_change['doc_id'],
                                type=_change['type'],
                                field=field,
                                value="N/A"
                            )
                        )
                if len(changes) > 0:
                    Change.objects.insert(changes)
        else:
            print('---change---')
            print(_change)
            print('---')

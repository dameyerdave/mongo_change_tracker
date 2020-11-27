from os import environ
import re
from mongoengine import Document, StringField, DateTimeField
from models.pipelines import Pipelines
from models.helper import flatten_json
from config.config import replacement_identifiers


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

    @staticmethod
    def evaluate_field(doc, field):
        parts = []
        fields = field.split('.')
        keys = field.split('.')
        for idx, key in enumerate(keys):
            if key.isnumeric():
                doc = doc[int(key)]
                identifier = re.sub(r'\.[0-9]+\.', '.X.', '.'.join(fields[:idx]))
                identifier2 = fields[idx - 1]
                print(identifier)
                print(identifier2)
                if identifier in replacement_identifiers and replacement_identifiers[identifier] in doc:
                    parts.append(doc[replacement_identifiers[identifier]])
                elif identifier2 in replacement_identifiers and replacement_identifiers[identifier2] in doc:
                    parts.append(doc[replacement_identifiers[identifier2]])
                else:
                    parts.append('X')
            else:
                doc = doc[key]
                parts.append(key)
        return '.'.join(parts)


    @classmethod
    def get_changes(cls, db, coll, doc_id):
        pipeline = Pipelines.CHANGES(db, coll, doc_id)
        changes = []
        ret = list(cls.objects.aggregate(pipeline, allowDiskUse=True))[0]
        initial_document = flatten_json(ret['initial_document'])
        for change in ret['changes']:
            changes.append({
                'timestamp': '',
                'field': cls.evaluate_field(ret['initial_document'], change['field']),
                'from': str(initial_document[change['field']]),
                'to': change['value']
            })
        return changes


    @classmethod
    def from_change(cls, _change):
        changes = []
        if _change['type'] == 'insert':
            if 'fullDocument' in _change:
                # for field, value in _change['fullDocument'].items():
                changes.append(
                        cls(
                            # .replace(tzinfo=timezone.utc).astimezone(tz=None)
                            timestamp=_change['timestamp'],
                            user=_change['user'],
                            db=_change['db'],
                            coll=_change['coll'],
                            doc_id=_change['doc_id'],
                            type=_change['type'],
                            field='fullDocument',
                            value=_change['fullDocument']
                        )
                    )
        elif _change['type'] == 'update':
            if 'updatedFields' in _change:
                for field, value in _change['updatedFields'].items():
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
                for field in _change['removedFields']:
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
        else:
            print('---change---')
            print(_change)
            print('---')
        return changes

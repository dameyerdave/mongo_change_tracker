import json
import re
from os import environ
from pprint import pprint

from dateutil.parser import parse
from mongoengine import DateTimeField, Document, StringField

from config.config import replacement_identifiers, value_replacements
from models.helper import flatten_json
from models.pipelines import Pipelines


class Change(Document):
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
            'timestamp',
            'user',
            'db',
            'coll',
            'doc_id',
            'type',
            'field',
            'value',
            (
                'db',
                'coll',
                'doc_id'
            ),
            (
                'db',
                'coll',
                'doc_id',
                'type',
                'field',
            )
        ]
    }

    def __str__(self):
        return self.to_json()

    @staticmethod
    def evaluate_field(doc, field):
        parts = []
        print(field)
        fields = field.split('.')
        keys = field.split('.')
        for idx, key in enumerate(keys):
            if key.isnumeric():
                doc = doc[int(key)]
                identifier = re.sub(
                    r'\.[0-9]+\.', '.X.', '.'.join(fields[:idx]))
                identifier2 = fields[idx - 1]
                if identifier in replacement_identifiers and replacement_identifiers[identifier] in doc:
                    parts.append(doc[replacement_identifiers[identifier]])
                elif identifier2 in replacement_identifiers and replacement_identifiers[identifier2] in doc:
                    parts.append(doc[replacement_identifiers[identifier2]])
                else:
                    parts.append('X')
            else:
                if key in doc:
                    doc = doc[key]
                    parts.append(key)
                else:
                    parts += keys[idx:]
                    pprint(parts)
                    break
        return '.'.join(parts)

    @staticmethod
    def evaluate_value(field, values):
        for value_replacement in value_replacements:
            if field.endswith(value_replacement):
                if isinstance(values, list):
                    for idx, value in enumerate(values):
                        if value in value_replacements[value_replacement]:
                            values[idx] = value_replacements[value_replacement][value]
                else:
                    if values in value_replacements[value_replacement]:
                        values = value_replacements[value_replacement][values]
        return values

    @classmethod
    def get_changes(cls, db, coll, doc_id, args):
        pipeline = Pipelines.CHANGES(db, coll, doc_id, args['filter'], args['sortBy'], (args['sortDesc'] == 'true'), int(
            args['perPage']) * (int(args['currentPage']) - 1), int(args['perPage']))

        print(pipeline)

        changes = []
        ret = list(cls.objects.aggregate(pipeline, allowDiskUse=True))[0]
        initial_document = flatten_json(ret['initial_document'])
        for change in ret['changes']:
            tos = []
            for idx, to in enumerate(cls.evaluate_value(change['field'], change['value'])):
                tos.append({
                    'timestamp': change['timestamp'][idx],
                    'user': change['user'][idx],
                    'to': to
                })
            changes.append({
                'last_timestamp': change['last_timestamp'],
                'last_user': change['last_user'],
                'field': cls.evaluate_field(ret['initial_document'], change['field']),
                'initial': cls.evaluate_value(change['field'], str(
                    initial_document[change['field']])) if change['field'] in initial_document else json.dumps(ret['initial_document'][change['field']]) if change['field'] in ret['initial_document'] else 'N/A',
                'to': tos
            })
        return {
            'count': ret['count'],
            'items': changes
        }

    @classmethod
    def from_change(cls, _change):
        changes = []
        if _change['type'] == 'insert':
            if 'fullDocument' in _change:
                changes.append(
                    cls(
                        timestamp=parse(_change['timestamp']),
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
                            timestamp=parse(_change['timestamp']),
                            user=_change['user'],
                            db=_change['db'],
                            coll=_change['coll'],
                            doc_id=_change['doc_id'],
                            type=_change['type'],
                            field=field,
                            value=str(value)
                        )
                    )
            if 'removedFields' in _change:
                for field in _change['removedFields']:
                    changes.append(
                        cls(
                            timestamp=parse(_change['timestamp']),
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

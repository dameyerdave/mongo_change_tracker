from os import environ
from mongoengine import Document, StringField, DateTimeField


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

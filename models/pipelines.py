
class Pipelines():

    @staticmethod
    def CHANGES(db, coll, doc_id):
        return [
            {
                '$facet': {
                    'initial_document': [
                        {
                            '$match': {
                                '$and': [
                                    {'db': db},
                                    {'coll': coll},
                                    {'doc_id': doc_id},
                                    {'type': 'insert'}
                                ]
                            }
                        }
                    ],
                    'changes': [
                        {
                            '$match': {
                                '$and': [
                                    {'db': db},
                                    {'coll': coll},
                                    {'doc_id': doc_id},
                                    {'type': 'update'}
                                ]
                            }
                        }, {
                            '$project': {
                                '_id': 0,
                                'user': 1,
                                'field': 1,
                                'value': 1
                            }
                        }
                    ]
                }
            }, {
                '$set': {
                    'initial_document': {'$arrayElemAt': ['$initial_document', 0]}
                }
            }, {
                '$set': {
                    'initial_document': '$initial_document.value'
                }
            }
        ]

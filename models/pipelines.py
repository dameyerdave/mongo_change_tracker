
class Pipelines():

    @staticmethod
    def CHANGES(db, coll, doc_id, filter, sortField, sortDesc, skip, limit):
        return [
            {
                "$match": {
                    "$and": [
                        {
                            "db": db
                        },
                        {
                            "coll": coll
                        },
                        {
                            "doc_id": doc_id
                        }
                    ]
                }
            },
            {
                "$facet": {
                    "initial_document": [
                        {
                            "$match": {
                                "type": "insert"
                            }
                        }
                    ],
                    "count": [
                        {
                            "$count": "totalDocs"
                        },
                    ],
                    "changes": [
                        {
                            "$match": {
                                "type": "update"
                            }
                        },
                        {
                            "$match": {
                                "$or": [
                                    {
                                        "field": {
                                            "$regex": filter,
                                            "$options": "i"
                                        }
                                    },
                                    {
                                        "value": {
                                            "$regex": filter,
                                            "$options": "i"
                                        }
                                    }
                                ]
                            }
                        },
                        {'$sort': {
                            'timestamp': -1}
                         },
                        {
                            "$project": {
                                "_id": 0,
                                "timestamp": 1,
                                "user": 1,
                                "field": 1,
                                "value": 1
                            }
                        },
                        {
                            "$group": {
                                "_id": "$field",
                                "value": {
                                    "$push": "$value"
                                },
                                "last_timestamp": {
                                    "$first": "$timestamp"
                                },
                                "timestamp": {
                                    "$push": "$timestamp"
                                },
                                "last_user": {
                                    "$first": "$user"
                                },
                                "user": {
                                    "$push": "$user"
                                }
                            }
                        },
                        {'$set': {'field': '$_id'}},
                        {'$sort': {sortField: -1 if sortDesc else 1}},
                        {'$skip': skip},
                        {'$limit': limit}
                    ]
                }
            },
            {
                "$set": {
                    "initial_document": {
                        "$arrayElemAt": [
                            "$initial_document",
                            0
                        ]
                    }
                }
            },
            {
                "$set": {
                    "initial_document": "$initial_document.value"
                }
            },
            {
                "$set": {
                    "count": {
                        "$cond": [
                            {
                                "$eq": [
                                    "$count",
                                    []
                                ]
                            },
                            0,
                            {
                                "$arrayElemAt": [
                                    "$count.totalDocs",
                                    0
                                ]
                            }
                        ]
                    }
                }
            }
        ]

#!/usr/bin/env python

import atexit
import logging
import traceback
from os import environ
from sys import exit, stdout

from dotenv import load_dotenv
from flask import request
from flask_api import FlaskAPI
from flask_cors import CORS
from flask_script import Manager, Server
from friendlylog import colored_logger as log
from mongoengine.queryset.visitor import Q
from tendo import singleton
from tendo.singleton import SingleInstanceException

from modules.decorators import queryset_respose
from flask_add_ons.logging import colorize_werkzeug

# Logging
logging.basicConfig(level=logging.DEBUG)
colorize_werkzeug()

__dev__ = environ['FLASK_ENV'] == 'development' or environ['DEBUG'] == 'True'
log.info(f"Development mode is '{__dev__}'")

# make sure only one instance is running
if not __dev__:
    try:
        me = singleton.SingleInstance()
    except SingleInstanceException:
        log.error("MCT already running!")
        exit(1)


app = FlaskAPI(__name__)
CORS(app)

app.config['DEFAULT_RENDERERS'] = [
    'flask_api.renderers.JSONRenderer',
    'flask_api.renderers.BrowsableAPIRenderer',
]


# API
@app.route('/status/', methods=['GET'])
def status():
    from modules.change_tracker import ChangeTracker
    return ChangeTracker.get_status()


@app.route('/changes/<db>/<coll>/', methods=['GET'])
@queryset_respose
def get_changes_coll(db, coll):
    from models.change import Change
    return Change.objects(Q(db=db) & Q(coll=coll))


@app.route('/changes/<db>/<coll>/<doc_id>/', methods=['GET'])
def get_changes_doc_id(db, coll, doc_id):
    from models.change import Change
    return Change.get_changes(db, coll, doc_id, request.args)


@app.route('/changes/<db>/<coll>/<doc_id>/<field>/', methods=['GET'])
@queryset_respose
def get_changes_field(db, coll, doc_id, field):
    from models.change import Change
    return Change.objects(Q(db=db) & Q(coll=coll) & Q(doc_id=doc_id) & Q(field=field))


# Initialization methods
def connectDb():
    from mongoengine import connect
    connect(
        db=environ.get('CT_DATABASE'),
        host=environ.get('CT_DATABASE_HOST'),
        port=int(environ.get('CT_DATABASE_PORT')),
        username=environ.get('CT_DATABASE_USERNAME'),
        password=environ.get('CT_DATABASE_PASSWORD'),
        authentication_source=environ.get('CT_AUTH_DATABASE'))


def __get_observe_database_uri():
    return 'mongodb://{CT_OBSERVE_USERNAME}:{CT_OBSERVE_PASSWORD}@{CT_OBSERVE_HOST}:{CT_OBSERVE_DATABASE_PORT}/{CT_OBSERVE_DATABASE}?authSource={CT_OBSERVE_AUTH_DATABASE}'.format(**environ)


def initChangeTracker():
    log.debug("Initialze change tracker")
    from modules.change_tracker import ChangeTracker
    changeTracker = ChangeTracker(__get_observe_database_uri(),
                                  [coll.strip() for coll in environ.get(
                                      'CT_COLLECTIONS').split(',')],
                                  [field.strip() for field in environ.get('CT_FIELDS').split(',')])
    changeTracker.start()


@atexit.register
def destroy():
    from modules.change_tracker import ChangeTracker
    ChangeTracker.destroy()


# Manager and commands
manager = Manager(app)
server = Server(host=environ.get('CT_HOSTNAME'), port=environ.get('CT_PORT'))
manager.add_command('runserver', server)


def init():
    try:
        load_dotenv(override=True)
        with app.app_context():
            connectDb()
            if not __dev__:
                initChangeTracker()
    except Exception as ex:
        log.error('!!! ChangeTracker Error !!!')
        log.error(ex)
        traceback.print_exc(file=stdout)
        destroy()


def gunicorn():
    init()
    return app


if __name__ == "__main__":
    init()
    manager.run(default_command='runserver')

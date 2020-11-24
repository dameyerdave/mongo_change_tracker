#!/usr/bin/env python

from os import environ
from sys import exit, stdout
from flask import Flask, jsonify, appcontext_tearing_down
from flask_script import Manager, Server
from flask_cors import CORS
from tendo import singleton
from tendo.singleton import SingleInstanceException
from modules.helper import colorize_werkzeug
import atexit
import traceback

import logging
from friendlylog import colored_logger as log

# Logging
logging.basicConfig(level=logging.DEBUG)
colorize_werkzeug()


# make sure only one instance is running
try: 
  me = singleton.SingleInstance()
except SingleInstanceException as ex:
  log.error("MCT already running!")
  exit(1)


app = Flask(__name__)
CORS(app)

# API
@app.route('/')
def status():
    status = {
      'running': True
    }
    return jsonify(status)


# Initialization methods
def connectDb():
    from mongoengine import connect
    connect('icarus', host=environ.get('CT_MONGO_DATABASE_URI'))


def initChangeTracker():
    from modules.change_tracker import ChangeTracker
    changeTracker = ChangeTracker(environ.get('CT_MONGO_DATABASE_URI'), [
        'variants', 'patient'])
    changeTracker.start()

@atexit.register
def destroy():
    from modules.change_tracker import ChangeTracker
    ChangeTracker.destroy()

# Manager and commands
manager = Manager(app)
server = Server(host=environ.get('CT_HOSTNAME'), port=environ.get('CT_PORT'))
manager.add_command('runserver', server)

if __name__ == "__main__":
  try:
    with app.app_context():
      connectDb()
      initChangeTracker()
    manager.run(default_command='runserver')
  except Exception as ex:
    log.error('!!! ChangeTracker Error !!!')
    log.error(ex)
    traceback.print_exc(file=stdout)
    destroy()
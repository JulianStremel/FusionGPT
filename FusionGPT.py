import os
import sys

# Get the absolute path to the "/lib" folder relative to the current file.
lib_path = os.path.join(os.path.dirname(__file__), "lib")
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

from . import commands
from .lib import fusionAddInUtils as futil
from FusionGPT import FusionGPT


def run(context):
    try:
        # Initialize the FusionGPT singleton
        fusiongpt = FusionGPT()

        # Start all commands
        commands.start()

    except:
        futil.handle_error('run')


def stop(context):
    try:
        futil.clear_handlers()
        commands.stop()

        # Close database connection
        instance = FusionGPT.instance()
        if instance and instance.sqlite:
            instance.sqlite.close()

    except:
        futil.handle_error('stop')

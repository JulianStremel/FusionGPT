# FusionGPT Command Registry
# Commands are registered here and automatically started/stopped with the add-in.

from .commandDialog import entry as settingsDialog
from .paletteShow import entry as chatPalette

commands = [
    settingsDialog,
    chatPalette,
]


def start():
    for command in commands:
        command.start()


def stop():
    for command in commands:
        command.stop()

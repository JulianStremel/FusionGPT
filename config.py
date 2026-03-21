# Application Global Variables
# This module serves as a way to share variables across different
# modules (global variables).

import os

# Flag that indicates to run in Debug mode or not.
DEBUG = True

# Gets the name of the add-in from the name of the folder the py file is in.
ADDIN_NAME = os.path.basename(os.path.dirname(__file__))
COMPANY_NAME = 'JulianStremel'

# Palettes
chat_palette_id = f'{COMPANY_NAME}_{ADDIN_NAME}_chat_palette'

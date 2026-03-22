import json
import adsk.core
import os
from ...lib import fusionAddInUtils as futil
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_Settings'
CMD_NAME = 'FusionGPT Settings'
CMD_Description = 'Configure FusionGPT API key and model settings'

IS_PROMOTED = False

WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidScriptsAddinsPanel'
COMMAND_BESIDE_ID = 'ScriptsManagerCommand'

ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

local_handlers = []


def start():
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)
    futil.add_handler(cmd_def.commandCreated, command_created)

    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)
    control.isPromoted = IS_PROMOTED


def stop():
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    if command_control:
        command_control.deleteMe()
    if command_definition:
        command_definition.deleteMe()


def command_created(args: adsk.core.CommandCreatedEventArgs):
    futil.log(f'{CMD_NAME} Command Created Event')

    inputs = args.command.commandInputs

    from FusionGPT import FusionGPT
    gpt = FusionGPT.instance()

    # API Key input
    current_key = gpt.get_api_key_masked() if gpt else ""
    placeholder = f"Current: {current_key}" if current_key else "Enter your OpenAI API key (sk-...)"
    inputs.addTextBoxCommandInput('api_key_input', 'OpenAI API Key', placeholder, 1, False)

    # Model selection dropdown
    model_dropdown = inputs.addDropDownCommandInput(
        'model_select', 'Model',
        adsk.core.DropDownStyles.TextListDropDownStyle
    )

    current_model = gpt.get_model() if gpt else "gpt-4o"
    available_models = gpt.get_available_models() if gpt else ["gpt-4o"]

    for model in available_models:
        is_selected = (model == current_model)
        model_dropdown.listItems.add(model, is_selected)

    # Status display
    if gpt and gpt.is_api_ready():
        status = "Connected"
    else:
        status = "Not connected - please enter a valid API key"
    inputs.addTextBoxCommandInput('status_display', 'Status', status, 1, True)

    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)


def command_execute(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Execute Event')

    inputs = args.command.commandInputs
    api_key_input: adsk.core.TextBoxCommandInput = inputs.itemById('api_key_input')
    model_select: adsk.core.DropDownCommandInput = inputs.itemById('model_select')

    from FusionGPT import FusionGPT
    gpt = FusionGPT.instance()
    if not gpt:
        ui.messageBox("FusionGPT is not initialized.")
        return

    # Update API key if a new one was entered (not the masked placeholder)
    new_key = api_key_input.text.strip()
    if new_key and new_key.startswith('sk-'):
        success = gpt.set_api_key(new_key)
        if success:
            ui.messageBox("API key updated and validated successfully.")
        else:
            ui.messageBox("Invalid API key. Please check and try again.")
            return

    # Update model selection
    selected_model = model_select.selectedItem.name
    gpt.set_model(selected_model)

    futil.log(f'{CMD_NAME}: Settings saved. Model: {selected_model}')


def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    futil.log(f'{CMD_NAME} Input Changed: {changed_input.id}')


def command_destroy(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME} Command Destroy Event')
    global local_handlers
    local_handlers = []

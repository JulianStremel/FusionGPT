import json
import threading
import adsk.core
import os
from ...lib import fusionAddInUtils as futil
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface

CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_ChatPalette'
CMD_NAME = 'FusionGPT Chat'
CMD_Description = 'Open the FusionGPT AI chat interface'
PALETTE_NAME = 'FusionGPT'
IS_PROMOTED = True

PALETTE_ID = config.chat_palette_id

PALETTE_URL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'html', 'index.html')
PALETTE_URL = PALETTE_URL.replace('\\', '/')

PALETTE_DOCKING = adsk.core.PaletteDockingStates.PaletteDockStateRight

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
    palette = ui.palettes.itemById(PALETTE_ID)

    if command_control:
        command_control.deleteMe()
    if command_definition:
        command_definition.deleteMe()
    if palette:
        palette.deleteMe()


def command_created(args: adsk.core.CommandCreatedEventArgs):
    futil.log(f'{CMD_NAME}: Command created event.')
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)


def command_execute(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME}: Command execute event.')

    palettes = ui.palettes
    palette = palettes.itemById(PALETTE_ID)
    if palette is None:
        palette = palettes.add(
            id=PALETTE_ID,
            name=PALETTE_NAME,
            htmlFileURL=PALETTE_URL,
            isVisible=True,
            showCloseButton=True,
            isResizable=True,
            width=450,
            height=700,
            useNewWebBrowser=True
        )
        futil.add_handler(palette.closed, palette_closed)
        futil.add_handler(palette.navigatingURL, palette_navigating)
        futil.add_handler(palette.incomingFromHTML, palette_incoming)
        futil.log(f'{CMD_NAME}: Created new palette: {palette.id}')

    if palette.dockingState == adsk.core.PaletteDockingStates.PaletteDockStateFloating:
        palette.dockingState = PALETTE_DOCKING

    palette.isVisible = True

    # Send initial state to the palette
    _send_init_state(palette)


def _send_init_state(palette):
    """Send current state (conversations, model, etc.) to the HTML palette."""
    from FusionGPT import FusionGPT
    gpt = FusionGPT.instance()
    if not gpt:
        return

    state = {
        "api_ready": gpt.is_api_ready(),
        "current_model": gpt.get_model(),
        "available_models": gpt.get_available_models(),
        "conversations": gpt.get_conversations(),
        "current_conversation_id": gpt.current_conversation_id,
        "api_key_masked": gpt.get_api_key_masked(),
    }

    # Load current conversation messages if there is one
    if gpt.current_conversation_id:
        messages = gpt.load_conversation(gpt.current_conversation_id)
        # Filter to only user and assistant messages for display
        state["messages"] = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m["role"] in ("user", "assistant")
        ]
    else:
        state["messages"] = []

    palette.sendInfoToHTML("initState", json.dumps(state))


def palette_closed(args: adsk.core.UserInterfaceGeneralEventArgs):
    futil.log(f'{CMD_NAME}: Palette was closed.')


def palette_navigating(args: adsk.core.NavigationEventArgs):
    url = args.navigationURL
    if url.startswith("http"):
        args.launchExternally = True


def palette_incoming(html_args: adsk.core.HTMLEventArgs):
    """Handle incoming events from the chat UI."""
    futil.log(f'{CMD_NAME}: Palette incoming event.')

    action = html_args.action
    data_str = html_args.data

    try:
        data = json.loads(data_str) if data_str else {}
    except json.JSONDecodeError:
        data = {}

    from FusionGPT import FusionGPT
    gpt = FusionGPT.instance()

    if action == 'sendMessage':
        user_message = data.get('message', '').strip()
        if not user_message:
            html_args.returnData = json.dumps({"error": "Empty message"})
            return

        if not gpt or not gpt.is_api_ready():
            html_args.returnData = json.dumps({"error": "API key not configured. Open Settings to add your OpenAI API key."})
            return

        # Process chat (this calls OpenAI and may execute tool calls)
        response = gpt.chat(user_message)

        html_args.returnData = json.dumps({
            "response": response,
            "conversation_id": gpt.current_conversation_id,
        })

    elif action == 'setApiKey':
        key = data.get('key', '').strip()
        if not gpt:
            html_args.returnData = json.dumps({"success": False, "error": "FusionGPT not initialized"})
            return

        success = gpt.set_api_key(key)
        html_args.returnData = json.dumps({
            "success": success,
            "api_key_masked": gpt.get_api_key_masked() if success else "",
            "error": "" if success else "Invalid API key. Please check and try again.",
        })

    elif action == 'setModel':
        model = data.get('model', '')
        if gpt:
            gpt.set_model(model)
        html_args.returnData = json.dumps({"success": True, "model": model})

    elif action == 'newConversation':
        if gpt:
            conv_id = gpt.create_conversation()
            html_args.returnData = json.dumps({
                "conversation_id": conv_id,
                "conversations": gpt.get_conversations(),
            })
        else:
            html_args.returnData = json.dumps({"error": "FusionGPT not initialized"})

    elif action == 'loadConversation':
        conv_id = data.get('conversation_id')
        if gpt and conv_id:
            messages = gpt.load_conversation(conv_id)
            display_messages = [
                {"role": m["role"], "content": m["content"]}
                for m in messages
                if m["role"] in ("user", "assistant")
            ]
            html_args.returnData = json.dumps({
                "conversation_id": conv_id,
                "messages": display_messages,
            })
        else:
            html_args.returnData = json.dumps({"error": "Invalid conversation"})

    elif action == 'deleteConversation':
        conv_id = data.get('conversation_id')
        if gpt and conv_id:
            gpt.delete_conversation(conv_id)
            html_args.returnData = json.dumps({
                "success": True,
                "conversations": gpt.get_conversations(),
            })
        else:
            html_args.returnData = json.dumps({"error": "Invalid conversation"})

    elif action == 'getConversations':
        if gpt:
            html_args.returnData = json.dumps({
                "conversations": gpt.get_conversations(),
            })
        else:
            html_args.returnData = json.dumps({"conversations": []})

    elif action == 'getState':
        if gpt:
            _send_init_state(ui.palettes.itemById(PALETTE_ID))
        html_args.returnData = json.dumps({"success": True})

    else:
        html_args.returnData = json.dumps({"error": f"Unknown action: {action}"})


def command_destroy(args: adsk.core.CommandEventArgs):
    futil.log(f'{CMD_NAME}: Command destroy event.')
    global local_handlers
    local_handlers = []

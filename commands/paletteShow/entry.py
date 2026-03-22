import json
import queue
import threading
import traceback
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

# ---------------------------------------------------------------------------
# Custom event IDs for background-thread → main-thread communication.
# TOOL_EXEC_EVENT: background thread requests a Fusion API tool call.
# CHAT_DONE_EVENT: background thread finished; send response to palette.
# ---------------------------------------------------------------------------
TOOL_EXEC_EVENT = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_ToolExec'
CHAT_DONE_EVENT = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_ChatDone'

# Maximum seconds to wait for a Fusion tool call to execute on the main thread.
TOOL_EXECUTION_TIMEOUT_SECONDS = 30

# Queues shared between background thread and custom-event handlers.
# Note: only tool-exec uses a result queue (round-trip handshake); the chat-done
# result is passed directly through CustomEventArgs.additionalInfo to avoid any
# queue-timing issues.
_tool_request_queue: queue.Queue = queue.Queue()
_tool_result_queue: queue.Queue = queue.Queue()

local_handlers = []
_custom_event_handlers = []


def start():
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)
    futil.add_handler(cmd_def.commandCreated, command_created)

    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)
    control.isPromoted = IS_PROMOTED

    # Register custom events used for off-thread chat execution.
    _register_custom_events()


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

    _unregister_custom_events()


# ---------------------------------------------------------------------------
# Custom-event registration helpers
# ---------------------------------------------------------------------------

def _register_custom_events():
    global _custom_event_handlers
    _custom_event_handlers = []

    for event_id, handler in [
        (TOOL_EXEC_EVENT, _on_tool_exec),
        (CHAT_DONE_EVENT, _on_chat_done),
    ]:
        try:
            app.registerCustomEvent(event_id)
        except Exception:
            pass  # Already registered from a previous load

        custom_event = app.customEvents.itemById(event_id)
        if custom_event:
            futil.add_handler(custom_event, handler,
                              local_handlers=_custom_event_handlers)


def _unregister_custom_events():
    global _custom_event_handlers
    _custom_event_handlers = []

    for event_id in (TOOL_EXEC_EVENT, CHAT_DONE_EVENT):
        try:
            app.unregisterCustomEvent(event_id)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Custom-event handlers (always called on the main thread by Fusion)
# ---------------------------------------------------------------------------

def _on_tool_exec(args: adsk.core.CustomEventArgs):
    """Main thread: execute the tool call requested by the background thread."""
    from FusionGPT.fusion_tools import execute_tool
    try:
        tool_name, tool_args = _tool_request_queue.get_nowait()
        result = execute_tool(tool_name, tool_args)
        _tool_result_queue.put(result)
    except queue.Empty:
        _tool_result_queue.put(json.dumps({"error": "Tool request queue was empty"}))
    except Exception:
        _tool_result_queue.put(json.dumps({"error": traceback.format_exc()}))


def _on_chat_done(args: adsk.core.CustomEventArgs):
    """Main thread: forward the finished chat result to the HTML palette.

    The result JSON is carried directly in args.additionalInfo so there is no
    separate queue and no timing dependency between the put() and the event
    delivery.
    """
    try:
        data_str = args.additionalInfo
        result = json.loads(data_str)
        palette = ui.palettes.itemById(PALETTE_ID)
        if palette is None:
            futil.log(f'{CMD_NAME}: _on_chat_done – palette not found, response lost')
            return
        action = 'chatError' if result.get('error') else 'chatResponse'
        futil.log(f'{CMD_NAME}: _on_chat_done – sending {action} to palette')
        palette.sendInfoToHTML(action, data_str)
    except Exception:
        futil.handle_error('_on_chat_done')


# ---------------------------------------------------------------------------
# Background-thread helpers
# ---------------------------------------------------------------------------

def _tool_executor(tool_name: str, tool_args: dict) -> str:
    """Called from the background thread to execute a Fusion-API tool on the
    main thread via a custom event, then block until the result arrives."""
    _tool_request_queue.put((tool_name, tool_args))
    app.fireCustomEvent(TOOL_EXEC_EVENT, '')
    try:
        return _tool_result_queue.get(timeout=TOOL_EXECUTION_TIMEOUT_SECONDS)
    except queue.Empty:
        return json.dumps({"error": f"Tool execution timed out after {TOOL_EXECUTION_TIMEOUT_SECONDS} s"})


def _run_chat_in_thread(user_message: str, feature_tree: str):
    """Background thread: run the full chat/tool-call loop then signal the
    main thread via CHAT_DONE_EVENT.

    The result is serialised to JSON and passed as the additionalInfo string
    of the custom event so that the main-thread handler can read it directly
    from args.additionalInfo without any queue involvement.
    """
    from FusionGPT import FusionGPT
    gpt = FusionGPT.instance()
    result_json = json.dumps({"error": "Unknown error in chat thread"})
    try:
        response = gpt.chat(
            user_message,
            feature_tree_context=feature_tree,
            tool_executor=_tool_executor,
        )
        result_json = json.dumps({
            "response": response,
            "conversation_id": gpt.current_conversation_id,
        })
    except Exception:
        result_json = json.dumps({"error": traceback.format_exc()})
    finally:
        app.fireCustomEvent(CHAT_DONE_EVENT, result_json)


# ---------------------------------------------------------------------------
# Palette command handlers
# ---------------------------------------------------------------------------

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
            html_args.returnData = json.dumps({
                "error": "API key not configured. Open Settings to add your OpenAI API key."
            })
            return

        # Extract the feature tree on the main thread (Fusion API call) before
        # handing off to the background thread.
        from FusionGPT.feature_tree import get_feature_tree_context
        try:
            feature_tree = get_feature_tree_context()
        except Exception:
            feature_tree = ""

        # Start the chat in a background thread so the main thread is not
        # blocked during the (potentially slow) OpenAI HTTP call.
        t = threading.Thread(
            target=_run_chat_in_thread,
            args=(user_message, feature_tree),
            daemon=True,
        )
        t.start()

        # Return immediately; the actual response is delivered via the
        # CHAT_DONE_EVENT custom event → _on_chat_done → sendInfoToHTML.
        html_args.returnData = json.dumps({"status": "processing"})

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


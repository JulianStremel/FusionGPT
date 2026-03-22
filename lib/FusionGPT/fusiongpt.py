import os
import json
import traceback
from sqlite3 import connect, Connection, Cursor
from typing import Callable, Optional
from .helper import install, checkSqlite, initSqlite, migrate_db, get_db_path
from . import logger as fgpt_logger

try:
    from openai import OpenAI
except Exception:
    install('openai')
    from openai import OpenAI

from .feature_tree import get_feature_tree_context
from .fusion_tools import TOOL_DEFINITIONS, execute_tool

AVAILABLE_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo",
    "o1",
    "o1-mini",
    "o3-mini",
]

DEFAULT_MODEL = "gpt-4o"

SYSTEM_PROMPT = """You are FusionGPT, an AI assistant integrated directly into Autodesk Fusion 360.
You help users with CAD design tasks, answer questions about their designs, and can directly
interact with the Fusion 360 environment through function calls.

Your capabilities:
- Answer questions about CAD design, engineering, and manufacturing
- Analyze the user's current Fusion 360 design (feature tree, components, sketches, bodies)
- Create sketches, draw shapes, extrude profiles, add fillets/chamfers, and more via function calls
- Create and modify user parameters
- Provide design insights and suggestions based on the current design context

When the user asks you to create or modify geometry, use the available tools.
When discussing the design, reference the feature tree context provided.
Be concise and practical. You are a CAD assistant, not a general-purpose chatbot.
"""


class FusionGPT:

    api: OpenAI
    sqlite: Connection
    cursor: Cursor
    path: str
    current_model: str
    current_conversation_id: int

    _instance = None

    @classmethod
    def instance(cls):
        """Return the singleton instance."""
        return cls._instance

    def __init__(self):
        FusionGPT._instance = self
        self.api = None
        self.sqlite = None
        self.cursor = None
        self.path = os.path.dirname(__file__)
        self.current_model = DEFAULT_MODEL
        self.current_conversation_id = None

        if not checkSqlite():
            initSqlite()
        else:
            migrate_db()

        self.sqlite = connect(get_db_path(), check_same_thread=False)
        self.sqlite.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.sqlite.cursor()

        self._load_settings()
        self._init_api()

    def _load_settings(self):
        """Load saved settings from the database."""
        try:
            self.cursor.execute("SELECT value FROM settings WHERE name='model'")
            row = self.cursor.fetchone()
            if row:
                self.current_model = row[0]
        except Exception:
            pass

    def _save_setting(self, name: str, value: str):
        """Persist a setting to the database."""
        self.cursor.execute(
            "INSERT INTO settings (name, value) VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET value=?",
            (name, value, value)
        )
        self.sqlite.commit()

    def _init_api(self):
        """Initialize OpenAI client from stored API key."""
        try:
            self.cursor.execute("SELECT value FROM keys WHERE name='OPENAI_API_KEY'")
            row = self.cursor.fetchone()
            if row and row[0]:
                self.api = OpenAI(api_key=row[0])
            else:
                print("FusionGPT: No OpenAI API key configured.")
        except Exception:
            print(f"FusionGPT: Error initializing API: {traceback.format_exc()}")

    def is_api_ready(self) -> bool:
        """Check if the OpenAI API client is configured."""
        return self.api is not None

    def set_api_key(self, key: str) -> bool:
        """Set and validate the OpenAI API key."""
        try:
            client = OpenAI(api_key=key)
            client.models.list()

            self.cursor.execute(
                "INSERT INTO keys (name, value) VALUES ('OPENAI_API_KEY', ?) ON CONFLICT(name) DO UPDATE SET value=?",
                (key, key)
            )
            self.sqlite.commit()
            self.api = client
            return True
        except Exception:
            return False

    def get_api_key_masked(self) -> str:
        """Return masked version of stored API key."""
        try:
            self.cursor.execute("SELECT value FROM keys WHERE name='OPENAI_API_KEY'")
            row = self.cursor.fetchone()
            if row and row[0] and len(row[0]) > 8:
                return row[0][:4] + "..." + row[0][-4:]
        except Exception:
            pass
        return ""

    def set_model(self, model: str):
        """Set the active model."""
        self.current_model = model
        self._save_setting("model", model)

    def get_model(self) -> str:
        return self.current_model

    def get_available_models(self) -> list:
        return AVAILABLE_MODELS

    # --- Conversation Management ---

    def create_conversation(self, title: str = "New Chat") -> int:
        """Create a new conversation and return its ID."""
        self.cursor.execute(
            "INSERT INTO conversations (title, model) VALUES (?, ?)",
            (title, self.current_model)
        )
        self.sqlite.commit()
        self.current_conversation_id = self.cursor.lastrowid
        return self.current_conversation_id

    def get_conversations(self, limit: int = 50) -> list:
        """Get recent conversations."""
        self.cursor.execute(
            "SELECT id, title, model, created_at, updated_at FROM conversations ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        )
        return [
            {"id": r[0], "title": r[1], "model": r[2], "created_at": r[3], "updated_at": r[4]}
            for r in self.cursor.fetchall()
        ]

    def load_conversation(self, conversation_id: int) -> list:
        """Load all messages for a conversation."""
        self.current_conversation_id = conversation_id
        self.cursor.execute(
            "SELECT role, content, tool_calls, tool_call_id FROM messages WHERE conversation_id=? ORDER BY id ASC",
            (conversation_id,)
        )
        messages = []
        for r in self.cursor.fetchall():
            msg = {"role": r[0], "content": r[1] or ""}
            if r[2]:
                msg["tool_calls"] = json.loads(r[2])
            if r[3]:
                msg["tool_call_id"] = r[3]
            messages.append(msg)
        return messages

    def delete_conversation(self, conversation_id: int):
        """Delete a conversation and its messages."""
        self.cursor.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))
        self.cursor.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))
        self.sqlite.commit()
        if self.current_conversation_id == conversation_id:
            self.current_conversation_id = None

    def _save_message(self, conversation_id: int, role: str, content: str,
                      tool_calls=None, tool_call_id=None):
        """Save a message to the database."""
        tc_json = json.dumps(tool_calls) if tool_calls else None
        self.cursor.execute(
            "INSERT INTO messages (conversation_id, role, content, tool_calls, tool_call_id) VALUES (?, ?, ?, ?, ?)",
            (conversation_id, role, content or "", tc_json, tool_call_id)
        )
        self.cursor.execute(
            "UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (conversation_id,)
        )
        self.sqlite.commit()

    def _auto_title(self, conversation_id: int, user_message: str):
        """Auto-generate conversation title from first message."""
        title = user_message[:60].strip()
        if len(user_message) > 60:
            title += "..."
        self.cursor.execute("UPDATE conversations SET title=? WHERE id=?", (title, conversation_id))
        self.sqlite.commit()

    # --- Chat ---

    def chat(self, user_message: str, include_feature_tree: bool = True,
             feature_tree_context: str = None,
             tool_executor: Optional[Callable[[str, dict], str]] = None) -> str:
        """Send a message and get a response. Handles function calling loop.

        Parameters
        ----------
        user_message:
            The text the user typed.
        include_feature_tree:
            If *True* and no *feature_tree_context* is provided, the method
            will try to extract the feature-tree from Fusion (safe only when
            called from the Fusion main thread).
        feature_tree_context:
            Pre-extracted feature-tree string.  When supplied the
            *include_feature_tree* flag is ignored.  Pass this when calling
            from a background thread so that the Fusion API is not accessed
            off-thread.
        tool_executor:
            Optional callable ``(tool_name: str, args: dict) -> str``.
            When provided it is used instead of the built-in ``execute_tool``
            function.  Pass a custom executor when running in a background
            thread so that Fusion API calls are marshalled to the main thread.
        """
        if not self.is_api_ready():
            return "Error: OpenAI API key not configured. Please set it in Settings."

        if self.current_conversation_id is None:
            self.create_conversation()

        conv_id = self.current_conversation_id

        # Check if this is the first user message to auto-title
        self.cursor.execute("SELECT COUNT(*) FROM messages WHERE conversation_id=? AND role='user'", (conv_id,))
        is_first = self.cursor.fetchone()[0] == 0

        # Save user message
        self._save_message(conv_id, "user", user_message)

        if is_first:
            self._auto_title(conv_id, user_message)

        # Build messages list
        messages = self._build_messages(conv_id, include_feature_tree, feature_tree_context)

        # Call OpenAI with function calling loop
        try:
            return self._completion_loop(conv_id, messages, tool_executor=tool_executor)
        except Exception as e:
            error_msg = f"Error calling OpenAI API: {str(e)}"
            fgpt_logger.log_error(f"chat() error: {traceback.format_exc()}")
            return error_msg

    def _build_messages(self, conv_id: int, include_feature_tree: bool = True,
                        feature_tree_context: str = None) -> list:
        """Build the full messages array for the API call."""
        system_content = SYSTEM_PROMPT

        if feature_tree_context:
            # Use pre-extracted context (caller is responsible for thread safety)
            system_content += f"\n\n{feature_tree_context}"
        elif include_feature_tree:
            try:
                tree_context = get_feature_tree_context()
                if tree_context:
                    system_content += f"\n\n{tree_context}"
            except Exception:
                pass

        messages = [{"role": "system", "content": system_content}]

        # Load conversation history
        history = self.load_conversation(conv_id)
        for msg in history:
            api_msg = {"role": msg["role"], "content": msg["content"]}
            if msg.get("tool_calls"):
                api_msg["tool_calls"] = msg["tool_calls"]
            if msg.get("tool_call_id"):
                api_msg["tool_call_id"] = msg["tool_call_id"]
            messages.append(api_msg)

        return messages

    def _completion_loop(self, conv_id: int, messages: list,
                         max_iterations: int = 10,
                         tool_executor: Optional[Callable[[str, dict], str]] = None) -> str:
        """Run the completion loop, handling tool calls until a final text response."""
        for _ in range(max_iterations):
            fgpt_logger.log_llm_request(self.current_model, messages)

            response = self.api.chat.completions.create(
                model=self.current_model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
            )

            choice = response.choices[0]
            message = choice.message

            if message.tool_calls:
                # Save assistant message with tool calls
                tool_calls_data = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in message.tool_calls
                ]
                fgpt_logger.log_llm_response(message.content, tool_calls_data)

                self._save_message(conv_id, "assistant", message.content or "", tool_calls=tool_calls_data)
                messages.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": tool_calls_data,
                })

                # Execute each tool call
                for tc in message.tool_calls:
                    args = json.loads(tc.function.arguments)
                    if tool_executor is not None:
                        result = tool_executor(tc.function.name, args)
                    else:
                        result = execute_tool(tc.function.name, args)

                    fgpt_logger.log_tool_call(tc.function.name, args, result)

                    self._save_message(conv_id, "tool", result, tool_call_id=tc.id)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
            else:
                # Final text response
                assistant_text = message.content or ""
                fgpt_logger.log_llm_response(assistant_text)
                self._save_message(conv_id, "assistant", assistant_text)
                return assistant_text

        return "Error: Maximum tool call iterations reached."

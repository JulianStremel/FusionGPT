# FusionGPT

FusionGPT is an Autodesk Fusion 360 add-in that integrates OpenAI's GPT models, allowing users to chat with AI directly within Fusion 360. The AI can provide design insights, answer questions, and interact with the Fusion 360 environment through function calling.

## Features

1.  [x] **Basic AI Chat**: Full chat interface inside a Fusion 360 palette with markdown rendering, conversation threading, and a dark-themed UI.
2.  [x] **Persistent Context**: Model selection (GPT-4o, GPT-4 Turbo, GPT-3.5 Turbo, o1, o3-mini, etc.), conversation history stored in SQLite, and settings persisted across restarts.
3.  [x] **Feature Tree Parsing**: Automatically extracts the active design's component hierarchy, bodies, sketches, features, timeline, joints, and user parameters — all provided as context to the AI.
4.  [x] **AI-Driven Interactions**: OpenAI function calling enables the AI to directly manipulate Fusion 360 — create sketches, draw shapes, extrude profiles, add fillets/chamfers, revolve, create components, and manage parameters.

## Setup

1. Copy the `FusionGPT` folder to your Fusion 360 add-ins directory:
   - **Windows**: `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\`
   - **macOS**: `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/`
2. In Fusion 360, go to **Tools > Add-Ins** and enable **FusionGPT**.
3. Click the **FusionGPT Chat** button in the toolbar to open the chat palette.
4. On first launch, open **Settings** (gear icon in the sidebar) and enter your OpenAI API key.

## Architecture

```
FusionGPT/
├── FusionGPT.py              # Main entry point (run/stop lifecycle)
├── config.py                 # Global configuration
├── lib/
│   ├── FusionGPT/
│   │   ├── fusiongpt.py      # Core class: chat, history, model management
│   │   ├── feature_tree.py   # Fusion 360 design tree extraction
│   │   ├── fusion_tools.py   # OpenAI function-calling tool definitions
│   │   └── helper.py         # Database setup and utilities
│   └── fusionAddInUtils/     # Fusion 360 add-in framework utilities
├── commands/
│   ├── paletteShow/          # Chat palette command + HTML/JS UI
│   └── commandDialog/        # Settings dialog command
└── FusionGPT.manifest        # Add-in manifest
```

## Available AI Tools

The AI can execute these actions in your design via function calling:

| Tool | Description |
|------|-------------|
| `create_sketch` | Create a sketch on XY, XZ, or YZ plane |
| `draw_rectangle` | Draw a rectangle on a sketch |
| `draw_circle` | Draw a circle on a sketch |
| `extrude_profile` | Extrude a sketch profile (new body, join, cut, intersect) |
| `revolve_profile` | Revolve a sketch profile around an axis |
| `add_fillet` | Add fillets to body edges |
| `add_chamfer` | Add chamfers to body edges |
| `set_parameter` | Create or modify user parameters |
| `create_component` | Create a new component |
| `get_design_info` | Query design structure and parameters |

## Notes

The backend uses OpenAI's API directly. Future work could add support for alternative backends like Ollama or other LLM providers.
- https://github.com/emirsahin1/llm-axe/blob/main/examples/ex_llm_setup.py
- https://github.com/szczyglis-dev/py-gpt
- https://ai.pydantic.dev/

// FusionGPT Chat UI - JavaScript

let state = {
    apiReady: false,
    currentModel: 'gpt-4o',
    availableModels: [],
    conversations: [],
    currentConversationId: null,
    isLoading: false,
};

// --- Initialization ---

function initState(dataString) {
    try {
        const data = JSON.parse(dataString);
        state.apiReady = data.api_ready || false;
        state.currentModel = data.current_model || 'gpt-4o';
        state.availableModels = data.available_models || [];
        state.conversations = data.conversations || [];
        state.currentConversationId = data.current_conversation_id;

        updateModelSelectors();
        updateConversationList();
        updateApiBanner();

        if (data.messages && data.messages.length > 0) {
            hideWelcome();
            data.messages.forEach(function(msg) {
                if (msg.role === 'user' || msg.role === 'assistant') {
                    appendMessage(msg.role, msg.content);
                }
            });
            scrollToBottom();
        }
    } catch (e) {
        console.log('Error parsing init state:', e);
    }
}

// --- UI Updates ---

function updateModelSelectors() {
    var headerSelect = document.getElementById('modelSelect');
    var settingsSelect = document.getElementById('settingsModelSelect');

    [headerSelect, settingsSelect].forEach(function(select) {
        if (!select) return;
        select.innerHTML = '';
        state.availableModels.forEach(function(model) {
            var opt = document.createElement('option');
            opt.value = model;
            opt.textContent = model;
            opt.selected = model === state.currentModel;
            select.appendChild(opt);
        });
    });
}

function updateConversationList() {
    var list = document.getElementById('conversationList');
    if (!list) return;
    list.innerHTML = '';

    state.conversations.forEach(function(conv) {
        var item = document.createElement('div');
        item.className = 'conv-item' + (conv.id === state.currentConversationId ? ' active' : '');
        item.onclick = function(e) {
            if (e.target.classList.contains('conv-delete')) return;
            loadConversation(conv.id);
        };

        var title = document.createElement('span');
        title.className = 'conv-title';
        title.textContent = conv.title || 'New Chat';
        item.appendChild(title);

        var del = document.createElement('button');
        del.className = 'conv-delete';
        del.innerHTML = '&#x2715;';
        del.onclick = function(e) {
            e.stopPropagation();
            deleteConversation(conv.id);
        };
        item.appendChild(del);

        list.appendChild(item);
    });
}

function updateApiBanner() {
    var banner = document.getElementById('apiBanner');
    if (banner) {
        banner.classList.toggle('show', !state.apiReady);
    }
}

function hideWelcome() {
    var welcome = document.getElementById('welcomeScreen');
    if (welcome) welcome.style.display = 'none';
}

function showWelcome() {
    var welcome = document.getElementById('welcomeScreen');
    if (welcome) welcome.style.display = 'flex';
}

function clearMessages() {
    var container = document.getElementById('chatContainer');
    container.innerHTML = '<div class="welcome-screen" id="welcomeScreen" style="display: flex;">' +
        '<h2>FusionGPT</h2>' +
        '<p>AI-powered design assistant for Autodesk Fusion 360. Ask questions, get design insights, or let the AI create geometry for you.</p>' +
        '<div class="hint"><p>Try: "Create a 5cm x 3cm rectangle and extrude it 2cm"</p>' +
        '<p>Or: "Explain the features in my current design"</p></div></div>';
}

function appendMessage(role, content) {
    hideWelcome();
    var container = document.getElementById('chatContainer');

    var msgDiv = document.createElement('div');
    msgDiv.className = 'message ' + role;

    var roleLabel = document.createElement('div');
    roleLabel.className = 'message-role';
    roleLabel.textContent = role === 'user' ? 'You' : 'FusionGPT';
    msgDiv.appendChild(roleLabel);

    var contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = formatMessage(content);
    msgDiv.appendChild(contentDiv);

    container.appendChild(msgDiv);
    scrollToBottom();
}

function appendError(message) {
    hideWelcome();
    var container = document.getElementById('chatContainer');

    var msgDiv = document.createElement('div');
    msgDiv.className = 'message error';

    var roleLabel = document.createElement('div');
    roleLabel.className = 'message-role';
    roleLabel.textContent = 'Error';
    msgDiv.appendChild(roleLabel);

    var contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = message;
    msgDiv.appendChild(contentDiv);

    container.appendChild(msgDiv);
    scrollToBottom();
}

function formatMessage(text) {
    if (!text) return '';

    // Escape HTML
    var escaped = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    // Code blocks (```)
    escaped = escaped.replace(/```(\w*)\n?([\s\S]*?)```/g, function(match, lang, code) {
        return '<pre><code>' + code.trim() + '</code></pre>';
    });

    // Inline code (`)
    escaped = escaped.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold (**)
    escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic (*)
    escaped = escaped.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    return escaped;
}

function scrollToBottom() {
    var container = document.getElementById('chatContainer');
    setTimeout(function() {
        container.scrollTop = container.scrollHeight;
    }, 50);
}

function setLoading(loading) {
    state.isLoading = loading;
    var indicator = document.getElementById('typingIndicator');
    var sendBtn = document.getElementById('sendBtn');
    var input = document.getElementById('messageInput');

    indicator.classList.toggle('show', loading);
    sendBtn.disabled = loading;
    input.disabled = loading;

    if (!loading) {
        input.focus();
    }

    scrollToBottom();
}

// --- Actions ---

function sendMessage() {
    var input = document.getElementById('messageInput');
    var message = input.value.trim();

    if (!message || state.isLoading) return;

    // Show user message
    appendMessage('user', message);
    input.value = '';
    autoResize(input);

    setLoading(true);

    // Send to Fusion
    var payload = JSON.stringify({ message: message });
    adsk.fusionSendData('sendMessage', payload).then(function(resultStr) {
        setLoading(false);

        try {
            var result = JSON.parse(resultStr);
            if (result.error) {
                appendError(result.error);
            } else {
                appendMessage('assistant', result.response);
                state.currentConversationId = result.conversation_id;
                // Refresh conversation list
                refreshConversations();
            }
        } catch (e) {
            appendError('Failed to parse response: ' + resultStr);
        }
    }).catch(function(err) {
        setLoading(false);
        appendError('Communication error: ' + err);
    });
}

function newConversation() {
    var payload = JSON.stringify({});
    adsk.fusionSendData('newConversation', payload).then(function(resultStr) {
        try {
            var result = JSON.parse(resultStr);
            if (result.conversation_id) {
                state.currentConversationId = result.conversation_id;
                state.conversations = result.conversations || state.conversations;
                clearMessages();
                showWelcome();
                updateConversationList();
            }
        } catch (e) {
            console.log('Error creating conversation:', e);
        }
    });
}

function loadConversation(convId) {
    var payload = JSON.stringify({ conversation_id: convId });
    adsk.fusionSendData('loadConversation', payload).then(function(resultStr) {
        try {
            var result = JSON.parse(resultStr);
            if (result.error) {
                appendError(result.error);
                return;
            }

            state.currentConversationId = result.conversation_id;
            clearMessages();

            if (result.messages && result.messages.length > 0) {
                result.messages.forEach(function(msg) {
                    if (msg.role === 'user' || msg.role === 'assistant') {
                        appendMessage(msg.role, msg.content);
                    }
                });
            } else {
                showWelcome();
            }

            updateConversationList();
        } catch (e) {
            console.log('Error loading conversation:', e);
        }
    });
}

function deleteConversation(convId) {
    var payload = JSON.stringify({ conversation_id: convId });
    adsk.fusionSendData('deleteConversation', payload).then(function(resultStr) {
        try {
            var result = JSON.parse(resultStr);
            if (result.success) {
                state.conversations = result.conversations || [];
                updateConversationList();

                if (state.currentConversationId === convId) {
                    state.currentConversationId = null;
                    clearMessages();
                    showWelcome();
                }
            }
        } catch (e) {
            console.log('Error deleting conversation:', e);
        }
    });
}

function refreshConversations() {
    adsk.fusionSendData('getConversations', '{}').then(function(resultStr) {
        try {
            var result = JSON.parse(resultStr);
            state.conversations = result.conversations || [];
            updateConversationList();
        } catch (e) {
            console.log('Error refreshing conversations:', e);
        }
    });
}

function changeModel(model) {
    state.currentModel = model;
    updateModelSelectors();
    adsk.fusionSendData('setModel', JSON.stringify({ model: model }));
}

function saveSettings() {
    var apiKey = document.getElementById('apiKeyInput').value.trim();
    var model = document.getElementById('settingsModelSelect').value;
    var statusEl = document.getElementById('settingsStatus');

    // Save model
    if (model && model !== state.currentModel) {
        changeModel(model);
    }

    // Save API key if entered
    if (apiKey && apiKey.startsWith('sk-')) {
        statusEl.textContent = 'Validating API key...';
        statusEl.className = 'status-text';

        adsk.fusionSendData('setApiKey', JSON.stringify({ key: apiKey })).then(function(resultStr) {
            try {
                var result = JSON.parse(resultStr);
                if (result.success) {
                    state.apiReady = true;
                    updateApiBanner();
                    statusEl.textContent = 'API key saved and validated!';
                    statusEl.className = 'status-text success';
                    document.getElementById('apiKeyInput').value = '';
                    document.getElementById('apiKeyInput').placeholder = result.api_key_masked || 'sk-...';
                } else {
                    statusEl.textContent = result.error || 'Invalid API key';
                    statusEl.className = 'status-text error';
                }
            } catch (e) {
                statusEl.textContent = 'Error saving settings';
                statusEl.className = 'status-text error';
            }
        });
    } else if (apiKey) {
        statusEl.textContent = 'API key must start with sk-';
        statusEl.className = 'status-text error';
    } else {
        statusEl.textContent = 'Settings saved!';
        statusEl.className = 'status-text success';
        setTimeout(function() { statusEl.textContent = ''; }, 2000);
    }
}

// --- Sidebar ---

function toggleSidebar() {
    var sidebar = document.getElementById('sidebar');
    var overlay = document.getElementById('sidebarOverlay');
    sidebar.classList.toggle('open');
    overlay.classList.toggle('show');
}

function toggleSettings() {
    var panel = document.getElementById('settingsPanel');
    panel.classList.toggle('show');
}

// --- Input handling ---

function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

// --- Fusion JS Handler ---

window.fusionJavaScriptHandler = {
    handle: function(action, data) {
        try {
            if (action === 'initState') {
                initState(data);
            } else if (action === 'debugger') {
                debugger;
            } else {
                return 'Unexpected action: ' + action;
            }
        } catch (e) {
            console.log('Handler error:', e, 'Action:', action);
        }
        return 'OK';
    },
};

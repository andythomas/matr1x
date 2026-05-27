// Monaco Editor initialization and configuration for Python code editing
// This module handles editor setup, linting integration, and Qt WebChannel communication

// Module state
let editor;
let editorBackend;
let currentDiagnostics = [];
let isModified = false;
let webChannelReady = false;
let monacoReady = false;
let monacoLoaderRequested = false;

const DEFAULT_MONACO_PORT = "54529";

// Enable additional debug logging level
console.debug = (...args) => {
  console.log("[DEBUG]", ...args);
};

const resolveMonacoPort = () => {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get("port") || DEFAULT_MONACO_PORT;
};

// Initialize both systems independently
const initializeIfReady = () => {
  if (webChannelReady && monacoReady) {
    console.log("QWebChannel and Monaco Editor are ready.");
  }
};

// Initialize QWebChannel
const initializeWebChannel = () => {
  new QWebChannel(qt.webChannelTransport, (channel) => {
    editorBackend = channel.objects.editor_backend;

    // Listen for linting results from the Python backend
    editorBackend.lintingComplete.connect((diagnosticsJson) => {
      const diagnostics = JSON.parse(diagnosticsJson);
      updateEditorDiagnostics(diagnostics);
    });

    console.log("QWebChannel initialized, editor backend connected");
    webChannelReady = true;
    initializeIfReady();
  });
};

// Initialize Monaco Editor
const initializeMonacoEditor = () => {
  if (monacoReady) {
    return;
  }

  require.config({
    paths: { vs: `http://localhost:${window.MONACO_PORT}/min/vs` },
  });

  require(["vs/editor/editor.main"], () => {
    editor = monaco.editor.create(document.getElementById("container"), {
      value: "",
      language: "python",
      theme: "vs-light",
      automaticLayout: true,
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      fontSize: 14,
      lineHeight: 21,
      renderWhitespace: "boundary",
      // Tab completion settings
      acceptSuggestionOnEnter: "on",
      acceptSuggestionOnCommitCharacter: true,
      suggestOnTriggerCharacters: true,
      quickSuggestions: {
        other: true,
        comments: true,
        strings: true,
      },
      wordBasedSuggestions: "allDocuments",
      tabCompletion: "on",
      // Disable hover loading popup
      hover: {
        enabled: true,
        delay: 0,
        sticky: true,
      },
    });

    // Register custom completion provider
    registerCustomCompletions();

    // Register hover provider
    registerHoverProvider();

    // Set up automatic linting on content changes
    setupContentChangeHandling();

    // Make editor globally available
    window.editor = editor;

    console.log("Monaco Editor initialized");
    monacoReady = true;
    initializeIfReady();
  });
};

// Register dynamic completion provider
const registerCustomCompletions = () => {
  monaco.languages.registerCompletionItemProvider("python", {
    provideCompletionItems: async (model, position) => {
      const triggerChar = model.getValueInRange({
        startLineNumber: position.lineNumber,
        startColumn: Math.max(1, position.column - 1),
        endLineNumber: position.lineNumber,
        endColumn: position.column,
      });

      const requestId = Date.now() + Math.random(); // Avoid collisions

      return new Promise((resolve, reject) => {
        const timeoutId = setTimeout(() => {
          if (pendingCompletionRequests.has(requestId)) {
            pendingCompletionRequests.delete(requestId);
            resolve({ suggestions: [] });
          }
        }, 2000);

        pendingCompletionRequests.set(requestId, { resolve, reject, timeoutId });

        // Request completions from Python
        if (webChannelReady && editorBackend?.handle_completion_request) {
          try {
            const completionData = {
              requestId: requestId,
              position: {
                line: position.lineNumber,
                character: position.column,
              },
              triggerCharacter: triggerChar,
              code: model.getValue(),
            };
            editorBackend.handle_completion_request(JSON.stringify(completionData));
          } catch (_error) {
            clearTimeout(timeoutId);
            pendingCompletionRequests.delete(requestId);
            resolve({ suggestions: [] });
          }
        } else {
          clearTimeout(timeoutId);
          pendingCompletionRequests.delete(requestId);
          resolve({ suggestions: [] });
        }
      });
    },
    triggerCharacters: [".", "(", "[", ",", ":"],
  });
};

// Store pending hover requests
const pendingHoverRequests = new Map();

// Store pending completion requests
const pendingCompletionRequests = new Map();

// Function to be called from Python backend
window.showHover = (requestId, content) => {
  const request = pendingHoverRequests.get(requestId);
  if (request) {
    clearTimeout(request.timeoutId);
    request.resolve({
      contents: content,
    });
    pendingHoverRequests.delete(requestId);
  }
};

// Function to be called from Python backend for completions
window.showCompletions = (requestId, completions) => {
  const request = pendingCompletionRequests.get(requestId);
  if (request) {
    clearTimeout(request.timeoutId);
    request.resolve({
      suggestions: completions,
    });
    pendingCompletionRequests.delete(requestId);
  }
};

const registerHoverProvider = () => {
  monaco.languages.registerHoverProvider("python", {
    provideHover: async (model, position) => {
      // Get the word at the current position
      const word = model.getWordAtPosition(position);

      if (!word) {
        return null;
      }

      const requestId = Date.now();

      return new Promise((resolve, reject) => {
        // Timeout after 2 seconds
        const timeoutId = setTimeout(() => {
          if (pendingHoverRequests.has(requestId)) {
            pendingHoverRequests.delete(requestId);
            resolve(null);
          }
        }, 2000);

        pendingHoverRequests.set(requestId, { resolve, reject, timeoutId });

        const hoverData = {
          requestId: requestId,
          position: {
            line: position.lineNumber,
            character: position.column,
          },
        };

        if (editorBackend?.handle_hover) {
          try {
            editorBackend.handle_hover(JSON.stringify(hoverData));
          } catch {
            clearTimeout(timeoutId);
            pendingHoverRequests.delete(requestId);
            resolve(null);
            return;
          }
        } else {
          clearTimeout(timeoutId);
          pendingHoverRequests.delete(requestId);
          resolve(null);
          return;
        }
      });
    },
  });
};

// Set up content change handling; debouncing is handled in the Python backend.
const setupContentChangeHandling = () => {
  editor.onDidChangeModelContent(() => {
    setModified(true);
    if (webChannelReady && editorBackend) {
      editorBackend.code_changed(editor.getValue());
    }
  });

  // Track cursor position changes
  editor.onDidChangeCursorPosition((e) => {
    if (webChannelReady && editorBackend) {
      editorBackend.cursor_position_changed(e.position.lineNumber, e.position.column);
    }
  });
};

// Update editor diagnostics with linting results
const updateEditorDiagnostics = (diagnostics) => {
  if (!monacoReady || !editor) {
    console.warn("Editor not ready for diagnostics update.");
    return;
  }

  try {
    monaco.editor.setModelMarkers(editor.getModel(), "ruff", diagnostics);
    currentDiagnostics = diagnostics;
    console.debug(`Updated editor diagnostics: ${diagnostics.length} issues`);
  } catch (error) {
    console.error("Error updating diagnostics:", error);
  }
};

// Function to set modification state
const setModified = (modified) => {
  if (modified !== isModified) {
    isModified = modified;
    console.debug("Content modification state changed:", isModified);
    if (editorBackend) {
      editorBackend.content_changed(isModified);
    }
  }
};

// Public API functions - explicitly assigned to window for global access
window.getLintingResults = () => currentDiagnostics;

window.setEditorContent = (content) => {
  if (monacoReady && editor) {
    editor.setValue(content);
  } else {
    console.warn("Editor not ready for content setting.");
  }
};

window.getEditorContent = () => {
  if (monacoReady && editor) {
    return editor.getValue();
  } else {
    console.warn("Editor not ready for content retrieval.");
    return "";
  }
};

// Function to set modification state from Python
window.setModificationState = (modified) => {
  setModified(modified);
};

// Function to check if content is modified (for external access)
window.isModified = () => isModified;

// Line highlighting utility functions
window.highlightLine = (lineNumber) => {
  if (!editor) {
    console.warn("Editor not ready to highlight a line.");
    return;
  }

  // Remove existing line highlighting
  if (window.currentLineHighlight) {
    window.currentLineHighlight = editor.deltaDecorations(window.currentLineHighlight, []);
  }

  // Get theme colors
  const theme = editor._themeService.getColorTheme();
  const backgroundColor =
    theme.getColor("editor.lineHighlightBackground") ||
    theme.getColor("editor.selectionHighlightBackground");
  const borderColor =
    theme.getColor("editorLineNumber.activeForeground") || theme.getColor("focusBorder");

  // Update CSS variables with theme colors
  document.documentElement.style.setProperty("--highlight-bg", backgroundColor);
  document.documentElement.style.setProperty("--highlight-border", borderColor);

  // Add new line highlighting using theme colors
  window.currentLineHighlight = editor.deltaDecorations(
    [],
    [
      {
        range: new monaco.Range(lineNumber, 1, lineNumber, 1),
        options: {
          isWholeLine: true,
          className: "highlighted-line",
          linesDecorationsClassName: "highlighted-line-decoration",
        },
      },
    ],
  );

  // Scroll to the highlighted line
  editor.revealLineInCenter(lineNumber);
};

window.clearLineHighlight = () => {
  if (editor && window.currentLineHighlight) {
    window.currentLineHighlight = editor.deltaDecorations(window.currentLineHighlight, []);
  }
};

// Function to enable/disable tab completion
window.enableTabCompletion = (enable) => {
  if (!editor) {
    console.warn("Editor not ready for tab completion setting.");
    return;
  }

  editor.updateOptions({
    tabCompletion: enable ? "on" : "off",
    acceptSuggestionOnEnter: enable ? "on" : "off",
    quickSuggestions: enable,
  });
};

// Function to insert text at cursor position
window.insertText = (text) => {
  if (!editor) {
    console.warn("Editor not ready for text insertion.");
    return;
  }

  return editor.executeEdits("insertText", [
    {
      range: editor.getSelection(),
      text: text,
    },
  ]);
};

// Initialize the editor immediately
initializeWebChannel();
window.MONACO_PORT = resolveMonacoPort();

const loadMonacoLoader = () => {
  if (window.require && typeof window.require.config === "function") {
    initializeMonacoEditor();
    return;
  }

  if (monacoLoaderRequested) {
    return;
  }

  const loaderScript = document.createElement("script");
  loaderScript.src = `http://localhost:${window.MONACO_PORT}/min/vs/loader.js`;
  loaderScript.onload = () => {
    monacoLoaderRequested = false;
    initializeMonacoEditor();
  };
  loaderScript.onerror = (error) => {
    monacoLoaderRequested = false;
    console.error("Failed to load Monaco loader:", error);
  };

  monacoLoaderRequested = true;
  document.head.appendChild(loaderScript);
};

loadMonacoLoader();

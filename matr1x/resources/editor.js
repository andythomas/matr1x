// Monaco Editor initialization and configuration for Python code editing
// This module handles editor setup, linting integration, and Qt WebChannel communication

// Module state
let editor;
let linter;
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

    // Initial linting
    triggerLinting();
  }
};

// Initialize QWebChannel
const initializeWebChannel = () => {
  new QWebChannel(qt.webChannelTransport, (channel) => {
    linter = channel.objects.linter;
    editorBackend = channel.objects.editor_backend;

    // Listen for linting results
    linter.lintingComplete.connect((diagnosticsJson) => {
      const diagnostics = JSON.parse(diagnosticsJson);
      updateEditorDiagnostics(diagnostics);
    });

    console.log("QWebChannel initialized, linter and editor backend connected");
    webChannelReady = true;
    initializeIfReady();
  });
};

// Initialize Monaco Editor
const initializeMonacoEditor = () => {
  if (monacoReady) {
    return;
  }

  require.config({ paths: { vs: `http://localhost:${window.MONACO_PORT}/min/vs` } });

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
    });

    // Register custom completion provider
    registerCustomCompletions();

    // Set up automatic linting on content changes
    setupContentChangeHandling();

    // Make editor globally available
    window.editor = editor;
    window.triggerLinting = triggerLinting;

    console.log("Monaco Editor initialized");
    monacoReady = true;
    initializeIfReady();
  });
};

// Register custom completion items for Python scripting
const registerCustomCompletions = () => {
  const customCompletions = [
    {
      label: "system",
      insertText: "system",
      kind: monaco.languages.CompletionItemKind.Property,
      documentation: "Represents the object of the current system.",
    },
    {
      label: "meta_data",
      insertText: "meta_data",
      kind: monaco.languages.CompletionItemKind.Property,
      documentation: "Dictionary containing metadata according to Dublin Core.",
    },
    {
      label: 'meta_data["creator"]',
      insertText: 'meta_data["creator"]',
      kind: monaco.languages.CompletionItemKind.Property,
      documentation: "The person performing this measurement.",
    },
    {
      label: 'meta_data["identifier"]',
      insertText: 'meta_data["identifier"]',
      kind: monaco.languages.CompletionItemKind.Property,
      documentation: "An identifier for the measurement, e.g. the sample name.",
    },
    {
      label: 'meta_data["relation"]',
      insertText: 'meta_data["relation"]',
      kind: monaco.languages.CompletionItemKind.Property,
      documentation: "Additonal information about the measurement identifier, e.g. an ancestor.",
    },
    {
      label: 'meta_data["description"]',
      insertText: 'meta_data["description"]',
      kind: monaco.languages.CompletionItemKind.Property,
      documentation: "Verbose information about the measurement.",
    },
    {
      label: "devs",
      insertText: "devs",
      kind: monaco.languages.CompletionItemKind.Property,
      documentation: "Dictionary of the connected devices.",
    },
    {
      label: "wait(duration, until, message, silent)",
      // biome-ignore lint/suspicious/noTemplateCurlyInString: literal value is desired
      insertText: 'wait(${1:0}, until=${2:None}, message="${3:}", silent=${4:10})',
      kind: monaco.languages.CompletionItemKind.Function,
      insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
      documentation:
        "Wait for either a duration or until a timestamp. " +
        "Also acts as a breakpoint to pause and abort the execution. " +
        "Print a message for wait period more than silent",
    },
    {
      label: "end_script(finished)",
      // biome-ignore lint/suspicious/noTemplateCurlyInString: literal value is desired
      insertText: "end_script(finished=${1:None})",
      kind: monaco.languages.CompletionItemKind.Function,
      insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
      documentation:
        "End script and mark as finished (True) or aborted (False) or query user (None).",
    },
    {
      label: "input(query, timeout, default_value)",
      // biome-ignore lint/suspicious/noTemplateCurlyInString: literal value is desired
      insertText: 'input("${1:query}", timeout=${2:float("inf")}, default_value="${3}")',
      kind: monaco.languages.CompletionItemKind.Function,
      insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
      documentation: "Prompts the user for input with an optional timeout and default reply.",
    },
    {
      label: "input_bool(query, timeout, default_value)",
      // biome-ignore lint/suspicious/noTemplateCurlyInString: literal value is desired
      insertText: 'input_bool("${1:query}", timeout=${2:float("inf")}, default_value="${3:yes}")',
      kind: monaco.languages.CompletionItemKind.Function,
      insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
      documentation:
        "Prompts the user for a yes/no input with an optional timeout and default reply.",
    },
    {
      label: "input_numerical(query, timeout, default_value, min_value, max_value, step, decimals)",
      insertText:
        // biome-ignore lint/suspicious/noTemplateCurlyInString: literal value is desired
        'input_numerical("${1:query}", timeout=${2:float("inf")}, ' +
        // biome-ignore lint/suspicious/noTemplateCurlyInString: literal value is desired
        "default_value=${3:0.0}, min_value=${4:-100e9}, max_value=${5:100e9}, " +
        // biome-ignore lint/suspicious/noTemplateCurlyInString: literal value is desired
        "step=${6:1.0}, decimals=${7:2})",
      kind: monaco.languages.CompletionItemKind.Function,
      insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
      documentation:
        "Prompts the user for numerical input with validation (min, max, step, decimals) " +
        "and optional default value and timeout.",
    },
    {
      label: "init_datafile(filename, comment, append, print_header, ntot)",
      insertText:
        // biome-ignore lint/suspicious/noTemplateCurlyInString: literal value is desired
        'init_datafile("${1:test}", comment="${2}", append=${3:False}, ' +
        // biome-ignore lint/suspicious/noTemplateCurlyInString: literal value is desired
        "print_header=${4:True}, ntot=${5:None})",
      kind: monaco.languages.CompletionItemKind.Function,
      insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
      documentation:
        "Initializes a new data file with optional comment, append mode, and header printing. " +
        "The total entry count is used to calculate the total measurement duration.",
    },
    {
      label: "measure_system(print_setpoint, print_data, print_telemetry)",
      insertText:
        // biome-ignore lint/suspicious/noTemplateCurlyInString: literal value is desired
        "measure_system(print_setpoint=${1:True}, print_data=${2:True}, " +
        // biome-ignore lint/suspicious/noTemplateCurlyInString: literal value is desired
        "print_telemetry=${3:True})",
      kind: monaco.languages.CompletionItemKind.Function,
      insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
      documentation:
        "Performs a system measurement with options to print setpoint, data, and telemetry.",
    },
    {
      label: "set_value(value_index, value)",
      // biome-ignore lint/suspicious/noTemplateCurlyInString: literal value is desired
      insertText: "set_value(${1:0}, ${2:0})",
      kind: monaco.languages.CompletionItemKind.Function,
      insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
      documentation:
        "Sets a system value by index (int). Please use 'help/system' for more information.",
    },
    {
      label: "set_value(name, value)",
      // biome-ignore lint/suspicious/noTemplateCurlyInString: literal value is desired
      insertText: 'set_value("${1:column}", ${2:0})',
      kind: monaco.languages.CompletionItemKind.Function,
      insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
      documentation:
        "Sets a system value by name (str). Please use 'help/system' for more information.",
    },
    {
      label: "read_value(value_index)",
      // biome-ignore lint/suspicious/noTemplateCurlyInString: literal value is desired
      insertText: "read_value(${1:0})",
      kind: monaco.languages.CompletionItemKind.Function,
      insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
      documentation:
        "Reads a system value by index (int). Please use 'help/system' for more information.",
    },
    {
      label: "read_value(name: str)",
      // biome-ignore lint/suspicious/noTemplateCurlyInString: literal value is desired
      insertText: 'read_value("${1:column}")',
      kind: monaco.languages.CompletionItemKind.Function,
      insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
      documentation:
        "Reads a system value by name (str). Please use 'help/system' for more information.",
    },
    {
      label: "trigger_value(value_index)",
      // biome-ignore lint/suspicious/noTemplateCurlyInString: literal value is desired
      insertText: "trigger_value(${1:0})",
      kind: monaco.languages.CompletionItemKind.Function,
      insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
      documentation:
        "Triggers a system value by index (int). Please use 'help/system' for more information.",
    },
    {
      label: "trigger_value(name)",
      // biome-ignore lint/suspicious/noTemplateCurlyInString: literal value is desired
      insertText: 'trigger_value("${1:column}")',
      kind: monaco.languages.CompletionItemKind.Function,
      insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
      documentation:
        "Triggers a system value by name (str). Please use 'help/system' for more information.",
    },
  ];

  monaco.languages.registerCompletionItemProvider("python", {
    provideCompletionItems: (model, position) => {
      const word = model.getWordUntilPosition(position);
      const range = new monaco.Range(
        position.lineNumber,
        word.startColumn,
        position.lineNumber,
        word.endColumn,
      );

      const suggestions = customCompletions.map((item) => ({
        ...item,
        range,
      }));

      return { suggestions };
    },
  });
};

// Set up content change handling and automatic linting
const LINTING_DELAY_MS = 1000;

const setupContentChangeHandling = () => {
  let changeTimeout;
  editor.onDidChangeModelContent(() => {
    // Mark as modified whenever content changes
    setModified(true);

    // Clear previous timeout
    if (changeTimeout) {
      clearTimeout(changeTimeout);
    }

    // Avoid too frequent calls
    changeTimeout = setTimeout(() => {
      triggerLinting();
    }, LINTING_DELAY_MS);
  });
};

// Trigger linting operation
const triggerLinting = () => {
  if (!webChannelReady || !monacoReady || !linter || !editor) {
    console.warn(
      "System not ready - WebChannel:",
      webChannelReady,
      "Monaco:",
      monacoReady,
      "Linter:",
      !!linter,
      "Editor:",
      !!editor,
    );
    return;
  }

  const code = editor.getValue();
  console.debug("Triggering linting for code length:", code.length);

  try {
    linter.lint_code(code);
  } catch (error) {
    console.error("Error during linting:", error);
  }
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
    triggerLinting();
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

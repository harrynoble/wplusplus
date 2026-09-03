/* W++ Playground front end.
 *
 * The editor is Monaco when it can be loaded, and a small built-in editor
 * otherwise, so the playground still works offline.  Both are wrapped in the
 * same tiny interface (getValue / setValue / focus / markError / clearError)
 * and the rest of the file does not care which one it got.
 *
 * Append ?editor=basic to the URL to force the built-in editor.
 */
(function () {
  'use strict';

  var MONACO_VERSION = '0.52.2';
  var MONACO_BASE = 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/' + MONACO_VERSION + '/min/vs';
  var MONACO_TIMEOUT_MS = 8000;

  var STARTER_SOURCE = [
    'cook greet(name):',
    '    yap("Hello, " + name)',
    '',
    'greet("World")',
    ''
  ].join('\n');

  var IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

  var el = {};
  var keywords = new Set();
  var reference = null;
  var examples = [];
  var editor = null;

  /* ------------------------------------------------------------ bootstrap */

  function boot() {
    [
      'examples-menu', 'examples-button', 'examples-list', 'docs-button', 'run-button',
      'run-shortcut', 'copy-button', 'reset-button', 'editor', 'splitter',
      'status', 'timing', 'sound-button', 'stop-button', 'clear-button',
      'output', 'docs-drawer',
      'drawer-body', 'drawer-close', 'drawer-scrim', 'toast', 'workspace'
    ].forEach(function (id) {
      el[camel(id)] = document.getElementById(id);
    });

    el.runShortcut.textContent = IS_MAC ? 'Cmd+Enter' : 'Ctrl+Enter';

    wireEvents();
    setupSound();
    loadReference();
    loadExamples();
    createEditor();
  }

  function camel(id) {
    return id.replace(/-([a-z])/g, function (_, c) { return c.toUpperCase(); });
  }

  /* ------------------------------------------------------------- the data */

  function loadReference() {
    fetch('/api/reference').then(toJson).then(function (data) {
      reference = data;
      keywords = new Set(Object.keys(data.keywords));
      if (editor && editor.refreshKeywords) editor.refreshKeywords();
      renderDocs();
    }).catch(function () { /* the editor still works without the docs */ });
  }

  function loadExamples() {
    fetch('/api/examples').then(toJson).then(function (data) {
      examples = data;
      renderExamplesMenu();
    }).catch(function () {
      el.examplesButton.disabled = true;
    });
  }

  function toJson(response) {
    if (!response.ok) throw new Error('HTTP ' + response.status);
    return response.json();
  }

  /* --------------------------------------------------------------- editor */

  function createEditor() {
    var forced = new URLSearchParams(location.search).get('editor');
    if (forced === 'basic') {
      editor = createBasicEditor();
      return;
    }
    loadMonaco().then(function (monaco) {
      editor = createMonacoEditor(monaco);
    }).catch(function () {
      editor = createBasicEditor();
      toast('Monaco unavailable - using the built-in editor');
    });
  }

  function loadMonaco() {
    return new Promise(function (resolve, reject) {
      var settled = false;
      var timer = setTimeout(function () {
        if (!settled) { settled = true; reject(new Error('timeout')); }
      }, MONACO_TIMEOUT_MS);

      var script = document.createElement('script');
      script.src = MONACO_BASE + '/loader.min.js';
      script.onerror = function () {
        if (!settled) { settled = true; clearTimeout(timer); reject(new Error('loader failed')); }
      };
      script.onload = function () {
        // Monaco's workers live on the CDN, so they need a same-origin shim.
        window.MonacoEnvironment = {
          getWorkerUrl: function () {
            return 'data:text/javascript;charset=utf-8,' + encodeURIComponent(
              "self.MonacoEnvironment={baseUrl:'" + MONACO_BASE + "/'};" +
              "importScripts('" + MONACO_BASE + "/base/worker/workerMain.js');"
            );
          }
        };
        window.require.config({ paths: { vs: MONACO_BASE } });
        window.require(['vs/editor/editor.main'], function () {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          resolve(window.monaco);
        }, function () {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          reject(new Error('editor.main failed'));
        });
      };
      document.head.appendChild(script);
    });
  }

  function createMonacoEditor(monaco) {
    monaco.languages.register({ id: 'wpp' });
    monaco.languages.setLanguageConfiguration('wpp', {
      comments: { lineComment: '#' },
      brackets: [['{', '}'], ['[', ']'], ['(', ')']],
      autoClosingPairs: [
        { open: '(', close: ')' }, { open: '[', close: ']' }, { open: '{', close: '}' },
        { open: '"', close: '"', notIn: ['string'] }, { open: "'", close: "'", notIn: ['string'] }
      ],
      // W++ blocks open with a colon, exactly like Python.
      onEnterRules: [{
        beforeText: /:\s*$/,
        action: { indentAction: monaco.languages.IndentAction.Indent }
      }]
    });

    setMonarch(monaco);

    monaco.editor.defineTheme('wpp-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [
        { token: 'comment', foreground: '5f6874', fontStyle: 'italic' },
        { token: 'keyword', foreground: 'b48ead' },
        { token: 'function', foreground: '7fa8d4' },
        { token: 'string', foreground: '97b982' },
        { token: 'number', foreground: 'd0a67d' },
        { token: 'operator', foreground: '93a1b1' },
        { token: 'delimiter', foreground: '93a1b1' },
        { token: 'identifier', foreground: 'dee3ea' }
      ],
      colors: {
        'editor.background': '#10141a',
        'editor.foreground': '#dee3ea',
        'editorGutter.background': '#10141a',
        'editorLineNumber.foreground': '#4a5461',
        'editorLineNumber.activeForeground': '#8a95a3',
        'editorCursor.foreground': '#dee3ea',
        'editor.selectionBackground': '#27405f',
        'editor.inactiveSelectionBackground': '#1d2b3c',
        'editor.lineHighlightBackground': '#141920',
        'editor.lineHighlightBorder': '#00000000',
        'editorIndentGuide.background1': '#1c232b',
        'editorIndentGuide.activeBackground1': '#2b343f',
        'editorWidget.background': '#141920',
        'editorWidget.border': '#2b343f',
        'editorBracketMatch.background': '#00000000',
        'editorBracketMatch.border': '#3b82f6',
        'scrollbarSlider.background': '#232a3388',
        'scrollbarSlider.hoverBackground': '#2b343fcc',
        'scrollbarSlider.activeBackground': '#2b343f'
      }
    });

    var instance = monaco.editor.create(el.editor, {
      value: STARTER_SOURCE,
      language: 'wpp',
      theme: 'wpp-dark',
      fontFamily: "'JetBrains Mono', ui-monospace, SFMono-Regular, Consolas, monospace",
      fontSize: 13,
      lineHeight: 20,
      tabSize: 4,
      insertSpaces: true,
      automaticLayout: true,
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      padding: { top: 12, bottom: 12 },
      renderLineHighlight: 'line',
      roundedSelection: false,
      cursorSmoothCaretAnimation: 'off',
      // Kept deliberately quiet: no popups while typing, no extra colours.
      quickSuggestions: false,
      suggestOnTriggerCharacters: false,
      bracketPairColorization: { enabled: false },
      overviewRulerLanes: 0,
      hideCursorInOverviewRuler: true,
      scrollbar: { verticalSliderSize: 8, horizontalSliderSize: 8, useShadows: false }
    });

    instance.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, run);

    var decorations = [];

    return {
      kind: 'monaco',
      getValue: function () { return instance.getValue(); },
      setValue: function (text) { instance.setValue(text); },
      focus: function () { instance.focus(); },
      refreshKeywords: function () { setMonarch(monaco); },
      markError: function (line) {
        if (!line) return;
        decorations = instance.deltaDecorations(decorations, [{
          range: new monaco.Range(line, 1, line, 1),
          options: {
            isWholeLine: true,
            className: 'error-line-highlight',
            linesDecorationsClassName: 'error-line-margin'
          }
        }]);
        instance.revealLineInCenterIfOutsideViewport(line);
      },
      clearError: function () { decorations = instance.deltaDecorations(decorations, []); }
    };
  }

  function setMonarch(monaco) {
    monaco.languages.setMonarchTokensProvider('wpp', {
      keywords: Array.from(keywords),
      tokenizer: {
        root: [
          [/#.*$/, 'comment'],
          [/"""/, { token: 'string', next: '@tripleDouble' }],
          [/'''/, { token: 'string', next: '@tripleSingle' }],
          [/"(?:[^"\\]|\\.)*"/, 'string'],
          [/'(?:[^'\\]|\\.)*'/, 'string'],
          [/"(?:[^"\\]|\\.)*$/, 'string.invalid'],
          [/'(?:[^'\\]|\\.)*$/, 'string.invalid'],
          [/\d+\.\d+/, 'number.float'],
          [/\d+/, 'number'],
          // A name after a dot is an attribute, never a keyword - the same rule
          // the translator applies, so the colours match what actually runs.
          [/(\.)([A-Za-z_]\w*)(?=\s*\()/, ['delimiter', 'function']],
          [/(\.)([A-Za-z_]\w*)/, ['delimiter', 'identifier']],
          // A name before "(" is a call or a definition, unless it is a keyword.
          [/[A-Za-z_]\w*(?=\s*\()/, { cases: { '@keywords': 'keyword', '@default': 'function' } }],
          [/[A-Za-z_]\w*/, { cases: { '@keywords': 'keyword', '@default': 'identifier' } }],
          [/[{}()[\]]/, 'delimiter'],
          [/[+\-*/%=<>!&|^~]+/, 'operator']
        ],
        tripleDouble: [[/"""/, { token: 'string', next: '@pop' }], [/./, 'string']],
        tripleSingle: [[/'''/, { token: 'string', next: '@pop' }], [/./, 'string']]
      }
    });
  }

  /* The offline editor: a textarea with a highlighted layer behind it. */
  function createBasicEditor() {
    el.editor.innerHTML =
      '<div class="fallback">' +
        '<div class="fallback-gutter"><div class="fallback-gutter-inner"></div></div>' +
        '<div class="fallback-scroll">' +
          '<pre class="fallback-highlight" aria-hidden="true"><code></code></pre>' +
          '<textarea class="fallback-input" spellcheck="false" autocomplete="off" ' +
            'autocapitalize="off" wrap="off" aria-label="W++ editor"></textarea>' +
        '</div>' +
      '</div>';

    var gutter = el.editor.querySelector('.fallback-gutter-inner');
    var scroll = el.editor.querySelector('.fallback-scroll');
    var pre = el.editor.querySelector('.fallback-highlight');
    var code = pre.querySelector('code');
    var input = el.editor.querySelector('.fallback-input');
    var errorLine = null;

    function sync() {
      var text = input.value;
      code.innerHTML = highlight(text, keywords);
      var lines = text.split('\n');
      gutter.innerHTML = lines.map(function (_, i) {
        var n = i + 1;
        return n === errorLine
          ? '<span class="tok-comment" style="color:var(--err)">' + n + '</span>'
          : String(n);
      }).join('\n');
      // The <pre> defines the scrollable area; the textarea is stretched to match.
      input.style.height = pre.scrollHeight + 'px';
      input.style.width = pre.scrollWidth + 'px';
    }

    input.addEventListener('input', sync);
    scroll.addEventListener('scroll', function () {
      gutter.style.transform = 'translateY(' + -scroll.scrollTop + 'px)';
    });

    input.addEventListener('keydown', function (event) {
      if (event.key === 'Tab') {
        event.preventDefault();
        insertAtCursor(input, '    ');
        sync();
        return;
      }
      if (event.key === 'Enter') {
        // Keep the current indentation, and add one level after a colon.
        var upto = input.value.slice(0, input.selectionStart);
        var current = /(^|\n)([ \t]*)[^\n]*$/.exec(upto);
        var indent = current ? current[2] : '';
        if (/:\s*$/.test(upto)) indent += '    ';
        event.preventDefault();
        insertAtCursor(input, '\n' + indent);
        sync();
      }
    });

    input.value = STARTER_SOURCE;
    sync();

    return {
      kind: 'basic',
      getValue: function () { return input.value; },
      setValue: function (text) { input.value = text; errorLine = null; sync(); },
      focus: function () { input.focus(); },
      refreshKeywords: sync,
      markError: function (line) { errorLine = line; sync(); },
      clearError: function () { errorLine = null; sync(); }
    };
  }

  function insertAtCursor(input, text) {
    var start = input.selectionStart;
    var end = input.selectionEnd;
    input.value = input.value.slice(0, start) + text + input.value.slice(end);
    input.selectionStart = input.selectionEnd = start + text.length;
  }

  /* A single-pass highlighter, used by the offline editor and the docs. */
  function highlight(code, words) {
    var pattern = /("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')|(#[^\n]*)|(\b\d+(?:\.\d+)?\b)|([A-Za-z_]\w*)|([+\-*/%=<>!&|^~]+)/g;
    var out = '';
    var last = 0;
    var match;

    while ((match = pattern.exec(code)) !== null) {
      out += escapeHtml(code.slice(last, match.index));
      var text = escapeHtml(match[0]);

      if (match[1]) {
        out += span('tok-string', text);
      } else if (match[2]) {
        out += span('tok-comment', text);
      } else if (match[3]) {
        out += span('tok-number', text);
      } else if (match[4]) {
        var afterDot = code[match.index - 1] === '.';
        if (!afterDot && words.has(match[0])) {
          out += span('tok-keyword', text);
        } else if (code[pattern.lastIndex] === '(') {
          out += span('tok-function', text);
        } else {
          out += text;
        }
      } else {
        out += span('tok-operator', text);
      }
      last = pattern.lastIndex;
    }

    return out + escapeHtml(code.slice(last));
  }

  function span(cls, text) { return '<span class="' + cls + '">' + text + '</span>'; }

  function escapeHtml(text) {
    return text.replace(/[&<>]/g, function (ch) {
      return ch === '&' ? '&amp;' : ch === '<' ? '&lt;' : '&gt;';
    });
  }

  /* ------------------------------------------------------------ execution
   *
   * A run is a session, because a W++ program can pause and ask for input.
   * POST /api/run starts it, an EventSource streams the ordered records the
   * worker produces, and POST /api/input feeds one line back when the program
   * blocks on dm().  Records arrive in program order, so the caret is always
   * drawn after the prompt that asked for it.
   */

  var session = null;                                  // the live run, if any
  var stream = { pre: null, node: null, caret: null };  // the output transcript

  function run() {
    if (!editor) return;
    stopSession();               // a second Run replaces the run in progress
    beginOutput();
    setStatus('running', 'Running...');
    el.timing.textContent = '';
    el.stopButton.hidden = false;
    editor.clearError();

    fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: editor.getValue() })
    })
      .then(toJson)
      .then(function (data) {
        session = { id: data.sessionId, stream: null, settled: false };
        listen(session);
      })
      .catch(function () {
        renderDisconnected();
        finishRun('error', 'Error');
      });
  }

  function listen(current) {
    var source = new EventSource('/api/stream?session=' + encodeURIComponent(current.id));
    current.stream = source;

    source.onmessage = function (message) {
      var record;
      try {
        record = JSON.parse(message.data);
      } catch (error) {
        return;
      }
      handleRecord(current, record);
    };

    source.onerror = function () {
      // EventSource reconnects on its own, which we never want here: either
      // the run is already over, or the connection is genuinely gone.
      source.close();
      if (current.settled) return;
      current.settled = true;
      removeCaret();
      renderDisconnected();
      finishRun('error', 'Error');
    };
  }

  function handleRecord(current, record) {
    if (record.event === 'stdout') {
      appendText(record.text);
      return;
    }
    if (record.event === 'stderr') {
      appendText(record.text, 'output-stderr');
      return;
    }
    if (record.event === 'input') {
      flushQueued();          // the prompt must be on screen under the caret
      showCaret(current);
      return;
    }
    if (record.event !== 'result') {
      return;
    }

    flushQueued();            // never lose the last chunk behind the result
    current.settled = true;
    if (current.stream) current.stream.close();
    removeCaret();

    if (record.error) {
      el.output.appendChild(errorBlock(record.error));
      if (record.error.line) editor.markError(record.error.line);
      playErrorSound();
    } else if (!hasOutput()) {
      el.output.appendChild(note('Program finished without producing output.'));
    }

    el.timing.textContent = record.durationMs + ' ms';
    if (record.error) {
      finishRun('error', 'Error');
    } else if (record.stopped) {
      finishRun('stopped', 'Stopped');
    } else {
      finishRun('completed', 'Completed');
    }
    scrollOutput();
  }

  function finishRun(state, label) {
    setStatus(state, label);
    el.stopButton.hidden = true;
    el.output.classList.remove('is-waiting');
    session = null;
  }

  function stopSession() {
    var current = session;
    if (!current) return;
    session = null;
    current.settled = true;
    if (current.stream) current.stream.close();
    removeCaret();
    el.stopButton.hidden = true;
    el.output.classList.remove('is-waiting');
    // Best effort: the server also ends a run when its stream drops.
    fetch('/api/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session: current.id })
    }).catch(function () {});
  }

  function stopFromButton() {
    if (!session) return;
    stopSession();
    setStatus('stopped', 'Stopped');
  }

  function setStatus(state, label) {
    el.status.dataset.state = state;
    el.status.textContent = label || 'Ready';
  }

  /* ------------------------------------------------------------ error sound
   *
   * A failing program plays audio/fah.mp3 unless the sound is muted. The
   * choice is remembered per browser. Browsers only allow audio after the
   * user has interacted with the page, which pressing Run satisfies.
   */

  var MUTE_KEY = 'wpp.muted';
  var sound = null;
  var muted = false;

  function setupSound() {
    muted = readMuted();
    applySoundButton();

    try {
      sound = new Audio('/audio/fah.mp3');
      sound.preload = 'auto';
    } catch (error) {
      sound = null;   // no audio support: the toggle simply does nothing
    }
  }

  function readMuted() {
    try {
      return localStorage.getItem(MUTE_KEY) === '1';
    } catch (error) {
      return false;   // private mode, or storage blocked
    }
  }

  function writeMuted(value) {
    try {
      localStorage.setItem(MUTE_KEY, value ? '1' : '0');
    } catch (error) {
      /* remembering it is a convenience, not a requirement */
    }
  }

  function applySoundButton() {
    var label = muted ? 'Unmute the error sound' : 'Mute the error sound';
    el.soundButton.setAttribute('aria-pressed', muted ? 'false' : 'true');
    el.soundButton.setAttribute('aria-label', label);
    el.soundButton.title = label;
  }

  function toggleSound() {
    muted = !muted;
    writeMuted(muted);
    applySoundButton();
    toast(muted ? 'Error sound muted' : 'Error sound on');
    if (!muted) playErrorSound();   // confirm it works, and that it is audible
  }

  function playErrorSound() {
    if (muted || !sound) return;
    try {
      sound.pause();
      sound.currentTime = 0;
      var started = sound.play();
      // play() rejects when the browser blocks autoplay; that is not an error
      // worth showing, so it is swallowed.
      if (started && typeof started.catch === 'function') {
        started.catch(function () {});
      }
    } catch (error) {
      /* nothing to do: the skill issue is already on screen */
    }
  }

  /* ----------------------------------------------- the output as a terminal */

  function beginOutput() {
    resetQueue();
    el.output.textContent = '';
    stream.pre = document.createElement('pre');
    stream.pre.className = 'output-stream';
    stream.node = null;
    stream.caret = null;
    el.output.appendChild(stream.pre);
  }

  /* Output is applied once per animation frame rather than once per record.
     A program printing flat out used to touch the DOM - and read scrollHeight,
     forcing a synchronous layout - on every single record, which locked the
     tab up hard enough that the page had to be reloaded. */
  var queued = [];
  var frame = null;

  function appendText(text, cls) {
    if (!text || !stream.pre) return;
    queued.push({ text: text, cls: cls });
    if (frame === null) {
      frame = requestAnimationFrame(drainQueued);
    }
  }

  function drainQueued() {
    frame = null;
    if (!stream.pre || !queued.length) {
      queued = [];
      return;
    }

    var batch = queued;
    queued = [];

    // The caret must stay last, so detach it while we write and put it back.
    var caret = stream.caret;
    if (caret && caret.parentNode === stream.pre) {
      stream.pre.removeChild(caret);
      stream.node = null;
    }

    for (var i = 0; i < batch.length; i++) {
      writeChunk(batch[i].text, batch[i].cls);
    }

    if (caret) {
      stream.pre.appendChild(caret);
      stream.node = null;
    }
    scrollOutput();
  }

  /* Appends to a trailing text node, which leaves earlier styled runs alone. */
  function writeChunk(text, cls) {
    if (cls) {
      var span = document.createElement('span');
      span.className = cls;
      span.textContent = text;
      stream.pre.appendChild(span);
      stream.node = null;
      return;
    }
    if (!stream.node) {
      stream.node = document.createTextNode('');
      stream.pre.appendChild(stream.node);
    }
    stream.node.appendData(text);
  }

  function resetQueue() {
    if (frame !== null) {
      cancelAnimationFrame(frame);
      frame = null;
    }
    queued = [];
  }

  /* Ordering matters more than batching when a prompt or a result arrives. */
  function flushQueued() {
    if (frame !== null) {
      cancelAnimationFrame(frame);
      frame = null;
    }
    drainQueued();
  }

  function hasOutput() {
    return !!stream.pre && stream.pre.textContent.length > 0;
  }

  /* The caret is a real input living in the output flow, immediately after
     whatever prompt the program just printed. */
  function showCaret(current) {
    if (!stream.pre) return;
    removeCaret();

    var caret = document.createElement('input');
    caret.type = 'text';
    caret.className = 'term-input';
    caret.setAttribute('spellcheck', 'false');
    caret.setAttribute('autocomplete', 'off');
    caret.setAttribute('autocapitalize', 'off');
    caret.setAttribute('aria-label', 'Program input');
    caret.style.width = '2ch';

    caret.addEventListener('input', function () {
      caret.style.width = Math.max(2, caret.value.length + 1) + 'ch';
    });

    caret.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter') return;
      event.preventDefault();
      event.stopPropagation();   // Enter here is not the global run shortcut
      submitCaret(current, caret);
    });

    stream.pre.appendChild(caret);
    stream.node = null;
    stream.caret = caret;

    el.output.classList.add('is-waiting');
    setStatus('input', 'Waiting for input');
    caret.focus();
    scrollOutput();
  }

  function submitCaret(current, caret) {
    var text = caret.value;
    removeCaret();
    // Echo the typed line, the way a terminal shows your own keystrokes.
    appendText(text + '\n');
    el.output.classList.remove('is-waiting');
    setStatus('running', 'Running...');

    fetch('/api/input', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session: current.id, text: text })
    })
      .then(toJson)
      .catch(function () {
        if (current.settled) return;
        current.settled = true;
        if (current.stream) current.stream.close();
        renderDisconnected();
        finishRun('error', 'Error');
      });
  }

  function removeCaret() {
    if (stream.caret && stream.caret.parentNode) {
      stream.caret.parentNode.removeChild(stream.caret);
    }
    stream.caret = null;
    stream.node = null;
  }

  function scrollOutput() {
    el.output.scrollTop = el.output.scrollHeight;
  }

  function errorBlock(error) {
    var box = document.createElement('div');
    box.className = 'output-error';

    box.appendChild(node('div', 'error-label', 'Error'));
    box.appendChild(node('div', 'error-message', error.message));

    if (error.line) {
      box.appendChild(node('div', 'error-line', 'Line ' + error.line));
    }
    if (error.source_line) {
      box.appendChild(node('div', 'error-source', error.source_line));
    }
    if (error.detail) {
      box.appendChild(node('div', 'error-detail', error.detail));
    }

    return box;
  }

  function renderDisconnected() {
    resetQueue();
    el.output.textContent = '';
    stream.pre = null;
    stream.node = null;
    stream.caret = null;
    var box = document.createElement('div');
    box.className = 'output-error';
    box.appendChild(node('div', 'error-label', 'Error'));
    box.appendChild(node('div', 'error-message', 'The playground server is not responding.'));
    box.appendChild(node('div', 'error-detail', 'Start it again with: python playground/server.py'));
    el.output.appendChild(box);
    playErrorSound();
  }

  function note(text) { return node('p', 'output-empty', text); }

  function node(tag, cls, text) {
    var element = document.createElement(tag);
    element.className = cls;
    element.textContent = text;
    return element;
  }

  function clearOutput() {
    stopSession();
    resetQueue();
    el.output.textContent = '';
    stream.pre = null;
    stream.node = null;
    stream.caret = null;
    el.output.appendChild(note('Run your W++ program to see the result here.'));
    el.timing.textContent = '';
    setStatus('ready', 'Ready');
    if (editor) editor.clearError();
  }

  /* -------------------------------------------------------------- menus */

  function renderExamplesMenu() {
    el.examplesList.textContent = '';
    examples.forEach(function (example) {
      var item = document.createElement('li');
      var button = document.createElement('button');
      button.className = 'menu-item';
      button.type = 'button';
      button.setAttribute('role', 'menuitem');
      button.textContent = example.name;
      button.addEventListener('click', function () {
        loadExample(example);
        closeMenu();
      });
      item.appendChild(button);
      el.examplesList.appendChild(item);
    });
  }

  function loadExample(example) {
    if (!editor) return;
    editor.setValue(example.source);
    clearOutput();
    editor.focus();
  }

  function openMenu() {
    el.examplesList.hidden = false;
    el.examplesButton.setAttribute('aria-expanded', 'true');
  }

  function closeMenu() {
    el.examplesList.hidden = true;
    el.examplesButton.setAttribute('aria-expanded', 'false');
  }

  /* --------------------------------------------------------------- docs */

  function renderDocs() {
    if (!reference) return;
    var body = el.drawerBody;
    body.textContent = '';

    body.appendChild(section('About', function (host) {
      host.appendChild(node('p', 'doc-text',
        'W++ is Python with a different vocabulary. Your program is translated ' +
        'keyword by keyword into Python and executed, so every Python expression ' +
        'you already know still works.'));
      var sample = document.createElement('pre');
      sample.className = 'doc-code';
      sample.innerHTML = highlight(
        'cook fizzbuzz(limit):\n' +
        '    spam i in range(1, limit + 1):\n' +
        '        bet i % 15 == 0:\n' +
        '            yap("FizzBuzz")\n' +
        '        nah:\n' +
        '            yap(i)\n', keywords);
      host.appendChild(sample);
    }));

    body.appendChild(section('Keywords', function (host) {
      var table = document.createElement('table');
      table.className = 'doc-table';
      table.innerHTML = '<thead><tr><th>W++</th><th>Python</th><th>Category</th></tr></thead>';
      var tbody = document.createElement('tbody');
      Object.keys(reference.keywords).forEach(function (word) {
        var row = document.createElement('tr');
        row.appendChild(cell('col-wpp', word, true));
        row.appendChild(cell('', reference.keywords[word], true));
        row.appendChild(cell('', reference.categories[word] || '', false));
        tbody.appendChild(row);
      });
      table.appendChild(tbody);
      host.appendChild(table);
    }));

    body.appendChild(section('Errors', function (host) {
      host.appendChild(node('p', 'doc-text',
        'Python exceptions are reported using the W++ Skill Issue Protocol, with ' +
        'the line they came from.'));
      var table = document.createElement('table');
      table.className = 'doc-table';
      table.innerHTML = '<thead><tr><th>Exception</th><th>Message</th></tr></thead>';
      var tbody = document.createElement('tbody');
      Object.keys(reference.skillIssues).forEach(function (name) {
        var row = document.createElement('tr');
        row.appendChild(cell('', name, true));
        row.appendChild(cell('', reference.skillIssues[name], false));
        tbody.appendChild(row);
      });
      table.appendChild(tbody);
      host.appendChild(table);
    }));

    body.appendChild(section('Command line', function (host) {
      host.appendChild(node('p', 'doc-text', 'The same interpreter runs from a terminal:'));
      host.appendChild(node('pre', 'doc-code', 'python wpp.py examples/fizzbuzz.wpp'));
      host.appendChild(node('p', 'doc-text',
        'Use --emit to print the generated Python, and --keywords for this table.'));
    }));
  }

  function section(title, build) {
    var wrapper = document.createElement('section');
    wrapper.className = 'doc-section';
    wrapper.appendChild(node('h3', 'doc-heading', title));
    build(wrapper);
    return wrapper;
  }

  function cell(cls, text, mono) {
    var td = document.createElement('td');
    if (cls) td.className = cls;
    if (mono) {
      var codeEl = document.createElement('code');
      codeEl.textContent = text;
      td.appendChild(codeEl);
    } else {
      td.textContent = text;
    }
    return td;
  }

  function openDrawer() {
    el.docsDrawer.hidden = false;
    el.drawerScrim.hidden = false;
    el.docsButton.setAttribute('aria-expanded', 'true');
    el.drawerClose.focus();
  }

  function closeDrawer() {
    el.docsDrawer.hidden = true;
    el.drawerScrim.hidden = true;
    el.docsButton.setAttribute('aria-expanded', 'false');
  }

  /* ------------------------------------------------------------ splitter */

  function wireSplitter() {
    var dragging = false;

    el.splitter.addEventListener('mousedown', function (event) {
      if (window.innerWidth <= 860) return;
      dragging = true;
      event.preventDefault();
      document.body.style.cursor = 'col-resize';
    });

    window.addEventListener('mousemove', function (event) {
      if (!dragging) return;
      var bounds = el.workspace.getBoundingClientRect();
      var left = Math.min(Math.max(event.clientX - bounds.left, 280), bounds.width - 280);
      el.workspace.style.gridTemplateColumns = left + 'px 1px 1fr';
    });

    window.addEventListener('mouseup', function () {
      if (!dragging) return;
      dragging = false;
      document.body.style.cursor = '';
    });

    el.splitter.addEventListener('keydown', function (event) {
      var step = event.key === 'ArrowLeft' ? -32 : event.key === 'ArrowRight' ? 32 : 0;
      if (!step) return;
      event.preventDefault();
      var bounds = el.workspace.getBoundingClientRect();
      var current = el.paneWidth || bounds.width * 0.55;
      el.paneWidth = Math.min(Math.max(current + step, 280), bounds.width - 280);
      el.workspace.style.gridTemplateColumns = el.paneWidth + 'px 1px 1fr';
    });
  }

  /* --------------------------------------------------------------- misc */

  var toastTimer = null;

  function toast(message) {
    el.toast.textContent = message;
    el.toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.toast.hidden = true; }, 3200);
  }

  function copySource() {
    if (!editor) return;
    var text = editor.getValue();
    var done = function () { toast('Copied to clipboard'); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { toast('Copy failed'); });
    } else {
      toast('Copy is unavailable in this browser');
    }
  }

  function wireEvents() {
    el.runButton.addEventListener('click', run);
    el.stopButton.addEventListener('click', stopFromButton);
    el.soundButton.addEventListener('click', toggleSound);
    el.clearButton.addEventListener('click', clearOutput);
    el.copyButton.addEventListener('click', copySource);
    el.resetButton.addEventListener('click', function () {
      if (!editor) return;
      editor.setValue(STARTER_SOURCE);
      clearOutput();
      editor.focus();
    });

    // Clicking anywhere in the output focuses the caret, like a terminal does.
    el.output.addEventListener('mousedown', function (event) {
      if (!stream.caret || event.target === stream.caret) return;
      if (window.getSelection && String(window.getSelection()).length) return;
      event.preventDefault();
      stream.caret.focus();
    });

    el.examplesButton.addEventListener('click', function (event) {
      event.stopPropagation();
      if (el.examplesList.hidden) openMenu(); else closeMenu();
    });
    document.addEventListener('click', function (event) {
      if (!el.examplesMenu.contains(event.target)) closeMenu();
    });

    el.docsButton.addEventListener('click', openDrawer);
    el.drawerClose.addEventListener('click', closeDrawer);
    el.drawerScrim.addEventListener('click', closeDrawer);

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') { closeMenu(); closeDrawer(); }
      // Ctrl/Cmd+Enter runs from anywhere on the page.
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        event.preventDefault();
        run();
      }
    });

    wireSplitter();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();

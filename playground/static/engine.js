/* Where W++ actually runs.
 *
 * The playground has two engines and the rest of the page cannot tell them
 * apart, because both emit the same records:
 *
 *   {event: "stdout", text}    program output
 *   {event: "stderr", text}    program output on stderr
 *   {event: "input",  prompt}  the program is waiting for a line
 *   {event: "reset"}           clear the transcript and start it again
 *   {event: "result", exitCode, error, durationMs, timedOut, stopped}
 *
 * The server engine talks to playground/server.py, which runs each program in
 * a child process - the fast path for local work.
 *
 * The browser engine runs the compiler itself, under Pyodide, in a worker.
 * That is what allows the playground to be deployed as static files with no
 * backend at all.
 *
 * Which one is used is decided at load time by asking the server if it is
 * there, so the same files work locally and on a static host.
 */
(function () {
  'use strict';

  var COMPUTE_LIMIT_MS = 10000;   // matches the server's budget

  /* ------------------------------------------------------------ detection */

  function detect() {
    // A short timeout: on a static host there is nothing listening and we
    // should not make the user wait to find out.
    return new Promise(function (resolve) {
      var settled = false;
      var timer = setTimeout(function () {
        if (!settled) { settled = true; resolve('browser'); }
      }, 2500);

      fetch('/api/reference', { method: 'GET' })
        .then(function (response) {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          resolve(response.ok ? 'server' : 'browser');
        })
        .catch(function () {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          resolve('browser');
        });
    });
  }

  /* --------------------------------------------------------- server engine */

  function ServerEngine() {
    this.kind = 'server';
  }

  ServerEngine.prototype.reference = function () {
    return fetch('/api/reference').then(toJson);
  };

  ServerEngine.prototype.examples = function () {
    return fetch('/api/examples').then(toJson);
  };

  ServerEngine.prototype.start = function (source, onRecord, onFailure) {
    var run = { stream: null, id: null, settled: false };

    fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source: source })
    })
      .then(toJson)
      .then(function (data) {
        run.id = data.sessionId;
        var stream = new EventSource(
          '/api/stream?session=' + encodeURIComponent(run.id));
        run.stream = stream;

        stream.onmessage = function (message) {
          var record;
          try {
            record = JSON.parse(message.data);
          } catch (error) {
            return;
          }
          if (record.event === 'result') {
            run.settled = true;
            stream.close();
          }
          onRecord(record);
        };

        stream.onerror = function () {
          stream.close();
          if (run.settled) return;
          run.settled = true;
          onFailure();
        };
      })
      .catch(function () {
        if (run.settled) return;
        run.settled = true;
        onFailure();
      });

    run.sendInput = function (text) {
      return fetch('/api/input', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session: run.id, text: text })
      }).then(toJson);
    };

    run.stop = function () {
      run.settled = true;
      if (run.stream) run.stream.close();
      if (!run.id) return;
      fetch('/api/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session: run.id })
      }).catch(function () {});
    };

    return run;
  };

  /* -------------------------------------------------------- browser engine */

  function BrowserEngine() {
    this.kind = 'browser';
    this.sources = null;
    this.worker = null;
    this.ready = null;
  }

  BrowserEngine.prototype.load = function () {
    var engine = this;

    // Only reuse the cached promise while its worker is still alive. Stopping
    // a runaway loop means terminating the worker, and without this check the
    // resolved promise for that dead worker would be handed out again and
    // every later run would fail.
    if (this.ready && this.worker) return this.ready;

    var sources = this.sources
      ? Promise.resolve(this.sources)                 // fetched once, kept
      : fetch('wpp-sources.json').then(toJson);

    this.ready = sources.then(function (loaded) {
      engine.sources = loaded;
      return engine.spawn();
    });
    return this.ready;
  };

  /* A fresh worker, booted with the compiler. */
  BrowserEngine.prototype.spawn = function () {
    var engine = this;
    return new Promise(function (resolve, reject) {
      var worker = new Worker('wpp-worker.js');
      var booted = false;

      worker.onmessage = function (event) {
        var record = event.data;
        if (record.event === 'ready') {
          booted = true;
          engine.worker = worker;
          resolve(worker);
          return;
        }
        if (record.event === 'bootFailed') {
          reject(new Error(record.detail || 'the engine could not start'));
          return;
        }
        if (engine.onRecord) engine.onRecord(record);
      };

      worker.onerror = function (error) {
        if (!booted) {
          reject(new Error((error && error.message) || 'the engine could not start'));
        }
      };

      worker.postMessage({ type: 'boot', sources: engine.sources });
    });
  };

  BrowserEngine.prototype.reference = function () {
    return this.load().then(function () {
      return this.sources.reference;
    }.bind(this));
  };

  BrowserEngine.prototype.examples = function () {
    return this.load().then(function () {
      return this.sources.examples;
    }.bind(this));
  };

  BrowserEngine.prototype.start = function (source, onRecord, onFailure) {
    var engine = this;
    var run = {
      settled: false,
      answers: [],
      started: 0,
      timer: null,
      computeMs: 0,
    };

    function clearTimer() {
      if (run.timer !== null) {
        clearTimeout(run.timer);
        run.timer = null;
      }
    }

    function finish(record) {
      clearTimer();
      run.settled = true;
      engine.onRecord = null;
      record.durationMs = Math.round(run.computeMs);
      onRecord(record);
    }

    /* A runaway loop cannot be asked to stop, so the worker is discarded. */
    function killAndReplace(record) {
      if (engine.worker) {
        engine.worker.terminate();
        engine.worker = null;
      }
      engine.ready = null;
      finish(record);
      // Start the replacement now, in the background, so it is warm by the
      // time the user presses Run again.
      engine.load().catch(function () {});
    }

    function beginAttempt() {
      run.started = (self.performance || Date).now();
      clearTimer();
      run.timer = setTimeout(function () {
        if (run.settled) return;
        killAndReplace({
          event: 'result',
          exitCode: 130,
          timedOut: true,
          error: {
            message: engine.skillIssue('KeyboardInterrupt'),
            exception: 'KeyboardInterrupt',
            path: 'main.wpp', line: null, source_line: null,
            detail: 'Stopped after ' + (COMPUTE_LIMIT_MS / 1000) +
                    ' seconds of running.',
          },
        });
      }, COMPUTE_LIMIT_MS);

      engine.worker.postMessage({
        type: 'run', source: source, answers: run.answers,
      });
    }

    engine.onRecord = function (record) {
      if (run.settled) return;

      if (record.event === 'input') {
        // Waiting for the user does not count against the compute budget,
        // which is the same rule the server applies.
        run.computeMs += (self.performance || Date).now() - run.started;
        clearTimer();
        onRecord(record);
        return;
      }

      if (record.event === 'result') {
        run.computeMs += (self.performance || Date).now() - run.started;
        finish(record);
        return;
      }

      onRecord(record);
    };

    engine.load().then(function () {
      if (run.settled) return;
      beginAttempt();
    }).catch(function () {
      run.settled = true;
      onFailure();
    });

    run.sendInput = function (text) {
      run.answers.push(text);
      beginAttempt();               // replay, now with one more answer
      return Promise.resolve({ ok: true });
    };

    run.stop = function () {
      if (run.settled) return;
      killAndReplace({ event: 'result', exitCode: 130, stopped: true,
                       error: null });
    };

    return run;
  };

  BrowserEngine.prototype.skillIssue = function (name) {
    var table = this.sources && this.sources.reference &&
                this.sources.reference.skillIssues;
    return (table && table[name]) || name;
  };

  /* ---------------------------------------------------------------- shared */

  function toJson(response) {
    if (!response.ok) throw new Error('HTTP ' + response.status);
    return response.json();
  }

  function create() {
    return detect().then(function (kind) {
      return kind === 'server' ? new ServerEngine() : new BrowserEngine();
    });
  }

  window.WppEngine = { create: create, ServerEngine: ServerEngine,
                       BrowserEngine: BrowserEngine };
})();

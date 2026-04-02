/**
 * Клиент теста голоса: WebSocket + Pipecat Protobuf + Web Audio API.
 * Вход: PCM 16-bit mono 16 kHz. Выход: PCM с сервера (ожидаем 24 kHz mono).
 * Сокет: тот же origin (Nginx проксирует на бэкенд).
 * TODO: При устаревании ScriptProcessorNode перейти на AudioWorklet для захвата аудио.
 */
(function () {
  "use strict";

  var TARGET_INPUT_HZ = 16000;
  var DEFAULT_OUTPUT_HZ = 24000;
  var SPEAKING_RESET_MS = 400;

  var root = null;
  var FrameType = null;
  var ws = null;
  var mediaStream = null;
  var audioContext = null;
  var playbackContext = null;
  var processor = null;
  var sourceNode = null;
  var protoReady = false;
  var protoLoadPromise = null;

  var nextPlayTime = 0;
  var speakingTimer = null;

  var elStatus = null;
  var elStatusText = null;
  var elLog = null;
  var elStart = null;
  var elEnd = null;
  var elSession = null;
  var elMode = null;
  var elScenario = null;
  var elScenarioField = null;
  var elManager = null;
  var elTranscriptBody = null;

  var API_SCENARIOS = "/api/scenarios";

  function nowLine() {
    return new Date().toISOString().replace("T", " ").slice(0, 19);
  }

  function clearTranscript() {
    if (elTranscriptBody) elTranscriptBody.innerHTML = "";
  }

  function appendUserTranscript(text) {
    if (!elTranscriptBody || !text) return;
    var line = document.createElement("div");
    line.className = "voice-transcript__line";
    var meta = document.createElement("span");
    meta.className = "voice-transcript__meta";
    meta.textContent = "Вы";
    var body = document.createElement("div");
    body.className = "voice-transcript__text";
    body.textContent = text;
    line.appendChild(meta);
    line.appendChild(body);
    elTranscriptBody.appendChild(line);
    elTranscriptBody.scrollTop = elTranscriptBody.scrollHeight;
  }

  function log(msg, level) {
    if (!elLog) return;
    var line = document.createElement("p");
    line.className = "log-box__line";
    if (level === "warn") line.classList.add("log-box__line--warn");
    if (level === "err") line.classList.add("log-box__line--err");
    if (level === "info" || !level) line.classList.add("log-box__line--info");
    line.textContent = "[" + nowLine() + "] " + msg;
    elLog.appendChild(line);
    elLog.scrollTop = elLog.scrollHeight;
  }

  function setStatus(state) {
    if (!elStatus || !elStatusText) return;
    elStatus.className = "status-badge status-badge--" + state;
    elStatus.setAttribute("data-state", state);
    var labels = {
      disconnected: "Отключено",
      connected: "Подключено",
      listening: "Слушаем",
      speaking: "Говорит агент",
      error: "Ошибка",
    };
    elStatusText.textContent = labels[state] || state;
  }

  function downsampleToInt16(inputFloat32, inputRate, outputRate) {
    var i;
    if (inputRate === outputRate) {
      var same = new Int16Array(inputFloat32.length);
      for (i = 0; i < inputFloat32.length; i++) {
        var x = Math.max(-1, Math.min(1, inputFloat32[i]));
        same[i] = x < 0 ? x * 0x8000 : x * 0x7fff;
      }
      return same;
    }
    var ratio = inputRate / outputRate;
    var outLen = Math.max(1, Math.floor(inputFloat32.length / ratio));
    var out = new Int16Array(outLen);
    for (i = 0; i < outLen; i++) {
      var srcPos = i * ratio;
      var i0 = Math.floor(srcPos);
      var frac = srcPos - i0;
      var s0 = inputFloat32[i0] || 0;
      var s1 = inputFloat32[i0 + 1] !== undefined ? inputFloat32[i0 + 1] : s0;
      var s = s0 * (1 - frac) + s1 * frac;
      var c = Math.max(-1, Math.min(1, s));
      out[i] = c < 0 ? c * 0x8000 : c * 0x7fff;
    }
    return out;
  }

  function encodeAudioProtobuf(pcm16) {
    var Frame = FrameType;
    var audioInner = {
      id: 0,
      name: "",
      audio: new Uint8Array(pcm16.buffer, pcm16.byteOffset, pcm16.byteLength),
      sampleRate: TARGET_INPUT_HZ,
      numChannels: 1,
    };
    var payload = { audio: audioInner };
    var err = Frame.verify(payload);
    if (err) throw new Error(err);
    var message = Frame.create(payload);
    return Frame.encode(message).finish();
  }

  function markSpeaking() {
    setStatus("speaking");
    if (speakingTimer) clearTimeout(speakingTimer);
    speakingTimer = setTimeout(function () {
      speakingTimer = null;
      if (ws && ws.readyState === WebSocket.OPEN) setStatus("listening");
    }, SPEAKING_RESET_MS);
  }

  function playPcmChunk(audioBytes, sampleRate) {
    if (!playbackContext || !audioBytes || audioBytes.length < 2) return;
    var rate = sampleRate || DEFAULT_OUTPUT_HZ;
    var u8 = audioBytes instanceof Uint8Array ? audioBytes : new Uint8Array(audioBytes);
    var len = Math.floor(u8.byteLength / 2);
    if (len === 0) return;
    var samples = new Int16Array(len);
    var j;
    for (j = 0; j < len; j++) {
      samples[j] = u8[j * 2] | (u8[j * 2 + 1] << 8);
    }

    var buffer = playbackContext.createBuffer(1, samples.length, rate);
    var ch = buffer.getChannelData(0);
    var j;
    for (j = 0; j < samples.length; j++) {
      ch[j] = samples[j] / 32768;
    }
    var src = playbackContext.createBufferSource();
    src.buffer = buffer;
    src.connect(playbackContext.destination);

    var t = playbackContext.currentTime;
    if (nextPlayTime < t) nextPlayTime = t;
    try {
      src.start(nextPlayTime);
      nextPlayTime += buffer.duration;
    } catch (e) {
      log("Не удалось запустить воспроизведение: " + e.message, "warn");
    }
    markSpeaking();
  }

  function handleBinaryFrame(arrayBuffer) {
    if (!FrameType) return;
    try {
      var uint8 = new Uint8Array(arrayBuffer);
      var decoded = FrameType.decode(uint8);

      if (decoded.audio) {
        var a = decoded.audio;
        playPcmChunk(a.audio, a.sampleRate);
        return;
      }
      if (decoded.transcription && decoded.transcription.text) {
        appendUserTranscript(String(decoded.transcription.text).trim());
        return;
      }
      if (decoded.text && decoded.text.text) {
        log("Текст (кадр): " + decoded.text.text, "info");
        return;
      }
    } catch (e) {
      log("Ошибка разбора Protobuf: " + e.message, "err");
    }
  }

  function ensureProtobuf() {
    if (typeof protobuf === "undefined") {
      return Promise.reject(new Error("Библиотека protobuf не загружена"));
    }
    if (protoReady) return Promise.resolve();
    if (protoLoadPromise) return protoLoadPromise;
    protoLoadPromise = protobuf
      .load("/static/proto/frames.proto")
      .then(function (r) {
        root = r;
        FrameType = root.lookupType("pipecat.Frame");
        protoReady = true;
        log("Схема Protobuf загружена", "info");
      })
      .catch(function (e) {
        protoLoadPromise = null;
        throw e;
      });
    return protoLoadPromise;
  }

  function endCall() {
    if (speakingTimer) {
      clearTimeout(speakingTimer);
      speakingTimer = null;
    }
    nextPlayTime = 0;

    if (processor) {
      try {
        processor.disconnect();
      } catch (e) { /* ignore */ }
      processor = null;
    }
    if (sourceNode) {
      try {
        sourceNode.disconnect();
      } catch (e) { /* ignore */ }
      sourceNode = null;
    }
    if (audioContext) {
      audioContext.close().catch(function () {});
      audioContext = null;
    }
    if (playbackContext) {
      playbackContext.close().catch(function () {});
      playbackContext = null;
    }
    if (mediaStream) {
      mediaStream.getTracks().forEach(function (t) {
        t.stop();
      });
      mediaStream = null;
    }
    if (ws) {
      try {
        ws.close();
      } catch (e) { /* ignore */ }
      ws = null;
    }

    elStart.disabled = false;
    elEnd.disabled = true;
    setStatus("disconnected");
    clearTranscript();
    log("Звонок завершён, микрофон и сокет освобождены", "info");
  }

  function buildWsUrl() {
    var proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    var host = window.location.host;
    var params = new URLSearchParams();
    var sid = (elSession && elSession.value && elSession.value.trim()) || "";
    if (sid) params.set("session_id", sid);
    var mode = (elMode && elMode.value) || "consultant";
    params.set("mode", mode);
    if (mode === "trainer" || mode === "trainer_client") {
      var sc = elScenario && elScenario.value;
      if (sc) params.set("scenario_id", sc);
    }
    var mgr = elManager && elManager.value && elManager.value.trim();
    if (mgr) params.set("manager_name", mgr);
    var qs = params.toString();
    return proto + "//" + host + "/voice/stream" + (qs ? "?" + qs : "");
  }

  /** Подгружает сценарии для выпадающего списка тренажёра. */
  function loadScenariosForDropdown() {
    if (!elScenario) return;
    fetch(API_SCENARIOS, { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (list) {
        elScenario.innerHTML = "";
        if (!list || !list.length) {
          var o = document.createElement("option");
          o.value = "";
          o.textContent = "— Нет сценариев — создайте на странице «Сценарии»";
          elScenario.appendChild(o);
          return;
        }
        var i;
        for (i = 0; i < list.length; i++) {
          var opt = document.createElement("option");
          opt.value = list[i].id;
          opt.textContent = list[i].title;
          elScenario.appendChild(opt);
        }
      })
      .catch(function () {
        elScenario.innerHTML = "";
        var err = document.createElement("option");
        err.value = "";
        err.textContent = "— Ошибка загрузки /api/scenarios —";
        elScenario.appendChild(err);
      });
  }

  function updateTrainerFieldsVisibility() {
    if (!elScenarioField || !elMode) return;
    var m = elMode.value;
    if (m === "trainer" || m === "trainer_client") {
      elScenarioField.hidden = false;
    } else {
      elScenarioField.hidden = true;
    }
  }

  function startAudioPipeline() {
    if (!mediaStream || !ws || ws.readyState !== WebSocket.OPEN) return;

    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    var inRate = audioContext.sampleRate;

    sourceNode = audioContext.createMediaStreamSource(mediaStream);
    var bufferSize = 4096;
    processor = audioContext.createScriptProcessor(bufferSize, 1, 1);

    processor.onaudioprocess = function (ev) {
      if (!ws || ws.readyState !== WebSocket.OPEN || !FrameType) return;
      var input = ev.inputBuffer.getChannelData(0);
      var copy = new Float32Array(input.length);
      copy.set(input);
      var pcm16 = downsampleToInt16(copy, inRate, TARGET_INPUT_HZ);
      try {
        var encoded = encodeAudioProtobuf(pcm16);
        ws.send(encoded);
      } catch (e) {
        log("Ошибка кодирования кадра: " + e.message, "err");
      }
    };

    var mute = audioContext.createGain();
    mute.gain.value = 0;
    sourceNode.connect(processor);
    processor.connect(mute);
    mute.connect(audioContext.destination);

    playbackContext = new (window.AudioContext || window.webkitAudioContext)();
    nextPlayTime = playbackContext.currentTime;

    setStatus("listening");
    log(
      "Аудио: ввод с частотой " +
        inRate +
        " Гц, отправка " +
        TARGET_INPUT_HZ +
        " Гц PCM",
      "info"
    );
  }

  function startCall() {
    if (elStart) elStart.disabled = true;
    clearTranscript();
    setStatus("connected");
    log("Запрос доступа к микрофону…", "info");

    var mode = (elMode && elMode.value) || "consultant";
    if (mode === "trainer" || mode === "trainer_client") {
      var scVal = elScenario && elScenario.value;
      if (!scVal) {
        log("В режиме тренажёра выберите сценарий из списка.", "err");
        setStatus("error");
        if (elStart) elStart.disabled = false;
        return;
      }
    }

    ensureProtobuf()
      .then(function () {
        return navigator.mediaDevices.getUserMedia({ audio: true });
      })
      .then(function (stream) {
        mediaStream = stream;
        var url = buildWsUrl();
        log("Подключение к " + url, "info");
        ws = new WebSocket(url);
        ws.binaryType = "arraybuffer";

        ws.onopen = function () {
          setStatus("connected");
          log("WebSocket открыт", "info");
          if (elEnd) elEnd.disabled = false;
          startAudioPipeline();
        };

        ws.onmessage = function (event) {
          if (event.data instanceof ArrayBuffer) {
            handleBinaryFrame(event.data);
          } else {
            log("Текстовое сообщение: " + String(event.data), "info");
          }
        };

        ws.onerror = function () {
          log("Ошибка WebSocket", "err");
          setStatus("error");
        };

        ws.onclose = function (ev) {
          log(
            "WebSocket закрыт (код " + ev.code + (ev.reason ? ", " + ev.reason : "") + ")",
            "warn"
          );
          if (elStart) elStart.disabled = false;
          if (elEnd) elEnd.disabled = true;
          cleanupAfterSocketClosed();
        };
      })
      .catch(function (e) {
        log("Не удалось начать звонок: " + (e.message || e), "err");
        setStatus("error");
        if (elStart) elStart.disabled = false;
        if (mediaStream) {
          mediaStream.getTracks().forEach(function (t) {
            t.stop();
          });
          mediaStream = null;
        }
      });
  }

  /** Оставляем UI в согласованном состоянии, не дублируя полное закрытие треков, если endCall уже вызван */
  function cleanupAfterSocketClosed() {
    if (processor) {
      try {
        processor.disconnect();
      } catch (e) { /* ignore */ }
      processor = null;
    }
    if (sourceNode) {
      try {
        sourceNode.disconnect();
      } catch (e) { /* ignore */ }
      sourceNode = null;
    }
    if (audioContext) {
      audioContext.close().catch(function () {});
      audioContext = null;
    }
    if (playbackContext) {
      playbackContext.close().catch(function () {});
      playbackContext = null;
    }
    if (mediaStream) {
      mediaStream.getTracks().forEach(function (t) {
        t.stop();
      });
      mediaStream = null;
    }
    ws = null;
    setStatus("disconnected");
  }

  function init() {
    elStatus = document.getElementById("voice-status");
    elStatusText = document.getElementById("voice-status-text");
    elLog = document.getElementById("voice-log");
    elStart = document.getElementById("btn-start-call");
    elEnd = document.getElementById("btn-end-call");
    elSession = document.getElementById("session-id-input");
    elMode = document.getElementById("voice-mode-select");
    elScenario = document.getElementById("voice-scenario-select");
    elScenarioField = document.getElementById("voice-scenario-field");
    elManager = document.getElementById("manager-name-input");
    elTranscriptBody = document.getElementById("voice-transcript-body");

    if (!elStart || !elEnd) return;

    if (elMode) {
      elMode.addEventListener("change", function () {
        updateTrainerFieldsVisibility();
      });
      updateTrainerFieldsVisibility();
    }
    loadScenariosForDropdown();

    elStart.addEventListener("click", function () {
      startCall();
    });
    elEnd.addEventListener("click", function () {
      endCall();
    });

    setStatus("disconnected");
    log("Готов к тесту. Нажмите «Начать звонок» (нужны localhost или HTTPS).", "info");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

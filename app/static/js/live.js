/* ========== AI Live Interview - MediaRecorder + VAD + Server STT ========== */
var socket = null, curRound = 0, totalRounds = 5, timerSec = 0, timerIV = null;
var candidateName = (typeof CANDIDATE_NAME !== 'undefined' && CANDIDATE_NAME) ? CANDIDATE_NAME : '候选人';
var camStream = null, micStream = null;
var _sending = false, _started = false, _ttsPlaying = false, _skipTTS = false;
var _currentAudio = null, _currentSpeakCb = null;
var mediaRecorder = null, audioChunks = [];
var audioContext = null, analyser = null, vadTimer = null;
var _isRecording = false, _silenceStart = 0, _hasSpeech = false;
var VAD_THRESHOLD = 15;
var VAD_SILENCE_MS = 2000;
var VAD_CHECK_INTERVAL = 100;
var IMG_BASE = '/static/images/digital_human/' + (new URLSearchParams(window.location.search).get('avatar') || 'set1_fay') + '/';
var IMAGES = { idle: IMG_BASE + 'idle.jpg', speaking: IMG_BASE + 'speaking.jpg', listening: IMG_BASE + 'listening.jpg', thinking: IMG_BASE + 'thinking.jpg' };
(function() { for (var k in IMAGES) { var img = new Image(); img.src = IMAGES[k]; } })();

function _g(id) { return document.getElementById(id); }
function escapeHtml(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

function setDHState(state) {
    var img = _g('dhImg'), frame = _g('dhFrame'), overlay = _g('dhOverlay');
    var ring = _g('dhStatusRing'), wave = _g('aiWave'), glow = _g('aiGlow');
    if (!img) return;
    var src = IMAGES[state] || IMAGES.idle;
    var curName = img.src.split('/').pop();
    if (curName !== src.split('/').pop()) {
        img.style.opacity = '0.3';
        setTimeout(function() { img.src = src; img.onload = function() { img.style.opacity = '1'; }; }, 80);
    }
    if (frame) frame.className = 'dh-frame state-' + state;
    if (overlay) overlay.className = 'dh-overlay ' + (state === 'speaking' ? 'active' : '');
    if (ring) ring.className = 'dh-status-ring ' + state;
    if (wave) wave.className = 'ai-wave' + (state === 'speaking' ? ' active' : '');
    if (glow) glow.className = 'ai-glow ' + state;
}

function startEyeTracking() {
    var img = _g('dhImg'); if (!img) return;
    var targetX = 0, targetY = 0, currentX = 0, currentY = 0;
    function update() {
        currentX += (targetX - currentX) * 0.05;
        currentY += (targetY - currentY) * 0.05;
        img.style.transform = 'translate(' + (currentX * 8) + 'px,' + (currentY * 6) + 'px) scale(1.02)';
        requestAnimationFrame(update);
    }
    window._dhFaceCallback = function(x, y) { targetX = (x - 0.5) * 2; targetY = (y - 0.5) * 2; };
    var idleT = 0;
    setInterval(function() {
        if (!camStream) { idleT += 0.008; targetX = Math.sin(idleT) * 0.3; targetY = Math.cos(idleT * 0.7) * 0.2; }
    }, 50);
    update();
}

function startCam() {
    var v = _g('camVideo'); if (!v) return;
    navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 }, audio: false })
        .then(function(s) { camStream = s; v.srcObject = s; v.onloadedmetadata = function() { v.play(); startFaceDetection(v); }; })
        .catch(function(e) { console.warn('Camera error:', e); });
}

function startFaceDetection(video) {
    var canvas = document.createElement('canvas'); var tctx = canvas.getContext('2d');
    canvas.width = 64; canvas.height = 48; var lastX = 0.5, lastY = 0.5;
    (function detectLoop() {
        if (!camStream) return;
        try {
            tctx.drawImage(video, 0, 0, 64, 48);
            var data = tctx.getImageData(0, 0, 64, 48).data;
            var totalBright = 0, weightedX = 0, weightedY = 0, count = 0;
            for (var y = 8; y < 40; y += 2) {
                for (var x = 10; x < 54; x += 2) {
                    var i = (y * 64 + x) * 4;
                    var r = data[i], g = data[i+1], b = data[i+2];
                    if (r > 95 && g > 40 && b > 20 && r > g && r > b && Math.abs(r-g) > 15 && r-b > 15) {
                        var brightness = (r + g + b) / 3;
                        weightedX += x * brightness; weightedY += y * brightness; totalBright += brightness; count++;
                    }
                }
            }
            if (count > 20) {
                lastX = lastX * 0.7 + (1 - weightedX / totalBright / 64) * 0.3;
                lastY = lastY * 0.7 + (weightedY / totalBright / 48) * 0.3;
                if (window._dhFaceCallback) window._dhFaceCallback(lastX, lastY);
            }
        } catch(e) {}
        setTimeout(detectLoop, 120);
    })();
}

function clearTypingBubble() { var el = document.querySelector('.chat-msg.ai.is-typing'); if (el) el.remove(); }
function showTypingBubble() {
    clearTypingBubble();
    var scroll = _g('chatScroll'); if (!scroll) return;
    var now = new Date();
    var hh = String(now.getHours()).padStart(2,'0');
    var mm = String(now.getMinutes()).padStart(2,'0');
    var d = document.createElement('div'); d.className = 'chat-msg ai is-typing';
    var label = 'AI 面试官';
    var avatar = 'AI';
    d.innerHTML = '<div class="chat-meta">' +
        '<div class="chat-avatar ai">' + escapeHtml(avatar) + '</div>' +
        '<div class="chat-info">' +
        '<div class="chat-name">' + escapeHtml(label) + '</div>' +
        '<div class="chat-time">' + hh + ':' + mm + '</div>' +
        '</div></div>' +
        '<div class="chat-bubble typing-bubble"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div>';
    scroll.appendChild(d); scroll.scrollTop = scroll.scrollHeight;
}
function addChat(who, text) {
    var scroll = _g('chatScroll'); if (!scroll) return;
    var now = new Date();
    var hh = String(now.getHours()).padStart(2,'0');
    var mm = String(now.getMinutes()).padStart(2,'0');
    var d = document.createElement('div'); d.className = 'chat-msg ' + who;
    var label = who === 'ai' ? 'AI 面试官' : candidateName;
    var avatar = who === 'ai' ? 'AI' : (candidateName ? candidateName.charAt(0) : '我');
    d.innerHTML = '<div class="chat-meta">' +
        '<div class="chat-avatar ' + who + '">' + escapeHtml(avatar) + '</div>' +
        '<div class="chat-info">' +
        '<div class="chat-name">' + escapeHtml(label) + '</div>' +
        '<div class="chat-time">' + hh + ':' + mm + '</div>' +
        '</div></div>' +
        '<div class="chat-bubble">' + escapeHtml(text) + '</div>';
    scroll.appendChild(d); scroll.scrollTop = scroll.scrollHeight;
}

function addSys(text) {
    var scroll = _g('chatScroll'); if (!scroll) return;
    var now = new Date();
    var hh = String(now.getHours()).padStart(2,'0');
    var mm = String(now.getMinutes()).padStart(2,'0');
    var d = document.createElement('div'); d.className = 'chat-msg sys';
    d.innerHTML = '<div class="sys-card">' + escapeHtml(text) + '<div class="sys-time">' + hh + ':' + mm + '</div></div>';
    scroll.appendChild(d); scroll.scrollTop = scroll.scrollHeight;
}

function setStatus(s) { var el = _g('aiStatus'); if (el) el.textContent = s; }
function setVADState(state, label) {
    var dot = _g('vadDot'), lbl = _g('vadLabel'), bar = _g('liveBar');
    if (bar) bar.style.display = 'flex';
    if (dot) { dot.className = 'vad-dot'; if (state) dot.classList.add(state); }
    if (lbl) lbl.textContent = label || '';
}
function hideLiveBar() { var bar = _g('liveBar'); if (bar) bar.style.display = 'none'; }
function showLiveBar() { var bar = _g('liveBar'); if (bar) bar.style.display = 'flex'; }
function showLiveText(text) {
    var el = _g('liveText');
    if (!el) return;
    if (text) {
        el.style.display = 'block';
        el.innerHTML = '<span class="live-label">识别中：</span>' + escapeHtml(text) + '<span class="live-dots">...</span>';
    } else {
        el.style.display = 'none';
        el.innerHTML = '';
    }
}
function showVoiceHint(show) { var el = _g('voiceHint'); if (el) el.style.display = show ? 'block' : 'none'; }
function showDoneBtn(show) { var el = _g('doneBtn'); if (el) el.style.display = show ? 'block' : 'none'; }

var _sr = null, _srFinal = '';
function startBrowserRecognition() {
    try {
        var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) return;
        if (_sr) { try { _sr.abort(); } catch(e) {} }
        _sr = new SR(); _sr.lang = 'zh-CN'; _sr.continuous = true; _sr.interimResults = true; _srFinal = '';
        _sr.onresult = function(ev) {
            var interim = '';
            for (var i = ev.resultIndex; i < ev.results.length; i++) {
                var t = ev.results[i][0].transcript;
                if (ev.results[i].isFinal) { _srFinal += t; } else { interim += t; }
            }
            showLiveText((_srFinal + interim).trim());
        };
        _sr.onerror = function(ev) { if (ev.error === 'no-speech' || ev.error === 'aborted') return; console.warn('SR error', ev.error); };
        _sr.onend = function() { if (_isRecording && _sr) { try { _sr.start(); } catch(e) {} } };
        _sr.start();
    } catch(e) { console.warn('SR start failed', e); }
}
function stopBrowserRecognition() {
    try { if (_sr) { _sr.onend = null; _sr.abort(); _sr = null; } } catch(e) {}
}

function initDots(n) {
    var c = _g('roundDots'); if (!c) return; c.innerHTML = '';
    for (var i = 0; i < n; i++) { var d = document.createElement('div'); d.className = 'dot'; c.appendChild(d); }
}
function updateDots(cur) {
    var dots = _g('roundDots'); if (!dots) return;
    var children = dots.children;
    for (var i = 0; i < children.length; i++) {
        if (i < cur) children[i].className = 'dot done';
        else if (i === cur) children[i].className = 'dot active';
        else children[i].className = 'dot';
    }
    var rt = _g('roundText');
    if (rt) rt.textContent = (cur + 1) + ' / ' + totalRounds;
}
function startTimer() {
    timerSec = 0; timerIV = setInterval(function() {
        timerSec++; var m = Math.floor(timerSec / 60), s = timerSec % 60;
        var el = _g('timer'); if (el) el.textContent = (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
    }, 1000);
}
function stopTimer() { if (timerIV) { clearInterval(timerIV); timerIV = null; } }

function speak(text, cb) {
    if (_skipTTS || !text) { if (cb) setTimeout(cb, 500); return; }
    stopTTS(); _ttsPlaying = true; _currentSpeakCb = cb || null; setDHState('speaking');
    var url = '/api/tts?text=' + encodeURIComponent(text) + '&voice=xiaoxiao&rate=-5%25';
    var audio = new Audio(url); _currentAudio = audio;
    var done = false;
    var finish = function() {
        if (!done) {
            done = true; _ttsPlaying = false; _currentAudio = null; _currentSpeakCb = null; hideSkipBtn(); setDHState('listening');
            if (cb) cb();
        }
    };
    audio.onended = finish;
    audio.onerror = function() { console.warn('TTS error'); finish(); };
    audio.play().catch(function() { finish(); });
    showSkipBtn();
    setTimeout(function() { if (!done) { try { audio.pause(); } catch(e) {} finish(); } }, 60000);
}
function stopTTS() {
    if (_currentAudio) { try { _currentAudio.pause(); _currentAudio.currentTime = 0; } catch(e) {} _currentAudio = null; }
    _ttsPlaying = false;
}
function skipTTS() {
    _skipTTS = true;
    var pendingCb = _currentSpeakCb;
    stopTTS(); hideSkipBtn(); setDHState('listening');
    var btn = _g('skipTTSBtn');
    if (btn) { btn.innerHTML = '&#9654; 恢复语音'; btn.onclick = restoreTTS; }
    if (typeof pendingCb === 'function') {
        var cb = pendingCb; _currentSpeakCb = null; cb();
    }
}
function restoreTTS() {
    _skipTTS = false;
    var btn = _g('skipTTSBtn');
    if (btn) { btn.innerHTML = '&#9193; 跳过语音'; btn.onclick = skipTTS; }
}
function showSkipBtn() { var btn = _g('skipTTSBtn'); if (btn) btn.style.display = 'block'; }
function hideSkipBtn() { var btn = _g('skipTTSBtn'); if (btn) btn.style.display = 'none'; }

function initMicStream(cb) {
    if (micStream) { cb(); return; }
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(function(stream) {
            micStream = stream;
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            var source = audioContext.createMediaStreamSource(stream);
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 512;
            source.connect(analyser);
            cb();
        })
        .catch(function(e) {
            console.warn('Mic error:', e);
            addSys('麦克风权限被拒绝，请允许麦克风访问');
            setVADState('silence', '麦克风权限被拒绝');
        });
}
function getVolume() {
    if (!analyser) return 0;
    var data = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(data);
    var sum = 0;
    for (var i = 0; i < data.length; i++) sum += data[i];
    return sum / data.length;
}
function startRecording() {
    if (_isRecording) return;
    initMicStream(function() {
        audioChunks = [];
        try { mediaRecorder = new MediaRecorder(micStream, { mimeType: 'audio/webm;codecs=opus' }); }
        catch(e) { try { mediaRecorder = new MediaRecorder(micStream); } catch(e2) { addSys('浏览器不支持音频录制'); return; } }
        mediaRecorder.ondataavailable = function(e) { if (e.data.size > 0) audioChunks.push(e.data); };
        mediaRecorder.onstop = function() { onRecordingStop(); };
        mediaRecorder.start(100);
        _isRecording = true; startBrowserRecognition();
        _hasSpeech = false; _silenceStart = 0;
        setVADState('listening', '请回答...');
        showLiveBar();
        var border = _g('camBorder'); if (border) border.classList.add('listening');
        startVAD();
    });
}
function startVAD() {
    if (vadTimer) clearInterval(vadTimer);
    vadTimer = setInterval(function() {
        if (!_isRecording) { stopVAD(); return; }
        var vol = getVolume();
        if (vol > VAD_THRESHOLD) {
            _hasSpeech = true; _silenceStart = 0; setVADState('speaking', '检测到语音...');
        } else if (_hasSpeech) {
            if (_silenceStart === 0) _silenceStart = Date.now();
            var elapsed = Date.now() - _silenceStart;
            var remaining = Math.ceil((VAD_SILENCE_MS - elapsed) / 1000);
            if (elapsed >= VAD_SILENCE_MS) {
                setVADState('countdown', '回答完毕，提交中...');
                stopRecording();
            } else {
                setVADState('silence', '静音 ' + remaining + '秒后自动提交...');
            }
        }
    }, VAD_CHECK_INTERVAL);
}
function stopVAD() { if (vadTimer) { clearInterval(vadTimer); vadTimer = null; } }
function stopRecording() {
    stopBrowserRecognition(); stopVAD();
    if (_isRecording && mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
    _isRecording = false;
    var border = _g('camBorder'); if (border) border.classList.remove('listening');
}
function onRecordingStop() {
    if (audioChunks.length === 0) {
        addSys('没有检测到语音'); setVADState('silence', '没有检测到语音'); return;
    }
    var webmBlob = new Blob(audioChunks, { type: 'audio/webm' }); audioChunks = [];
    setVADState('submitted', '音频转换中...');
    blobToWav(webmBlob, function(wavBlob) { sendAudioToSTT(wavBlob); });
}
function blobToWav(blob, cb) {
    var reader = new FileReader();
    reader.onload = function() {
        var ac = new (window.AudioContext || window.webkitAudioContext)();
        ac.decodeAudioData(reader.result, function(audioBuffer) {
            var wavBlob = audioBufferToWav(audioBuffer); cb(wavBlob);
        }, function(e) { console.warn('Decode failed, sending raw blob:', e); cb(blob); });
    };
    reader.readAsArrayBuffer(blob);
}
function audioBufferToWav(buffer) {
    var numChannels = buffer.numberOfChannels;
    var sampleRate = buffer.sampleRate;
    var format = 1;
    var bitDepth = 16;
    var bytesPerSample = bitDepth / 8;
    var blockAlign = numChannels * bytesPerSample;
    var dataLength = buffer.length * blockAlign;
    var bufferLength = 44 + dataLength;
    var arrayBuffer = new ArrayBuffer(bufferLength);
    var view = new DataView(arrayBuffer);
    function writeString(offset, str) { for (var i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i)); }
    writeString(0, 'RIFF');
    view.setUint32(4, bufferLength - 8, true);
    writeString(8, 'WAVE');
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, format, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * blockAlign, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bitDepth, true);
    writeString(36, 'data');
    view.setUint32(40, dataLength, true);
    var offset = 44;
    var channels = [];
    for (var c = 0; c < numChannels; c++) channels.push(buffer.getChannelData(c));
    for (var i = 0; i < buffer.length; i++) {
        for (var c = 0; c < numChannels; c++) {
            var sample = Math.max(-1, Math.min(1, channels[c][i]));
            sample = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
            view.setInt16(offset, sample, true);
            offset += 2;
        }
    }
    return new Blob([arrayBuffer], { type: 'audio/wav' });
}
function sendAudioToSTT(blob) {
    setVADState('submitted', '语音识别中...');
    setStatus('识别中...');
    var formData = new FormData();
    formData.append('audio', blob, 'recording.webm');
    formData.append('lang', 'zh-CN');
    fetch('/api/stt', { method: 'POST', body: formData })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.text && data.text.trim()) {
                showLiveText(data.text);
                setVADState('submitted', '已识别，提交中...');
                submitVoiceAnswer(data.text.trim());
            } else {
                var errMsg = data.error || '未能识别语音';
                addSys('语音识别: ' + errMsg);
                setVADState('silence', '识别失败: ' + errMsg);
                setTimeout(function() {
                    if (!_sending && _started) { setVADState('listening', '请重新回答...'); startRecording(); }
                }, 2000);
            }
        })
        .catch(function(e) {
            console.warn('STT request failed:', e);
            addSys('语音识别请求失败');
            setVADState('silence', '识别请求失败');
        });
}
function submitVoiceAnswer(text) {
    if (_sending) return;
    if (!text) text = '(未作答)';
    _sending = true;
    stopTTS();
    addChat('you', text);
    showLiveText('');
    showDoneBtn(false);
    showVoiceHint(false);
    setDHState('thinking');
    setVADState('submitted', '已提交，AI评估中...');
    setStatus('评估中...');
    if (socket && socket.connected) {
        socket.emit('answer', { text: text, round: curRound });
    } else {
        addSys('连接已断开');
        _sending = false;
    }
    setTimeout(function() { _sending = false; }, 5000);
}
function forceSubmitAnswer() {
    stopRecording();
    if (audioChunks.length > 0) return;
    submitVoiceAnswer('(未作答)');
}
function connectSocket() {
    var url = (typeof WS_BASE !== 'undefined' && WS_BASE) ? WS_BASE : '/';
    socket = io(url, { transports: ['websocket', 'polling'] });
    socket.on('connect', function() {
        console.debug('Socket connected, joining interview...');
        socket.emit('join_interview', { token: TOKEN });
    });
    socket.on('disconnect', function() { addSys('连接断开'); setStatus('连接断开'); });
    socket.on('connect_error', function(err) { addSys('连接错误，正在重试...'); setStatus('连接错误'); });
    socket.on('system', function(data) {
        if (data.total_rounds) {
            totalRounds = data.total_rounds;
            initDots(totalRounds); updateDots(0);
            var rt = _g('roundText'); if (rt) rt.textContent = '1 / ' + totalRounds;
        }
        if (data.candidate_name) candidateName = data.candidate_name;
        addSys(data.message || '面试开始');
    });
    socket.on('question', function(data) {
        curRound = data.round || (curRound + 1);
        updateDots(curRound - 1);
        var qText = data.question || data.text || '';
        addChat('ai', qText);
        setDHState('speaking');
        setStatus('第 ' + curRound + ' / ' + totalRounds + ' 题');
        _sending = false;
        showLiveText('');
        speak(qText, function() {
            setDHState('listening');
            showVoiceHint(true);
            showDoneBtn(true);
            startRecording();
        });
    });
    socket.on('next_round', function(data) {
        curRound = data.round || (curRound + 1);
        updateDots(curRound - 1);
        var qText = data.question || data.text || '';
        addChat('ai', qText);
        setDHState('speaking');
        setStatus('第 ' + curRound + ' / ' + totalRounds + ' 题');
        _sending = false;
        showLiveText('');
        speak(qText, function() {
            setDHState('listening');
            showVoiceHint(true);
            showDoneBtn(true);
            startRecording();
        });
    });
    socket.on('interview_complete', function(data) {
        _started = false; stopRecording(); stopTTS();
        if (camStream) { camStream.getTracks().forEach(function(t) { t.stop(); }); camStream = null; }
        if (micStream) { micStream.getTracks().forEach(function(t) { t.stop(); }); micStream = null; }
        stopTimer(); hideLiveBar(); hideSkipBtn(); showDoneBtn(false); showVoiceHint(false);
        setDHState('idle');
        showComplete(data);
    });
    socket.on('error', function(data) {
        addSys('错误: ' + (data.message || data));
        _sending = false;
    });
}
function showComplete(data) {
    var ev = data && data.evaluation ? data.evaluation : data || {};
    var score = typeof ev.overall_score === 'number' ? ev.overall_score : 0;
    var circumference = 2 * Math.PI * 52;
    var arc = _g('scoreArc');
    if (arc) arc.style.strokeDashoffset = circumference * (1 - score / 10);
    var val = _g('scoreVal');
    if (val) val.textContent = score.toFixed(1);
    var recMap = { hire: '建议录用', maybe: '待定', no_hire: '不建议录用' };
    var tag = _g('recTag');
    if (tag) { tag.textContent = recMap[ev.recommendation] || '待定'; tag.className = 'rec-tag ' + ((ev.recommendation) || 'maybe'); }
    var sections = _g('evalSections');
    if (sections) {
        var html = '';
        var fields = [
            { title: '📊 总结', text: ev.summary },
            { title: '✅ 优势', text: ev.strengths },
            { title: '⚠️ 待提升', text: ev.weaknesses }
        ];
        for (var i = 0; i < fields.length; i++) {
            var txt = fields[i].text || '暂无';
            html += '<div class="eval-sec"><h3>' + fields[i].title + '</h3><p>' + escapeHtml(txt) + '</p></div>';
        }
        sections.innerHTML = html;
    }
    var completePage = _g('completePage');
    if (completePage) completePage.style.display = 'flex';
}
function initInterview() {
    _started = true;
    startCam();
    startEyeTracking();
    startTimer();
    connectSocket();
    var startBtn = _g('startBtn');
    if (startBtn) startBtn.addEventListener('click', function() {
        var welcome = _g('welcomePage');
        if (welcome) welcome.style.display = 'none';
        var interview = _g('interviewPage');
        if (interview) interview.style.display = 'flex';
        var recDot = _g('recDot');
        if (recDot) recDot.classList.add('on');
    });
    var doneBtn = _g('doneBtn');
    if (doneBtn) doneBtn.addEventListener('click', function() {
        forceSubmitAnswer();
    });
}
document.addEventListener('DOMContentLoaded', initInterview);

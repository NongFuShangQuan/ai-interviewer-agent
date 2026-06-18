let socket = null;
let currentRound = 0;
let totalRounds = 5;
let waitingForInput = false;
let candidateName = (typeof CANDIDATE_NAME !== 'undefined' && CANDIDATE_NAME) ? CANDIDATE_NAME : '';

function startInterview() {
    document.getElementById('welcomeOverlay').style.display = 'none';
    connect();
}

function connect() {
    socket = io('/', {
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: Infinity,
        transports: ['websocket', 'polling'],
    });

    socket.on('connect', function() {
        addSystemMsg('\u5df2\u8fde\u63a5\u5230\u9762\u8bd5\u670d\u52a1\u5668\uff0c\u8bf7\u7b49\u5f85AI\u9762\u8bd5\u5b98...');
        socket.emit('join_interview', { token: TOKEN });
    });

    socket.on('disconnect', function() {
        if (waitingForInput) {
            addSystemMsg('\u8fde\u63a5\u5df2\u65ad\u5f00\uff0c\u6b63\u5728\u91cd\u8fde...');
            disableInput();
        }
    });

    socket.on('reconnect', function() {
        addSystemMsg('\u8fde\u63a5\u5df2\u6062\u590d');
        socket.emit('join_interview', { token: TOKEN });
    });

    socket.on('system', function(data) {
        handleMessage({ type: 'system', data: data });
    });

    socket.on('round_start', function(data) {
        handleMessage({ type: 'round_start', data: data });
    });

    socket.on('question', function(data) {
        handleMessage({ type: 'question', data: data });
    });

    socket.on('status', function(data) {
        handleMessage({ type: 'status', data: data });
    });

    socket.on('round_end', function(data) {
        handleMessage({ type: 'round_end', data: data });
    });

    socket.on('interview_complete', function(data) {
        handleMessage({ type: 'interview_complete', data: data });
    });

    socket.on('error', function(data) {
        handleMessage({ type: 'error', data: data });
    });

    socket.on('connect_error', function(err) {
        addSystemMsg('\u8fde\u63a5\u51fa\u9519\uff0c\u6b63\u5728\u91cd\u8bd5...');
        console.error('Socket.IO connect error:', err);
    });
}

function handleMessage(msg) {
    var d = msg.data;
    switch (msg.type) {
        case 'system':
            if (d.candidate_name) candidateName = d.candidate_name;
            if (d.message && d.message.indexOf("RAG") >= 0) {
                var indicator = document.getElementById("rag-indicator");
                if (indicator) {
                    indicator.style.display = "block";
                    document.getElementById("rag-status-text").textContent = "Active";
                    setTimeout(function() { indicator.style.opacity = "0.7"; }, 3000);
                }
            }
            document.getElementById('jobTitle').textContent = '\u5171 ' + d.total_rounds + ' \u8f6e\u95ee\u7b54';
            totalRounds = d.total_rounds;
            break;
        case 'round_start':
            currentRound = d.round;
            updateProgress();
            if (d.status === 'generating_question') showTyping();
            break;
        case 'question':
            removeTyping();
            addAIMessage(d.question, d.round);
            enableInput();
            break;
        case 'status':
            if (d.message) { showTyping(d.message); disableInput(); }
            break;
        case 'round_end':
            removeTyping();
            disableInput();
            break;
        case 'interview_complete':
            removeTyping();
            disableInput();
            showComplete(d.evaluation);
            break;
        case 'error':
            addSystemMsg('\u274c ' + d.message);
            break;
    }
}

var _sending = false;
function sendAnswer() {
    if (_sending) return;
    var input = document.getElementById('answerInput');
    var answer = input.value.trim();
    if (!answer || !socket || !socket.connected) {
        addSystemMsg('\u8fde\u63a5\u5df2\u65ad\u5f00\uff0c\u8bf7\u5237\u65b0\u9875\u9762\u91cd\u8bd5');
        return;
    }
    _sending = true;
    addCandidateMessage(answer);
    socket.emit('answer', { text: answer });
    input.value = '';
    autoResize(input);
    disableInput();
    _sending = false;
}

document.getElementById('answerInput').addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendAnswer(); }
});
document.getElementById('answerInput').addEventListener('input', function() { autoResize(this); });

function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 150) + 'px';
}

function addAIMessage(text, round) {
    var chat = document.getElementById('chatArea');
    chat.innerHTML += '<div class="message ai"><div class="avatar">\u1f916</div><div><div class="round-badge">\u7b2c ' + round + ' / ' + totalRounds + ' \u8f6e</div><div class="bubble">' + escapeHtml(text) + '</div></div></div>';
    scrollBottom();
}

function addCandidateMessage(text) {
    var chat = document.getElementById('chatArea');
    chat.innerHTML += '<div class="message candidate"><div class="avatar">\u1f9d1</div><div class="bubble">' + escapeHtml(text) + '</div></div>';
    scrollBottom();
}

function addSystemMsg(text) {
    var chat = document.getElementById('chatArea');
    chat.innerHTML += '<div class="system-msg">' + text + '</div>';
    scrollBottom();
}

function showTyping(text) {
    removeTyping();
    var chat = document.getElementById('chatArea');
    chat.innerHTML += '<div class="system-msg"><span class="spinner"></span>' + (text || 'AI\u6b63\u5728\u601d\u8003..') + '</div>';
    scrollBottom();
}

function removeTyping() {
    document.querySelectorAll('.system-msg .spinner').forEach(function(el) { el.parentElement.remove(); });
}

function updateProgress() {
    var pct = ((currentRound - 1) / totalRounds) * 100;
    document.getElementById('progressFill').style.width = pct + '%';
    document.getElementById('progressText').textContent = '\u7b2c ' + currentRound + ' / ' + totalRounds + ' \u8f6e';
}

function enableInput() {
    waitingForInput = true;
    document.getElementById('inputArea').style.display = 'block';
    document.getElementById('answerInput').disabled = false;
    document.getElementById('sendBtn').disabled = false;
    document.getElementById('answerInput').focus();
}

function disableInput() {
    waitingForInput = false;
    document.getElementById('answerInput').disabled = true;
    document.getElementById('sendBtn').disabled = true;
}

function showComplete(ev) {
    document.getElementById('progressFill').style.width = '100%';
    document.getElementById('progressText').textContent = '\u9762\u8bd5\u5df2\u5b8c\u6210';
    var recMap = { hire: '\u5efa\u8bae\u5f55\u7528', maybe: '\u5f85\u5b9a', no_hire: '\u4e0d\u5efa\u8bae\u5f55\u7528' };
    var recClass = ev.recommendation || 'maybe';
    var score = ev.overall_score || 0;
    var pct = (score / 10) * 100;
    var chat = document.getElementById('chatArea');
    chat.innerHTML += '<div class="complete-card"><h2>\u2705 \u9762\u8bd5\u5b8c\u6210</h2>' +
        '<div class="score-circle" style="--pct: ' + pct + '%;"><div class="score-inner">' + score.toFixed(1) + '</div></div>' +
        '<p style="color:#888; margin-top:8px;">\u7efc\u5408\u8bc4\u5206\uff08\u6ee1\u520610\u5206\uff09</p>' +
        '<span class="rec-badge ' + recClass + '">' + (recMap[recClass] || '\u5f85\u5b9a') + '</span>' +
        '<div class="eval-section"><h3>\u1f4ca \u603b\u7ed3</h3><p>' + escapeHtml(ev.summary || '\u6682\u65e0') + '</p></div>' +
        '<div class="eval-section"><h3>\u2705 \u4f18\u52bf</h3><p>' + escapeHtml(ev.strengths || '\u6682\u65e0') + '</p></div>' +
        '<div class="eval-section"><h3>\u26a0\ufe0f \u5f85\u63d0\u5347</h3><p>' + escapeHtml(ev.weaknesses || '\u6682\u65e0') + '</p></div></div>';
    scrollBottom();
    document.getElementById('inputArea').style.display = 'none';
}

function scrollBottom() {
    var chat = document.getElementById('chatArea');
    chat.scrollTop = chat.scrollHeight;
}

function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML.replace(/\n/g, '<br>');
}
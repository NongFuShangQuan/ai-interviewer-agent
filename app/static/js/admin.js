/* ========== AI Interview Admin JS ========== */
var jobTemplates = null;

function selectType(el) {
    document.querySelectorAll('.type-card').forEach(function(x) { x.classList.remove('active'); });
    el.classList.add('active');
    el.querySelector('input').checked = true;
}

/* Navigation */
function switchPage(name) {
    document.querySelectorAll('.page').forEach(function(p) { p.classList.remove('active'); });
    document.querySelectorAll('.sb-link').forEach(function(l) { l.classList.remove('active'); });
    var page = document.getElementById('page-' + name);
    if (page) page.classList.add('active');
    document.querySelectorAll('.sb-link').forEach(function(l) {
        if (l.dataset.page === name) l.classList.add('active');
    });
    if (name === 'dashboard') loadStats();
    if (name === 'list') loadInterviews();
    if (name === 'guard') loadGuardStats();
    if (name === 'rag') loadRAGStats();
}
document.querySelectorAll('.sb-link').forEach(function(l) {
    l.addEventListener('click', function() { switchPage(l.dataset.page); });
});

function getInterviewType() {
    var checked = document.querySelector('input[name="itype"]:checked');
    return checked ? checked.value : 'text';
}

/* Job templates */
async function loadJobTemplates() {
    try {
        var r = await fetch('/api/admin/job-templates');
        jobTemplates = await r.json();
        var sel = document.getElementById('jobCategory');
        sel.innerHTML = '<option value="">选择类别</option>';
        jobTemplates.categories.forEach(function(c) {
            sel.innerHTML += '<option value="' + c.name + '">' + c.icon + ' ' + c.name + '</option>';
        });
    } catch (e) { console.error('Job templates load failed:', e); }
}

function onCategoryChange() {
    var cat = document.getElementById('jobCategory').value;
    var sel = document.getElementById('jobTitle');
    sel.innerHTML = '<option value="">选择职位</option>';
    if (!cat || !jobTemplates) return;
    var c = jobTemplates.categories.find(function(x) { return x.name === cat; });
    if (c) c.jobs.forEach(function(j) { sel.innerHTML += '<option value="' + j.title + '">' + j.title + '</option>'; });
}

function onJobChange() {
    var title = document.getElementById('jobTitle').value;
    if (!title || !jobTemplates) return;
    for (var i = 0; i < jobTemplates.categories.length; i++) {
        var j = jobTemplates.categories[i].jobs.find(function(x) { return x.title === title; });
        if (j) {
            document.getElementById('jTitle').value = j.title;
            document.getElementById('jDesc').value = j.description;
            break;
        }
    }
}

/* Stats */
async function loadStats() {
    try {
        var r = await fetch('/api/admin/interviews');
        var d = await r.json();
        document.getElementById('statTotal').textContent = d.stats.total_interviews;
        document.getElementById('statCompleted').textContent = d.stats.completed;
        document.getElementById('statInProgress').textContent = d.stats.in_progress;
        document.getElementById('statAvgScore').textContent = d.stats.average_score;
        var tbody = document.getElementById('recentBody');
        tbody.innerHTML = '';
        var statusMap = {pending: '待开始', in_progress: '进行中', completed: '已完成'};
        var recMap = {hire: '建议录用', maybe: '待定', no_hire: '不建议'};
        d.interviews.slice(0, 5).forEach(function(iv) {
            var score = iv.overall_score ? iv.overall_score.toFixed(1) : '-';
            var rec = iv.recommendation ? '<span class="badge ' + iv.recommendation + '">' + (recMap[iv.recommendation] || iv.recommendation) + '</span>' : '-';
            tbody.innerHTML += '<tr><td><strong>' + iv.candidate_name + '</strong><br><span style="font-size:11px;color:var(--text3)">' + iv.candidate_email + '</span></td><td>' + iv.job_title + '</td><td>' + (iv.interview_type === 'video' ? '视频' : iv.interview_type === 'live' ? '直播' : '文本') + '</td><td><span class="badge ' + iv.status + '">' + (statusMap[iv.status] || iv.status) + '</span></td><td><strong>' + score + '</strong></td><td><button class="btn ghost" data-detail="' + iv.id + '">详情</button></td></tr>';
        });
    } catch (e) { console.error(e); }
}

/* Create */
async function createInterview() {
    var body = {
        candidate_name: document.getElementById('cName').value,
        candidate_email: document.getElementById('cEmail').value,
        job_title: document.getElementById('jTitle').value,
        job_description: document.getElementById('jDesc').value,
        position: document.getElementById('jTitle').value,
        resume_text: document.getElementById('cResume').value,
        total_rounds: parseInt(document.getElementById('totalRounds').value) || 5
    };
    if (!body.candidate_name || !body.candidate_email || !body.job_title || !body.job_description) {
        alert('请填写必填项');
        return;
    }
    try {
        var r = await fetch('/api/admin/interviews', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        });
        var d = await r.json();
        var el = document.getElementById('createResult');
        el.style.display = 'block';
        if (d.success) {
            var type = getInterviewType();
            var prefix = '/interview/';
            if (type === 'video') prefix = '/video/';
            else if (type === 'live') prefix = '/live/';
            var url = location.origin + prefix + d.token;
            el.className = 'result-box success';
            el.innerHTML = '<p>面试创建成功！</p><p>面试链接：<a href="' + url + '" target="_blank">' + url + '</a></p>';
        } else {
            el.className = 'result-box error';
            el.innerHTML = '<p>创建失败：' + (d.error || '未知错误') + '</p>';
        }
    } catch (e) {
        var el = document.getElementById('createResult');
        el.style.display = 'block';
        el.className = 'result-box error';
        el.innerHTML = '<p>请求失败：' + e.message + '</p>';
    }
}

/* Interview list */
async function loadInterviews() {
    try {
        var r = await fetch('/api/admin/interviews');
        var d = await r.json();
        var tbody = document.getElementById('interviewBody');
        tbody.innerHTML = '';
        var statusMap = {pending: '待开始', in_progress: '进行中', completed: '已完成'};
        var recMap = {hire: '建议录用', maybe: '待定', no_hire: '不建议'};
        d.interviews.forEach(function(iv) {
            var score = iv.overall_score ? iv.overall_score.toFixed(1) : '-';
            var rec = iv.recommendation ? '<span class="badge ' + iv.recommendation + '">' + (recMap[iv.recommendation] || iv.recommendation) + '</span>' : '-';
            tbody.innerHTML += '<tr><td><strong>' + iv.candidate_name + '</strong><br><span style="font-size:11px;color:var(--text3)">' + iv.candidate_email + '</span></td><td>' + iv.job_title + '</td><td>' + (iv.interview_type === 'video' ? '视频' : iv.interview_type === 'live' ? '直播' : '文本') + '</td><td><span class="badge ' + iv.status + '">' + (statusMap[iv.status] || iv.status) + '</span></td><td>' + iv.current_round + '/' + iv.total_rounds + '</td><td><strong>' + score + '</strong></td><td>' + rec + '</td><td><button class="btn ghost" data-detail="' + iv.id + '">详情</button> <button class="btn ghost" data-export="' + iv.id + ':json">导出</button></td></tr>';
        });
    } catch (e) { console.error(e); }
}

/* Detail */
async function viewDetail(id) {
    try {
        var r = await fetch('/api/admin/interviews/' + id);
        var d = await r.json();
        var html = '<div class="dsec"><h3>基本信息</h3><p>候选人：' + d.candidate_name + '<br>职位：' + d.job_title + '</p></div>';
        if (d.evaluation) {
            var ev = d.evaluation;
            html += '<div class="dsec"><h3>评分</h3><div class="score-grid">';
            var keys = ['overall_score', 'technical_score', 'communication_score', 'problem_solving_score', 'cultural_fit_score', 'experience_score'];
            var labels = {overall_score: '综合', technical_score: '技术', communication_score: '沟通', problem_solving_score: '问题解决', cultural_fit_score: '文化匹配', experience_score: '经验'};
            keys.forEach(function(k) {
                html += '<div class="score-item"><div class="sv">' + (ev[k] != null ? ev[k].toFixed(1) : '0.0') + '</div><div class="sl">' + labels[k] + '</div></div>';
            });
            html += '</div></div>';
            html += '<div class="dsec"><h3>总结</h3><p>' + esc(ev.summary) + '</p></div>';
            html += '<div class="dsec"><h3>优势</h3><p>' + esc(ev.strengths) + '</p></div>';
            html += '<div class="dsec"><h3>待提升</h3><p>' + esc(ev.weaknesses) + '</p></div>';
        }
        if (d.messages && d.messages.length) {
            html += '<div class="dsec"><h3>对话记录</h3>';
            d.messages.forEach(function(m) {
                var role = m.role === 'ai' ? 'AI' : '候选人';
                html += '<p><strong>' + role + ' (第' + m.round_num + '轮)</strong><br>' + esc(m.content) + '</p>';
            });
            html += '</div>';
        }
        document.getElementById('detailBody').innerHTML = html;
        
        document.getElementById('detailBody').innerHTML += '<div style="display:flex;gap:8px;margin-top:16px;padding-top:16px;border-top:1px solid var(--border)"><button class="btn ghost" data-export="' + id + ':json">JSON</button><button class="btn ghost" data-export="' + id + ':csv">CSV</button><button class="btn primary" data-export="' + id + ':html">HTML Report</button></div>';
        document.getElementById('detailModal').style.display = 'flex';
    } catch (e) { alert('加载失败：' + e.message); }
}

function closeDetail() { document.getElementById('detailModal').style.display = 'none'; }

function esc(s) {
    var d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML.replace(/\n/g, '<br>');
}

/* Guard stats */
async function loadGuardStats() {
    try {
        var r = await fetch('/api/admin/guard/stats');
        var d = await r.json();
        var el = document.getElementById('guardStats');
        el.innerHTML =
            '<div class="stat-card"><div class="stat-icon blue"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><path d="M22 2L15 22 11 13 2 9z"/></svg></div><div><span class="stat-val">' + d.total_tool_calls + '</span><span class="stat-label">工具调用总数</span></div></div>' +
            '<div class="stat-card"><div class="stat-icon green"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg></div><div><span class="stat-val">' + d.health_rate + '%</span><span class="stat-label">健康率</span></div></div>' +
            '<div class="stat-card"><div class="stat-icon purple"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg></div><div><span class="stat-val">' + d.total_loop_events + '</span><span class="stat-label">循环事件</span></div></div>' +
            '<div class="stat-card"><div class="stat-icon amber"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></div><div><span class="stat-val">' + Object.keys(d.calls_by_result || {}).length + '</span><span class="stat-label">调用状态类型</span></div></div>';
    } catch (e) { console.error(e); }
}

/* Event delegation for detail buttons */
document.addEventListener('click', function(e) {
    var btn = e.target.closest('[data-detail]');
    if (btn) { viewDetail(btn.dataset.detail); }
});

/* Export button event delegation */
document.addEventListener('click', function(e) {
    var btn = e.target.closest('[data-export]');
    if (btn) {
        var parts = btn.dataset.export.split(':');
        var id = parts[0];
        var format = parts[1];
        window.open('/api/admin/interviews/' + id + '/export/' + format, '_blank');
    }
});


/* RAG Module */
var ragQuestionBank = null;

async function loadRAGStats() {
    try {
        var r = await fetch('/api/admin/rag/status');
        var d = await r.json();
        document.getElementById('ragQCount').textContent = d.question_bank_count || 0;
        document.getElementById('ragKCount').textContent = d.knowledge_count || 0;
        document.getElementById('ragECount').textContent = d.eval_ref_count || 0;
        document.getElementById('ragCacheSize').textContent = d.embedding_cache_size || 0;
    } catch (e) { console.error('RAG stats load failed:', e); }

    // Load question bank content
    try {
        var r2 = await fetch('/api/admin/rag/question-bank');
        if (r2.ok) {
            ragQuestionBank = await r2.json();
            populateRAGFilters(ragQuestionBank);
            renderRAGQuestions(ragQuestionBank.questions);
        }
    } catch (e) { console.error('Question bank load failed:', e); }

    // Load knowledge entries
    try {
        var r3 = await fetch('/api/admin/rag/status');
        var status = await r3.json();
        var knowledgeEl = document.getElementById('ragKnowledgeList');
        if (knowledgeEl) {
            knowledgeEl.innerHTML = '<div style="color:var(--text3);padding:12px">Knowledge base: ' + (status.knowledge_count || 0) + ' entries loaded from job templates</div>';
        }
    } catch (e) {}
}

function populateRAGFilters(bank) {
    var catSelect = document.getElementById('ragFilterCategory');
    var famSelect = document.getElementById('ragFilterFamily');
    if (!catSelect || !famSelect) return;

    var categories = [];
    var families = [];
    bank.questions.forEach(function(q) {
        if (categories.indexOf(q.category) < 0) categories.push(q.category);
        if (families.indexOf(q.job_family) < 0) families.push(q.job_family);
    });

    catSelect.innerHTML = '<option value="">All Categories</option>';
    categories.forEach(function(c) { catSelect.innerHTML += '<option value="' + c + '">' + c + '</option>'; });

    famSelect.innerHTML = '<option value="">All Job Families</option>';
    families.forEach(function(f) { famSelect.innerHTML += '<option value="' + f + '">' + f + '</option>'; });
}

function filterRAGQuestions() {
    if (!ragQuestionBank) return;
    var cat = document.getElementById('ragFilterCategory').value;
    var fam = document.getElementById('ragFilterFamily').value;
    var filtered = ragQuestionBank.questions.filter(function(q) {
        if (cat && q.category !== cat) return false;
        if (fam && q.job_family !== fam) return false;
        return true;
    });
    renderRAGQuestions(filtered);
}

function renderRAGQuestions(questions) {
    var el = document.getElementById('ragQuestionList');
    if (!el) return;
    if (!questions || questions.length === 0) {
        el.innerHTML = '<div style="color:var(--text3);padding:12px">No questions found</div>';
        return;
    }

    var diffColors = {easy: 'var(--success)', medium: 'var(--warn)', hard: 'var(--danger)'};
    var diffLabels = {easy: 'Easy', medium: 'Medium', hard: 'Hard'};
    var html = '<table><thead><tr><th>ID</th><th>Category</th><th>Job Family</th><th>Difficulty</th><th>Question</th><th>Keywords</th></tr></thead><tbody>';

    questions.forEach(function(q) {
        var diff = q.difficulty || 'medium';
        var color = diffColors[diff] || 'var(--text3)';
        var keywords = (q.keywords || []).slice(0, 3).join(', ');
        html += '<tr>';
        html += '<td><code style="font-size:11px">' + q.id + '</code></td>';
        html += '<td>' + q.category + '</td>';
        html += '<td>' + q.job_family + '</td>';
        html += '<td><span style="color:' + color + ';font-weight:600;font-size:12px">' + (diffLabels[diff] || diff) + '</span></td>';
        html += '<td style="max-width:300px">' + q.question + '</td>';
        html += '<td style="font-size:11px;color:var(--text3)">' + keywords + '</td>';
        html += '</tr>';
    });

    html += '</tbody></table>';
    el.innerHTML = html;
}

async function reindexRAG() {
    if (!confirm('确定要重新建立RAG索引吗？这可能需要几分钟时间。')) return;
    try {
        var r = await fetch('/api/admin/rag/reindex', {method: 'POST'});
        var d = await r.json();
        if (d.success) {
            alert('索引重建成功！');
            loadRAGStats();
        } else {
            alert('重建失败：' + (d.error || '未知错误'));
        }
    } catch (e) { alert('请求失败：' + e.message); }
}


/* Export Functions */
function exportInterview(id, format) {
    window.open('/api/admin/interviews/' + id + '/export/' + format, '_blank');
}

/* Init */
loadStats();
loadJobTemplates();
loadRAGStats();
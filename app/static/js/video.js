/* ========== AI Interview - Modern Virtual Human ========== */
var socket = null, curRound = 0, totalRounds = 5, timerSec = 0, timerIV = null; var candidateName = (typeof CANDIDATE_NAME !== 'undefined' && CANDIDATE_NAME) ? CANDIDATE_NAME : 'You';
var synth = window.speechSynthesis, camStream = null;
var faceX = 0.5, faceY = 0.5, eyeTrackRAF = null;
var vhState = 'idle';

// Animation state
var anim = {
    blinkT: 0, blinkDur: 0, isBlinking: false,
    mouthOpen: 0, mouthTarget: 0,
    breath: 0, idle: 0,
    nod: 0, smile: 0,
    eyeX: 0.5, eyeY: 0.5,
    _eyeX: 0.5, _eyeY: 0.5,
    nextBlink: 200 + Math.random() * 300,
    frameCount: 0
};

function _g(id) { return document.getElementById(id); }

// ==================== HIGH QUALITY VIRTUAL HUMAN ====================
var cv, ctx, W = 500, H = 650;

function initCanvas() {
    cv = _g('vhCanvas');
    if (!cv) { cv = document.createElement('canvas'); cv.id = 'vhCanvas'; }
    cv.width = W; cv.height = H;
    ctx = cv.getContext('2d');
}

function drawWelcomeAvatar() {
    var c = _g('welcomeAvatar');
    if (!c) return;
    var ctx2 = c.getContext('2d');
    if (!ctx2) return;
    drawVirtualHuman(ctx2, 200, 200, true);
}

// Main rendering function
function drawVirtualHuman(c, w, h, mini) {
    try {
        c.clearRect(0, 0, w, h);
        var s = w / 500;
        var cx = w / 2, cy = h * 0.35;

        // Smooth eye tracking
        anim._eyeX += (anim.eyeX - anim._eyeX) * 0.08;
        anim._eyeY += (anim.eyeY - anim._eyeY) * 0.08;

        // Breathing
        anim.breath += 0.015;
        var breathY = Math.sin(anim.breath) * 2 * s;

        // Idle movement
        anim.idle += 0.008;
        var idleX = Math.sin(anim.idle) * 1.2 * s;
        var idleY = Math.cos(anim.idle * 0.7) * 0.8 * s;

        // Nod when speaking
        if (vhState === 'speaking') {
            anim.nod = (anim.nod + (Math.random() - 0.5) * 0.15) * 0.88;
            anim.smile += (0.15 - anim.smile) * 0.04;
        } else {
            anim.nod *= 0.92;
            anim.smile += (0.05 - anim.smile) * 0.03;
        }

        var hx = cx + idleX;
        var hy = cy + idleY + anim.nod * s + breathY;

        // Blinking
        anim.frameCount++;
        anim.blinkT++;
        if (!anim.isBlinking && anim.blinkT > anim.nextBlink) {
            anim.isBlinking = true;
            anim.blinkDur = 0;
        }
        if (anim.isBlinking) {
            anim.blinkDur++;
            if (anim.blinkDur > 8) {
                anim.isBlinking = false;
                anim.blinkT = 0;
                anim.nextBlink = 150 + Math.random() * 250;
            }
        }
        var blinkAmt = anim.isBlinking ? Math.sin(anim.blinkDur / 8 * Math.PI) : 0;

        // Mouth animation
        if (vhState === 'speaking') {
            anim.mouthTarget = 0.3 + Math.random() * 0.5;
        } else {
            anim.mouthTarget = 0;
        }
        anim.mouthOpen += (anim.mouthTarget - anim.mouthOpen) * 0.15;

        if (!mini) {
            // Background glow based on state
            var glowColor = vhState === 'speaking' ? 'rgba(99,102,241,0.08)' :
                           vhState === 'listening' ? 'rgba(34,197,94,0.06)' :
                           vhState === 'thinking' ? 'rgba(245,158,11,0.06)' : 'rgba(99,102,241,0.04)';
            var glow = c.createRadialGradient(cx, cy, 0, cx, cy, w * 0.5);
            glow.addColorStop(0, glowColor);
            glow.addColorStop(1, 'rgba(0,0,0,0)');
            c.fillStyle = glow;
            c.fillRect(0, 0, w, h);
        }

        // ===== HAIR (behind head) =====
        drawHairBack(c, hx, hy, s);

        // ===== NECK =====
        drawNeck(c, hx, hy, s, breathY);

        // ===== BODY =====
        drawBody(c, hx, hy, s, h, breathY);

        // ===== EARS =====
        drawEars(c, hx, hy, s);

        // ===== FACE =====
        drawFaceShape(c, hx, hy, s);

        // ===== EYES =====
        drawEyes(c, hx, hy, s, blinkAmt);

        // ===== NOSE =====
        drawNose(c, hx, hy, s);

        // ===== MOUTH =====
        drawMouth(c, hx, hy, s);

        // ===== EYEBROWS =====
        drawEyebrows(c, hx, hy, s);

        // ===== HAIR (front) =====
        drawHairFront(c, hx, hy, s);

        // ===== GLASSES (optional) =====
        // drawGlasses(c, hx, hy, s);

    } catch(e) { console.warn('drawVirtualHuman error:', e); }
}

function drawHairBack(c, hx, hy, s) {
    c.fillStyle = '#1a1a2e';
    c.beginPath();
    c.ellipse(hx, hy - 45 * s, 95 * s, 85 * s, 0, Math.PI, 0);
    c.quadraticCurveTo(hx + 95 * s, hy + 20 * s, hx + 80 * s, hy + 50 * s);
    c.lineTo(hx - 80 * s, hy + 50 * s);
    c.quadraticCurveTo(hx - 95 * s, hy + 20 * s, hx - 95 * s, hy - 45 * s);
    c.fill();
}

function drawNeck(c, hx, hy, s, breathY) {
    var grad = c.createLinearGradient(hx - 22 * s, hy + 75 * s, hx + 22 * s, hy + 75 * s);
    grad.addColorStop(0, '#e8c4a0');
    grad.addColorStop(0.3, '#f0d4b0');
    grad.addColorStop(0.5, '#f2d8b8');
    grad.addColorStop(0.7, '#f0d4b0');
    grad.addColorStop(1, '#e0bc98');
    c.fillStyle = grad;
    c.beginPath();
    c.moveTo(hx - 20 * s, hy + 72 * s + breathY);
    c.lineTo(hx + 20 * s, hy + 72 * s + breathY);
    c.lineTo(hx + 24 * s, hy + 120 * s + breathY);
    c.lineTo(hx - 24 * s, hy + 120 * s + breathY);
    c.fill();

    // Neck shadow
    var shadow = c.createLinearGradient(hx, hy + 68 * s, hx, hy + 80 * s);
    shadow.addColorStop(0, 'rgba(0,0,0,0.08)');
    shadow.addColorStop(1, 'rgba(0,0,0,0)');
    c.fillStyle = shadow;
    c.fillRect(hx - 22 * s, hy + 68 * s + breathY, 44 * s, 12 * s);
}

function drawBody(c, hx, hy, s, h, breathY) {
    c.save();
    c.beginPath();
    c.moveTo(hx - 80 * s, h + 10);
    c.quadraticCurveTo(hx - 90 * s, hy + 120 * s + breathY, hx - 24 * s, hy + 116 * s + breathY);
    c.lineTo(hx + 24 * s, hy + 116 * s + breathY);
    c.quadraticCurveTo(hx + 90 * s, hy + 120 * s + breathY, hx + 80 * s, h + 10);

    // Dark professional blazer
    var suitGrad = c.createLinearGradient(hx - 80 * s, hy + 110 * s, hx + 80 * s, hy + 110 * s);
    suitGrad.addColorStop(0, '#1a1a30');
    suitGrad.addColorStop(0.25, '#252548');
    suitGrad.addColorStop(0.5, '#2a2a55');
    suitGrad.addColorStop(0.75, '#252548');
    suitGrad.addColorStop(1, '#1a1a30');
    c.fillStyle = suitGrad;
    c.fill();

    // Blazer lapels
    c.strokeStyle = 'rgba(255,255,255,0.06)';
    c.lineWidth = 1 * s;
    c.beginPath();
    c.moveTo(hx - 40 * s, hy + 112 * s + breathY);
    c.lineTo(hx - 10 * s, hy + 145 * s + breathY);
    c.stroke();
    c.beginPath();
    c.moveTo(hx + 40 * s, hy + 112 * s + breathY);
    c.lineTo(hx + 10 * s, hy + 145 * s + breathY);
    c.stroke();

    // White blouse collar
    c.fillStyle = '#f0ebe3';
    c.beginPath();
    c.moveTo(hx - 22 * s, hy + 108 * s + breathY);
    c.lineTo(hx, hy + 130 * s + breathY);
    c.lineTo(hx + 22 * s, hy + 108 * s + breathY);
    c.lineTo(hx + 16 * s, hy + 108 * s + breathY);
    c.lineTo(hx, hy + 122 * s + breathY);
    c.lineTo(hx - 16 * s, hy + 108 * s + breathY);
    c.fill();

    // Subtle necklace
    c.strokeStyle = 'rgba(200,180,140,0.4)';
    c.lineWidth = 1.2 * s;
    c.beginPath();
    c.arc(hx, hy + 100 * s + breathY, 18 * s, 0.3, Math.PI - 0.3);
    c.stroke();

    c.restore();
}

function drawEars(c, hx, hy, s) {
    // Left ear
    c.fillStyle = '#e8c4a0';
    c.beginPath();
    c.ellipse(hx - 78 * s, hy + 5 * s, 12 * s, 18 * s, -0.1, 0, Math.PI * 2);
    c.fill();
    c.fillStyle = 'rgba(200,160,120,0.3)';
    c.beginPath();
    c.ellipse(hx - 76 * s, hy + 5 * s, 7 * s, 12 * s, -0.1, 0, Math.PI * 2);
    c.fill();

    // Right ear
    c.fillStyle = '#e8c4a0';
    c.beginPath();
    c.ellipse(hx + 78 * s, hy + 5 * s, 12 * s, 18 * s, 0.1, 0, Math.PI * 2);
    c.fill();
    c.fillStyle = 'rgba(200,160,120,0.3)';
    c.beginPath();
    c.ellipse(hx + 76 * s, hy + 5 * s, 7 * s, 12 * s, 0.1, 0, Math.PI * 2);
    c.fill();
}

function drawFaceShape(c, hx, hy, s) {
    // Face base with warm skin tone
    var skinGrad = c.createRadialGradient(hx - 15 * s, hy - 15 * s, 0, hx, hy + 10 * s, 80 * s);
    skinGrad.addColorStop(0, '#f5dcc4');
    skinGrad.addColorStop(0.4, '#f0d4b4');
    skinGrad.addColorStop(0.7, '#e8c8a4');
    skinGrad.addColorStop(1, '#e0bc98');
    c.fillStyle = skinGrad;

    // Face shape - oval with slight jaw
    c.beginPath();
    c.moveTo(hx, hy - 70 * s);
    c.bezierCurveTo(hx + 55 * s, hy - 70 * s, hx + 78 * s, hy - 30 * s, hx + 75 * s, hy + 5 * s);
    c.bezierCurveTo(hx + 72 * s, hy + 35 * s, hx + 55 * s, hy + 65 * s, hx + 35 * s, hy + 75 * s);
    c.bezierCurveTo(hx + 15 * s, hy + 82 * s, hx - 15 * s, hy + 82 * s, hx - 35 * s, hy + 75 * s);
    c.bezierCurveTo(hx - 55 * s, hy + 65 * s, hx - 72 * s, hy + 35 * s, hx - 75 * s, hy + 5 * s);
    c.bezierCurveTo(hx - 78 * s, hy - 30 * s, hx - 55 * s, hy - 70 * s, hx, hy - 70 * s);
    c.fill();

    // Cheek blush
    var blushL = c.createRadialGradient(hx - 40 * s, hy + 30 * s, 0, hx - 40 * s, hy + 30 * s, 25 * s);
    blushL.addColorStop(0, 'rgba(240,180,160,0.12)');
    blushL.addColorStop(1, 'rgba(240,180,160,0)');
    c.fillStyle = blushL;
    c.fillRect(hx - 65 * s, hy + 5 * s, 50 * s, 50 * s);

    var blushR = c.createRadialGradient(hx + 40 * s, hy + 30 * s, 0, hx + 40 * s, hy + 30 * s, 25 * s);
    blushR.addColorStop(0, 'rgba(240,180,160,0.12)');
    blushR.addColorStop(1, 'rgba(240,180,160,0)');
    c.fillStyle = blushR;
    c.fillRect(hx + 15 * s, hy + 5 * s, 50 * s, 50 * s);

    // Face shadow (left side for depth)
    var faceShadow = c.createLinearGradient(hx - 75 * s, hy, hx - 50 * s, hy);
    faceShadow.addColorStop(0, 'rgba(0,0,0,0.04)');
    faceShadow.addColorStop(1, 'rgba(0,0,0,0)');
    c.fillStyle = faceShadow;
    c.beginPath();
    c.ellipse(hx - 60 * s, hy + 5 * s, 20 * s, 60 * s, 0, 0, Math.PI * 2);
    c.fill();
}

function drawEyes(c, hx, hy, s, blinkAmt) {
    var eyeLX = hx - 28 * s, eyeRX = hx + 28 * s;
    var eyeY = hy - 5 * s;
    var eyeW = 22 * s, eyeH = 12 * s;

    // Eye direction offset
    var dx = (anim._eyeX - 0.5) * 6 * s;
    var dy = (anim._eyeY - 0.5) * 4 * s;

    [eyeLX, eyeRX].forEach(function(ex) {
        // Eye white
        c.fillStyle = '#fff';
        c.beginPath();
        c.ellipse(ex, eyeY, eyeW, eyeH * (1 - blinkAmt * 0.9), 0, 0, Math.PI * 2);
        c.fill();

        if (blinkAmt < 0.8) {
            // Iris
            var irisR = 9 * s;
            var irisGrad = c.createRadialGradient(ex + dx, eyeY + dy, 0, ex + dx, eyeY + dy, irisR);
            irisGrad.addColorStop(0, '#2a1a0a');
            irisGrad.addColorStop(0.5, '#4a3020');
            irisGrad.addColorStop(0.8, '#3a2515');
            irisGrad.addColorStop(1, '#2a1a0a');
            c.fillStyle = irisGrad;
            c.beginPath();
            c.ellipse(ex + dx, eyeY + dy, irisR, irisR, 0, 0, Math.PI * 2);
            c.fill();

            // Pupil
            c.fillStyle = '#0a0a0a';
            c.beginPath();
            c.ellipse(ex + dx, eyeY + dy, 4 * s, 4 * s, 0, 0, Math.PI * 2);
            c.fill();

            // Eye highlight (main)
            c.fillStyle = 'rgba(255,255,255,0.9)';
            c.beginPath();
            c.ellipse(ex + dx + 3 * s, eyeY + dy - 3 * s, 2.5 * s, 2 * s, -0.3, 0, Math.PI * 2);
            c.fill();

            // Eye highlight (secondary)
            c.fillStyle = 'rgba(255,255,255,0.5)';
            c.beginPath();
            c.ellipse(ex + dx - 2 * s, eyeY + dy + 2 * s, 1.5 * s, 1 * s, 0, 0, Math.PI * 2);
            c.fill();

            // Upper eyelid shadow
            var lidShadow = c.createLinearGradient(ex, eyeY - eyeH, ex, eyeY - eyeH + 6 * s);
            lidShadow.addColorStop(0, 'rgba(0,0,0,0.08)');
            lidShadow.addColorStop(1, 'rgba(0,0,0,0)');
            c.fillStyle = lidShadow;
            c.beginPath();
            c.ellipse(ex, eyeY - eyeH + 3 * s, eyeW + 2 * s, 5 * s, 0, 0, Math.PI * 2);
            c.fill();
        }

        // Eyelashes (upper)
        c.strokeStyle = '#1a1a2e';
        c.lineWidth = 1.5 * s;
        c.beginPath();
        c.ellipse(ex, eyeY, eyeW, eyeH * (1 - blinkAmt * 0.9), 0, Math.PI + 0.3, -0.3);
        c.stroke();
    });
}

function drawNose(c, hx, hy, s) {
    // Nose bridge (subtle highlight)
    c.fillStyle = 'rgba(255,255,255,0.06)';
    c.beginPath();
    c.moveTo(hx - 3 * s, hy - 15 * s);
    c.lineTo(hx + 3 * s, hy - 15 * s);
    c.lineTo(hx + 2 * s, hy + 20 * s);
    c.lineTo(hx - 2 * s, hy + 20 * s);
    c.fill();

    // Nose tip
    c.fillStyle = 'rgba(230,190,160,0.3)';
    c.beginPath();
    c.ellipse(hx, hy + 22 * s, 8 * s, 5 * s, 0, 0, Math.PI * 2);
    c.fill();

    // Nostrils (subtle)
    c.fillStyle = 'rgba(180,140,110,0.2)';
    c.beginPath();
    c.ellipse(hx - 5 * s, hy + 24 * s, 3 * s, 2 * s, 0.2, 0, Math.PI * 2);
    c.fill();
    c.beginPath();
    c.ellipse(hx + 5 * s, hy + 24 * s, 3 * s, 2 * s, -0.2, 0, Math.PI * 2);
    c.fill();
}

function drawMouth(c, hx, hy, s) {
    var mouthY = hy + 42 * s;
    var mouthOpen = anim.mouthOpen;
    var smile = anim.smile;

    // Lips
    c.fillStyle = '#d4736a';

    // Upper lip
    c.beginPath();
    c.moveTo(hx - 18 * s, mouthY);
    c.quadraticCurveTo(hx - 8 * s, mouthY - 5 * s - smile * 3 * s, hx, mouthY - 3 * s - smile * 2 * s);
    c.quadraticCurveTo(hx + 8 * s, mouthY - 5 * s - smile * 3 * s, hx + 18 * s, mouthY);
    c.quadraticCurveTo(hx + 8 * s, mouthY + 2 * s, hx, mouthY + 1 * s);
    c.quadraticCurveTo(hx - 8 * s, mouthY + 2 * s, hx - 18 * s, mouthY);
    c.fill();

    // Lower lip
    c.fillStyle = '#c86860';
    c.beginPath();
    c.moveTo(hx - 16 * s, mouthY + 1 * s);
    c.quadraticCurveTo(hx, mouthY + 8 * s + mouthOpen * 12 * s, hx + 16 * s, mouthY + 1 * s);
    c.quadraticCurveTo(hx, mouthY + 2 * s, hx - 16 * s, mouthY + 1 * s);
    c.fill();

    // Mouth opening when speaking
    if (mouthOpen > 0.1) {
        c.fillStyle = '#2a1a1a';
        c.beginPath();
        c.moveTo(hx - 12 * s, mouthY + 1 * s);
        c.quadraticCurveTo(hx, mouthY + 3 * s + mouthOpen * 10 * s, hx + 12 * s, mouthY + 1 * s);
        c.quadraticCurveTo(hx, mouthY + 2 * s, hx - 12 * s, mouthY + 1 * s);
        c.fill();
    }

    // Lip highlight
    c.fillStyle = 'rgba(255,255,255,0.15)';
    c.beginPath();
    c.ellipse(hx, mouthY - 2 * s, 8 * s, 2 * s, 0, 0, Math.PI * 2);
    c.fill();
}

function drawEyebrows(c, hx, hy, s) {
    c.strokeStyle = '#2a2018';
    c.lineWidth = 3 * s;
    c.lineCap = 'round';

    // Left eyebrow
    c.beginPath();
    c.moveTo(hx - 48 * s, hy - 25 * s);
    c.quadraticCurveTo(hx - 28 * s, hy - 32 * s - anim.smile * 3 * s, hx - 10 * s, hy - 26 * s);
    c.stroke();

    // Right eyebrow
    c.beginPath();
    c.moveTo(hx + 48 * s, hy - 25 * s);
    c.quadraticCurveTo(hx + 28 * s, hy - 32 * s - anim.smile * 3 * s, hx + 10 * s, hy - 26 * s);
    c.stroke();
}

function drawHairFront(c, hx, hy, s) {
    c.fillStyle = '#1a1a2e';

    // Main hair volume
    c.beginPath();
    c.moveTo(hx - 70 * s, hy - 40 * s);
    c.bezierCurveTo(hx - 65 * s, hy - 80 * s, hx - 30 * s, hy - 95 * s, hx, hy - 90 * s);
    c.bezierCurveTo(hx + 30 * s, hy - 95 * s, hx + 65 * s, hy - 80 * s, hx + 70 * s, hy - 40 * s);
    c.bezierCurveTo(hx + 60 * s, hy - 55 * s, hx + 40 * s, hy - 65 * s, hx + 25 * s, hy - 60 * s);
    c.bezierCurveTo(hx + 10 * s, hy - 55 * s, hx - 10 * s, hy - 55 * s, hx - 25 * s, hy - 60 * s);
    c.bezierCurveTo(hx - 40 * s, hy - 65 * s, hx - 60 * s, hy - 55 * s, hx - 70 * s, hy - 40 * s);
    c.fill();

    // Side hair
    c.beginPath();
    c.moveTo(hx - 75 * s, hy - 30 * s);
    c.quadraticCurveTo(hx - 82 * s, hy - 10 * s, hx - 78 * s, hy + 20 * s);
    c.quadraticCurveTo(hx - 70 * s, hy + 10 * s, hx - 72 * s, hy - 10 * s);
    c.quadraticCurveTo(hx - 74 * s, hy - 25 * s, hx - 75 * s, hy - 30 * s);
    c.fill();

    c.beginPath();
    c.moveTo(hx + 75 * s, hy - 30 * s);
    c.quadraticCurveTo(hx + 82 * s, hy - 10 * s, hx + 78 * s, hy + 20 * s);
    c.quadraticCurveTo(hx + 70 * s, hy + 10 * s, hx + 72 * s, hy - 10 * s);
    c.quadraticCurveTo(hx + 74 * s, hy - 25 * s, hx + 75 * s, hy - 30 * s);
    c.fill();

    // Hair shine
    c.fillStyle = 'rgba(255,255,255,0.04)';
    c.beginPath();
    c.ellipse(hx - 15 * s, hy - 75 * s, 30 * s, 8 * s, -0.3, 0, Math.PI * 2);
    c.fill();
}

// ==================== ANIMATION LOOP ====================
function animFrame() {
    if (!ctx) return;
    drawVirtualHuman(ctx, W, H, false);
    // Draw welcome avatar too
    drawWelcomeAvatar();
    requestAnimationFrame(animFrame);
}

// ==================== EYE TRACKING ====================
function startEyeTracking() {
    var idleT = 0;
    function update() {
        if (!camStream) {
            idleT += 0.01;
            anim.eyeX = 0.5 + Math.sin(idleT) * 0.15;
            anim.eyeY = 0.5 + Math.cos(idleT * 0.7) * 0.1;
        }
        requestAnimationFrame(update);
    }
    update();
}

// ==================== WEBCAM ====================
function startCam() {
    var v = _g('camVideo');
    if (!v) return;
    navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 }, audio: true })
        .then(function(s) {
            camStream = s;
            v.srcObject = s;
            v.onloadedmetadata = function() { v.play(); startFaceDetection(v); };
        })
        .catch(function(e) { console.warn('Camera error:', e); });
}

function startFaceDetection(video) {
    var canvas = document.createElement('canvas');
    var tctx = canvas.getContext('2d');
    canvas.width = 64; canvas.height = 48;
    var lastX = 0.5, lastY = 0.5;

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
                        weightedX += x * brightness; weightedY += y * brightness;
                        totalBright += brightness; count++;
                    }
                }
            }
            if (count > 20) {
                lastX = lastX * 0.7 + (1 - weightedX / totalBright / 64) * 0.3;
                lastY = lastY * 0.7 + (weightedY / totalBright / 48) * 0.3;
                anim.eyeX = lastX;
                anim.eyeY = lastY;
            }
        } catch(e) {}
        setTimeout(detectLoop, 120);
    })();
}

function stopCam() {
    if (camStream) { camStream.getTracks().forEach(function(t) { t.stop(); }); camStream = null; }
}

// ==================== STATE MANAGEMENT ====================
function setDHState(state) {
    vhState = state;
    var wave = _g('aiWave');
    var glow = _g('aiGlow');
    var ring = _g('vhStatusRing');

    if (wave) wave.className = 'ai-wave' + (state === 'speaking' ? ' active' : '');
    if (glow) glow.className = 'ai-glow ' + state;
    if (ring) ring.className = 'vh-status-ring ' + state;
}

// ==================== INTERVIEW FLOW ====================
function startInterview() {
    var wp = _g('welcomePage'); if (wp) wp.style.display = 'none';
    var ip = _g('interviewPage'); if (ip) ip.style.display = 'flex';
    buildDots();
    startCam();
    startTimer();
    startEyeTracking();
    initCanvas();
    animFrame();
    connect();
}

function buildDots() {
    var el = _g('roundDots'); if (!el) return;
    el.innerHTML = '';
    for (var i = 1; i <= totalRounds; i++) {
        var d = document.createElement('div');
        d.className = 'round-dot' + (i === 1 ? ' active' : '');
        d.id = 'dot-' + i;
        el.appendChild(d);
    }
}

function connect() {
    socket = io('/', {
        reconnection: true, reconnectionDelay: 1000, reconnectionDelayMax: 5000,
        reconnectionAttempts: Infinity, transports: ['websocket', 'polling'],
    });
    socket.on('connect', function() { addSys('连接成功，面试即将开始...'); setDHState('idle'); setStatus('待开始'); socket.emit('join_interview', {token: TOKEN}); startHeartbeat(); });
    socket.on('disconnect', function() { addSys('连接已断开'); setDHState('idle'); setStatus('已断开'); });
    socket.on('connect_error', function(err) { addSys('连接错误，正在重试...'); setStatus('错误'); });
    socket.on('reconnect', function() { addSys('已重连'); socket.emit('join_interview', {token: TOKEN}); });
    socket.on('system', function(d) { handleMsg({type:'system',data:d}); });
    socket.on('round_start', function(d) { handleMsg({type:'round_start',data:d}); });
    socket.on('question', function(d) { handleMsg({type:'question',data:d}); });
    socket.on('status', function(d) { handleMsg({type:'status',data:d}); });
    socket.on('round_end', function(d) { handleMsg({type:'round_end',data:d}); });
    socket.on('interview_complete', function(d) { handleMsg({type:'interview_complete',data:d}); });
    socket.on('error', function(d) { handleMsg({type:'error',data:d}); });
}

function handleMsg(msg) {
    var d = msg.data || msg;
    var t = msg.type;
    if (t === 'system') {
        // RAG status indicator
        if (d.message && d.message.indexOf("RAG") >= 0) {
            var indicator = document.getElementById("rag-indicator");
            if (indicator) {
                indicator.style.display = "block";
                document.getElementById("rag-status-text").textContent = "Active";
                setTimeout(function() { indicator.style.opacity = "0.7"; }, 3000);
            }
        }

        addSys(d.message || '系统消息');
        if (d.candidate_name) candidateName = d.candidate_name;
        if (d.total_rounds && d.total_rounds > 0) {
            totalRounds = d.total_rounds;
            buildDots();
            var rt = _g('roundText');
            if (rt) rt.textContent = '1 / ' + totalRounds;
        }
    } else if (t === 'question') {
        curRound = d.round || (curRound + 1);
        updateDots();
        setDHState('speaking');
        setStatus('待回答...');
        hideInput();
        var qText = d.question || d.text || d.message || '';
        addAI(qText, curRound);
        speak(qText, function() {
            setDHState('listening');
            setStatus('待回答...');
            showInput();
        });
    } else if (t === 'evaluating') {
        setDHState('thinking');
        setStatus('AI评估中...');
        hideInput();
        addSys(d.message || '系统消息');
    } else if (t === 'round_result') {
        addSys('\u7b2c' + curRound + '\u8f6e\u8bc4\u4f30\u5b8c\u6210');
    } else if (t === 'round_end') {
        addSys('\u7b2c' + (d.round || curRound) + '\u8f6e\u7ed3\u675f');
        setDHState('thinking');
        setStatus('AI\u6b63\u5728\u51c6\u5907\u4e0b\u4e00\u4e2a\u95ee\u9898...');
        hideInput();
    } else if (t === 'status') {
        addSys(d.message || '\u7cfb\u7edf\u6d88\u606f');
    } else if (t === 'interview_complete' || t === 'complete') {
        setDHState('idle');
        setStatus('\u9762\u8bd5\u5df2\u7ed3\u675f');
        hideInput();
        var ev = d.evaluation || d;
        setTimeout(function() { showComplete(ev); }, 1000);
    } else if (t === 'error') {
        addSys('错误: ' + (d.message || msg.message || '\u672a\u77e5错误'));
        setStatus('面试结束');
    }
}

// ==================== TTS ====================
function getBestVoice() {
    var voices = synth.getVoices();
    var msPreferred = [
        'Microsoft Xiaoxiao Online', 'Xiaoxiao',
        'Microsoft Xiaoyi Online', 'Xiaoyi',
        'Microsoft Xiaohan Online', 'Xiaohan',
        'Microsoft Xiaomeng Online', 'Xiaomeng',
        'Microsoft Xiaorui Online', 'Xiaorui',
        'Microsoft Xiaoxuan Online', 'Xiaoxuan',
        'Microsoft Xiaoyan Online', 'Xiaoyan',
        'Microsoft Huihui', 'Huihui',
        'Microsoft Yaoyao', 'Yaoyao'
    ];
    var googlePreferred = [
        'Google \u666e\u901a\u8bdd', 'Google \u53f0\u6e7e\u8bed',
        'Google Cantonese', 'Google \u7ca4\u8bed'
    ];
    var zhVoices = [];
    for (var i = 0; i < voices.length; i++) {
        var v = voices[i];
        if (v.lang.indexOf('zh') !== -1 || v.lang.indexOf('cmn') !== -1 || v.lang.indexOf('yue') !== -1) {
            zhVoices.push(v);
        }
    }
    if (zhVoices.length > 0) {
        console.debug('Available zh voices:', zhVoices.map(function(v) { return v.name + ' (' + v.lang + ')'; }));
    }
    var allPreferred = msPreferred.concat(googlePreferred);
    for (var p = 0; p < allPreferred.length; p++) {
        for (var j = 0; j < zhVoices.length; j++) {
            if (zhVoices[j].name.indexOf(allPreferred[p]) !== -1) return zhVoices[j];
        }
    }
    var femaleHints = ['female', 'woman', 'girl', 'xiao', 'mei', 'ling', 'wan', 'xiu', 'hui', 'yao', 'han', 'meng', 'rui', 'xuan', 'yan', 'yi'];
    for (var j = 0; j < zhVoices.length; j++) {
        var name = zhVoices[j].name.toLowerCase();
        for (var f = 0; f < femaleHints.length; f++) {
            if (name.indexOf(femaleHints[f]) !== -1) return zhVoices[j];
        }
    }
    return zhVoices[0] || null;
}

var _skipTTS = false;
var _ttsMuted = false;
function toggleTTS() {
    _ttsMuted = !_ttsMuted;
    _skipTTS = _ttsMuted;
    var sb = document.getElementById('skipTTSBtn');
    if (sb) {
        if (_ttsMuted) {
            if (synth) synth.cancel();
            sb.innerHTML = '\u25b6 \u6062\u590d\u8bed\u97f3';
            sb.style.background = 'rgba(34,197,94,0.85)';
        } else {
            sb.innerHTML = '\u23f9 \u8df3\u8fc7\u8bed\u97f3';
            sb.style.background = 'rgba(99,102,241,0.85)';
        }
    }
}
function skipTTS() { toggleTTS(); }
var _ttsAudio = null;
function _ensureTtsAudio() {
    if (!_ttsAudio) {
        _ttsAudio = new Audio();
        _ttsAudio.volume = 1.0;
        _ttsAudio.src = 'data:audio/mp3;base64,SUQzBAAAAAABEVRYWFgAAAAtAAADY29tbWVudABCaWdTb3VuZEJhbmsuY29tIC8gTGFTb25vdGhlcXVlLm9yZwBURU5DAAAAHQAAA1N3aXRjaCBQbHVzIMKpIE5DSCBTb2Z0d2FyZQBUSVQyAAAABgAAAzIyMzUAVFNTRQAAAA8AAANMYXZmNTcuODMuMTAwAAAAAAAAAAAAAAD/80DEAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQsRbAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQMSkAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV';
        try { _ttsAudio.play().then(function() { _ttsAudio.pause(); }).catch(function() {}); } catch(e) {}
    }
    return _ttsAudio;
}
function speak(text, cb) {
    if (!text) { if (cb) setTimeout(cb, 1500); return; }
    _skipTTS = false;
    var sb = document.getElementById('skipTTSBtn');
    if (sb) {
        sb.style.display = 'block';
        if (_ttsMuted) {
            sb.innerHTML = '\u25b6 \u6062\u590d\u8bed\u97f3';
            sb.style.background = 'rgba(34,197,94,0.85)';
        } else {
            sb.innerHTML = '\u23f9 \u8df3\u8fc7\u8bed\u97f3';
            sb.style.background = 'rgba(99,102,241,0.85)';
        }
    }
    if (_ttsMuted) { if (cb) setTimeout(cb, 500); return; }
    var audio = _ensureTtsAudio();
    var done = false;
    var finishCb = function() { if (!done) { done = true; if (sb) sb.style.display = 'none'; if (cb) cb(); } };
    audio.onended = finishCb;
    audio.onerror = function() { console.warn('TTS error - skipping'); finishCb(); };
    audio.src = '/api/tts?text=' + encodeURIComponent(text) + '&voice=xiaoxiao&rate=-5%25';
    var p = audio.play();
    if (p !== undefined) p.catch(function(e) { console.warn('TTS play blocked:', e.message); finishCb(); });
    // Safety timeout: 30s max for TTS playback
    setTimeout(function() { if (!done) { done = true; try { audio.pause(); } catch(e) {} if (cb) cb(); } }, 30000);
    // Loading timeout: if audio doesn't start playing within 8s, skip
    var loadTimer = setTimeout(function() {
        if (!done && audio.readyState < 2) {
            console.warn('TTS load timeout - skipping');
            done = true; try { audio.pause(); } catch(e) {} if (cb) cb();
        }
    }, 8000);
    audio.addEventListener('playing', function() { clearTimeout(loadTimer); }, { once: true });
}

// ==================== \ud83c\udfa4 \u8bed\u97f3 ====================
var recognition = null, micActive = false;
var _voiceSilenceTimer = null, _voiceFinalTranscript = '', _voiceInterimTranscript = '';
function toggleMic() {
    if (micActive) { stopMic(); return; }
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { addSys('\u6d4f\u89c8\u5668\u4e0d\u652f\u6301\u8bed\u97f3\u8bc6\u522b\uff0c\u8bf7\u624b\u52a8\u8f93\u5165'); return; }
    recognition = new SR();
    recognition.lang = 'zh-CN';
    recognition.continuous = true;
    recognition.interimResults = true;
    var finalText = '', silenceTimer = null;
    recognition.onresult = function(e) {
        var interim = '';
        for (var i = e.resultIndex; i < e.results.length; i++) {
            if (e.results[i].isFinal) finalText += e.results[i][0].transcript;
            else interim += e.results[i][0].transcript;
        }
        var ta = _g('answerInput');
        if (ta) ta.value = finalText + interim;
        if (silenceTimer) clearTimeout(silenceTimer);
        silenceTimer = setTimeout(function() { if (finalText.trim().length > 5) stopMic(); }, 3000);
    };
    recognition.onerror = function(e) {
        console.warn('Speech error:', e.error);
        if (e.error === 'not-allowed' || e.error === 'audio-capture') {
            addSys('\u9ea6\u514b\u98ce\u6743\u9650\u88ab\u62d2\u7edd');
        }
        stopMic();
    };
    recognition.onend = function() {
        isListening = false;
        micActive = false;
        var btn = _g('micBtn');
        if (btn) btn.textContent = '\ud83c\udfa4 \u8bed\u97f3';
        // Auto-restart if still in answering state and not sending
        var inputArea = _g('inputBox');
        if (!_sending && inputArea && inputArea.style.display !== 'none') {
            setTimeout(function() {
                try {
                    recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
                    recognition.lang = 'zh-CN';
                    recognition.continuous = true;
                    recognition.interimResults = true;
                    // Re-attach all handlers
                    var finalText2 = finalText;
                    recognition.onresult = function(e) {
                        var interim = '';
                        for (var i = e.resultIndex; i < e.results.length; i++) {
                            if (e.results[i].isFinal) finalText2 += e.results[i][0].transcript;
                            else interim += e.results[i][0].transcript;
                        }
                        var ta = _g('answerInput');
                        if (ta) ta.value = finalText2 + interim;
                    };
                    recognition.onerror = function(e) { console.warn('Speech retry error:', e.error); };
                    recognition.onend = function() { micActive = false; };
                    recognition.start();
                    micActive = true;
                    isListening = true;
                    if (btn) btn.textContent = '\ud83d\udd0a';
                } catch(e) { console.warn('SR restart failed:', e); }
            }, 500);
        }
    };
    recognition.start();
    micActive = true;
    var btn = _g('micBtn'); if (btn) btn.textContent = '\ud83d\udd0a';
}

function stopMic() {
    if (recognition) { try { recognition.stop(); } catch(e) {} }
    micActive = false;
    var btn = _g('micBtn'); if (btn) btn.textContent = '\ud83c\udfa4 \u8bed\u97f3 Voice';
}

// ==================== SEND ANSWER ====================
var _sending = false;
function sendAnswer() {
    if (_sending) return;
    var ta = _g('answerInput'); if (!ta) return;
    var text = ta.value.trim();
    // If no text, use a default response to avoid getting stuck
    if (!text) { text = '(\u6ca1\u6709\u68c0\u6d4b\u5230\u56de\u7b54\uff0c\u8bf7\u7ee7\u7eed\u4e0b\u4e00\u4e2a\u95ee\u9898)'; }
    _sending = true;
    addHuman(text); ta.value = '';
    hideInput(); setDHState('thinking'); setStatus('Evaluating...');
    try {
        if (socket && socket.connected) {
            socket.emit('answer', { text: text, round: curRound });
        } else {
            addSys('连接已断开\uff0c\u8bf7\u5237\u65b0\u9875\u9762\u91cd\u8bd5');
            _sending = false;
            return;
        }
    } catch(e) {
        console.error('Send error:', e);
        addSys('\u53d1\u9001\u5931\u8d25: ' + e.message);
        _sending = false;
        return;
    }
    // Safety: reset _sending after 5 seconds if no response
    setTimeout(function() { _sending = false; }, 5000);
    startEvalTimeout();
}

// ==================== UI HELPERS ====================
function setStatus(t) { var el = _g('aiStatus'); if (el) el.textContent = t; }
function showInput() {
    var el = _g('inputBox'); if (el) el.style.display = 'block';
    var ta = _g('answerInput'); if (ta) { ta.disabled = false; ta.focus(); }
    var b = _g('camBorder'); if (b) b.classList.add('listening');
}
function hideInput() {
    var el = _g('inputBox'); if (el) el.style.display = 'none';
    var ta = _g('answerInput'); if (ta) ta.disabled = true;
    stopMic();
    var b = _g('camBorder'); if (b) { b.classList.remove('listening'); b.className = 'cam-border'; }
}
function updateDots() {
    for (var i = 1; i <= totalRounds; i++) {
        var d = _g('dot-' + i); if (!d) continue;
        d.className = 'round-dot' + (i < curRound ? ' done' : (i === curRound ? ' active' : ''));
    }
    var el = _g('roundText'); if (el) el.textContent = curRound + ' / ' + totalRounds;
}
function startTimer() {
    timerIV = setInterval(function() {
        timerSec++;
        var m = Math.floor(timerSec / 60).toString().padStart(2, '0');
        var s = (timerSec % 60).toString().padStart(2, '0');
        var el = _g('timer'); if (el) el.textContent = m + ':' + s;
    }, 1000);
}
function addAI(text, round) {
    var el = _g('chatScroll'); if (!el) return;
    var d = document.createElement('div'); d.className = 'cmsg';
    d.innerHTML = '<div class="cmsg-head"><div class="cmsg-avatar ai">BOT</div><span class="cmsg-name ai">\u5c0f\u667a</span><span class="cmsg-round">Round ' + round + '</span></div><div class="cmsg-body ai streaming" id="s-' + round + '"></div>';
    el.appendChild(d);
    streamText('s-' + round, text, function() { el.scrollTop = el.scrollHeight; });
    el.scrollTop = el.scrollHeight;
}
function streamText(id, text, cb) {
    var el = document.getElementById(id); if (!el) return;
    var i = 0;
    var iv = setInterval(function() {
        if (i < text.length) { el.textContent += text[i]; i++; if (cb) cb(); }
        else { clearInterval(iv); el.classList.remove('streaming'); }
    }, 28);
}
function addHuman(text) {
    var el = _g('chatScroll'); if (!el) return;
    var d = document.createElement('div'); d.className = 'cmsg';
    d.innerHTML = '<div class="cmsg-head"><div class="cmsg-avatar human">\ud83d\udc64</div><span class="cmsg-name human">' + esc(candidateName) + '</span></div><div class="cmsg-body human">' + esc(text) + '</div>';
    el.appendChild(d); el.scrollTop = el.scrollHeight;
}
function addSys(t) {
    var el = _g('chatScroll'); if (!el) return;
    var d = document.createElement('div'); d.className = 'cmsg-sys'; d.textContent = t;
    el.appendChild(d); el.scrollTop = el.scrollHeight;
}
function esc(s) { var d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML.replace(/\n/g, '<br>'); }
function showComplete(ev) {
    if (timerIV) clearInterval(timerIV); stopCam();
    var ip = _g('interviewPage'); if (ip) ip.style.display = 'none';
    var cp = _g('completePage'); if (cp) cp.style.display = 'flex';
    var score = ev.overall_score || 0;
    var arc = _g('scoreArc'); if (arc) arc.style.strokeDashoffset = 326.7 * (1 - score / 10);
    var sv = _g('scoreVal'); if (sv) sv.textContent = score.toFixed(1);
    var recMap = { hire: '\u5efa\u8bae\u5f55\u7528', maybe: '\u5f85\u5b9a', no_hire: '\u4e0d\u5efa\u8bae\u5f55\u7528' };
    var tag = _g('recTag'); if (tag) { tag.textContent = recMap[ev.recommendation] || '\u5f85\u5b9a'; tag.className = 'rec-tag ' + ((ev.recommendation) || 'maybe'); }
    var html = '';
    if (ev.summary) html += '<div class="eval-sec"><h3>Summary</h3><p>' + esc(ev.summary) + '</p></div>';
    if (ev.strengths) html += '<div class="eval-sec"><h3>Strengths</h3><p>' + esc(ev.strengths) + '</p></div>';
    if (ev.weaknesses) html += '<div class="eval-sec"><h3>Weaknesses</h3><p>' + esc(ev.weaknesses) + '</p></div>';
    var es = _g('evalSections'); if (es) es.innerHTML = html;
}

// ==================== VOICE CAPTURE (Voice-Only Mode) ====================
function startVoiceCapture() {
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
        addSys('浏览器不支持语音识别，请使用Chrome浏览器');
        setVADState('silence', '浏览器不支持');
        return;
    }
    try { recognition = new SR(); } catch(e) { addSys('语音识别初始化失败'); return; }
    recognition.lang = 'zh-CN';
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    _voiceFinalTranscript = ''; _voiceInterimTranscript = '';

    recognition.onstart = function() {
        micActive = true;
        setVADState('listening', '正在听取...');
        var b = _g('camBorder'); if (b) b.classList.add('listening');
    };

    recognition.onresult = function(e) {
        _voiceInterimTranscript = '';
        for (var i = e.resultIndex; i < e.results.length; i++) {
            if (e.results[i].isFinal) {
                _voiceFinalTranscript += e.results[i][0].transcript;
            } else {
                _voiceInterimTranscript += e.results[i][0].transcript;
            }
        }
        var displayText = _voiceFinalTranscript + _voiceInterimTranscript;
        var lt = _g('liveText');
        if (lt && displayText) { lt.textContent = displayText; lt.style.display = 'block'; }
        setVADState('listening', '识别中...');

        // Reset silence timer
        if (_voiceSilenceTimer) { clearTimeout(_voiceSilenceTimer); _voiceSilenceTimer = null; }
        if (displayText.trim().length > 0) {
            _voiceSilenceTimer = setTimeout(function() {
                if (micActive && !_sending && (_voiceFinalTranscript + _voiceInterimTranscript).trim().length > 0) {
                    setVADState('countdown', '检测到回答完毕，提交中...');
                    sendAnswer();
                }
            }, 3000);
        }
    };

    recognition.onerror = function(e) {
        console.warn('Voice capture error:', e.error);
        if (e.error === 'not-allowed') {
            addSys('麦克风权限被拒绝');
        } else if (e.error === 'network') {
            addSys('语音识别网络错误，请检查VPN');
        }
        stopVoiceCapture();
    };

    recognition.onend = function() {
        if (micActive && !_sending) {
            setTimeout(function() {
                if (micActive && !_sending) {
                    try { recognition.start(); } catch(e) {}
                }
            }, 200);
        }
    };

    try { recognition.start(); } catch(e) { addSys('语音识别启动失败'); }
}

function stopVoiceCapture() {
    micActive = false;
    if (_voiceSilenceTimer) { clearTimeout(_voiceSilenceTimer); _voiceSilenceTimer = null; }
    if (recognition) { try { recognition.stop(); } catch(e) {} recognition = null; }
    var b = _g('camBorder'); if (b) b.classList.remove('listening');
}

function setVADState(state, label) {
    var dot = _g('vadDot'), lbl = _g('vadLabel'), bar = _g('liveBar');
    if (bar) bar.style.display = 'flex';
    if (dot) { dot.className = 'vad-dot'; if (state) dot.classList.add(state); }
    if (lbl) lbl.textContent = label || '';
}

function skipTTS() {
    _ttsMuted = !_ttsMuted;
    _skipTTS = _ttsMuted;
    var sb = _g('skipTTSBtn');
    if (sb) {
        if (_ttsMuted) {
            if (synth) synth.cancel();
            try { if (_ttsAudio) { _ttsAudio.pause(); _ttsAudio.currentTime = 0; } } catch(e) {}
            sb.innerHTML = '\u25b6 \u6062\u590d\u8bed\u97f3';
            sb.style.background = 'rgba(34,197,94,0.85)';
        } else {
            sb.innerHTML = '\u23f9 \u8df3\u8fc7\u8bed\u97f3';
            sb.style.background = 'rgba(99,102,241,0.85)';
        }
    }
}

// Bind done button
(function() {
    var doneBtn = _g('doneBtn');
    if (doneBtn) doneBtn.onclick = function() { sendAnswer(); };
})();
// ==================== INIT ====================
var _heartbeatIV = null;
function startHeartbeat() {
    if (_heartbeatIV) clearInterval(_heartbeatIV);
    _heartbeatIV = setInterval(function() {
        if (socket && socket.connected) {
            socket.emit('ping', {});
        } else {
            addSys('\u8fde\u63a5\u65ad\u5f00\uff0c\u6b63\u5728\u91cd\u8fde...');
            setStatus('\u91cd\u8fde\u4e2d...');
        }
    }, 30000);
}

function bindEvents() {
    var el;
    el = _g('startBtn'); if (el) el.onclick = startInterview;
    el = _g('sendBtn'); if (el) el.onclick = sendAnswer;
    el = _g('micBtn'); if (el) el.onclick = toggleMic;
    el = _g('answerInput'); if (el) el.onkeydown = function(e) {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.stopPropagation(); sendAnswer(); }
    };
}

// Draw welcome avatar on load
try { initCanvas(); drawWelcomeAvatar(); } catch(e) { console.warn('Welcome avatar error:', e); }
bindEvents();
if (synth) synth.onvoiceschanged = function() { synth.getVoices(); };
import * as THREE from 'https://unpkg.com/three@0.150.1/build/three.module.js';
import { FaceLandmarker, FilesetResolver } from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.32/+esm";

window.arState = window.arState || { 
    active: false, 
    videoElement: null, 
    overlayCanvas: null, 
    landmarker: null,
    lastVideoTime: -1
};

const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

function playTone(freq, type, duration, vol = 0.1) {
    if (audioCtx.state === 'suspended') audioCtx.resume();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    gain.gain.setValueAtTime(vol, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.00001, audioCtx.currentTime + duration);
    osc.stop(audioCtx.currentTime + duration);
}

window.setupAR = async () => {
    if (window.arState.landmarker) return true;
    const vision = await FilesetResolver.forVisionTasks("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.32/wasm");
    window.arState.landmarker = await FaceLandmarker.createFromOptions(vision, { 
        baseOptions: { 
            modelAssetPath: "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task", 
            delegate: "GPU" 
        }, 
        runningMode: "VIDEO", 
        numFaces: 1 // Optimized: AI only tracks 1 face now
    });
    return true;
};

class LaserGame {
    constructor() {
        this.canvas = window.arState.overlayCanvas;
        this.video = window.arState.videoElement;
        
        const isMirrored = typeof window.isVideoMirrored !== 'undefined' ? window.isVideoMirrored : true;
        this.canvas.style.transformOrigin = "center center";
        this.canvas.style.transform = isMirrored ? "scaleX(-1)" : "none";

        this.scene = new THREE.Scene();
        this.camera = new THREE.OrthographicCamera(-window.innerWidth/2, window.innerWidth/2, window.innerHeight/2, -window.innerHeight/2, 1, 1000);
        this.camera.position.z = 100;
        this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, alpha: true, antialias: true });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setClearColor(0x000000, 0);

        this.score = 0;
        this.gameStarted = false;
        this.gameOver = false;
        this.enemies =[];
        this.lasers = [];
        this.particles = [];
        this.djs =[]; // Formerly kittens
        this.lastEnemySpawn = 0;
        this.lastBombSpawn = 0;
        this.enemySpawnInterval = 1200;
        this.bombSpawnInterval = 7000;

        // Single Player Setup
        this.player = this.createPlayerData('cyan');

        this.calibrationHistory =[];
        this.maxCalibrationHistory = 30;
        this.stabilityFrames = 12;
        this.recalibrationCooldown = 1800;
        this.positionChangeThreshold = 0.11;
        this.distanceChangeThreshold = 0.25;
        this.currentStabilityCount = 0;
        this.pendingRecalibration = false;
        this.baseFaceDistance = 0;
        this.lastRecalibrationTime = 0;

        this.textureLoader = new THREE.TextureLoader();
        this.djPositions =[{ x: -0.1, y: -0.15 }, { x: 0.0, y: -0.15 }, { x: 0.1, y: -0.15 }]; // Formerly kittenPositions

        this.buildUI();
        this.initPromise = this.init(); 
    }

    createPlayerData(color) {
        return {
            leftEye: { x: 0, y: 0 }, rightEye: { x: 0, y: 0 },
            mouth: { x: 0, y: 0, isOpen: false },
            smoothGaze: { x: 0.5, y: 0.5 },
            faceCenter: { x: 0.5, y: 0.5 },
            currentFaceCenter: { x: 0.5, y: 0.5 },
            calibrated: false,
            color: color,
            lastLaserTime: 0,
            laserTip: null
        };
    }

    buildUI() {
        if (document.getElementById('laser-game-overlay')) document.getElementById('laser-game-overlay').remove();
        this.ui = document.createElement('div');
        this.ui.id = 'laser-game-overlay';
        this.ui.style.cssText = 'position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none; z-index:2005; font-family:"Share Tech Mono", monospace;';
        
        const eyeMarkup = (id, color) => `<div id="${id}" style="position:absolute; width:18px; height:18px; background:#ebff68; border:4px solid ${color}; border-radius:50%; display:none; transform:translate(-50%,-50%); box-shadow:0 0 12px #68ff98;"></div>`;
        const mouthMarkup = (id) => `<div id="${id}" style="position:absolute; width:68px; height:44px; border-radius:50%; background:radial-gradient(circle, #ff0066 0%, transparent 70%); display:none; transform:translate(-50%,-50%); border:3px solid #ff0066; box-shadow:0 0 15px #ff3399;"></div>`;

        this.ui.innerHTML = `
            <div id="game-score" style="position:absolute; top:85px; left:20px; color:#00ff41; font-size:26px; font-weight:bold; background:rgba(0,0,0,0.75); padding:12px 18px; border:3px solid #00ff41; display:none; letter-spacing:2px;">SCORE: 0</div>
            ${eyeMarkup('pl', '#00ffff')} ${eyeMarkup('pr', '#00ffff')}
            ${mouthMarkup('pm')}
            <div id="game-over-screen" style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); background:rgba(15,15,15,0.96); padding:45px; border:5px solid #ff3b30; color:#ff3b30; text-align:center; display:none; pointer-events:auto; border-radius:8px;">
                <h1 style="margin:0; font-size:42px; letter-spacing:4px;">DJS COMPROMISED</h1>
                <p style="font-size:26px; color:#00ff41; margin:15px 0;">FINAL SCORE: <span id="final-score">0</span></p>
                <button id="restart-game-btn" style="background:#ff3b30; color:#fff; border:none; padding:18px 40px; font-family:inherit; font-size:22px; cursor:pointer; margin-top:15px; letter-spacing:2px;">REBOOT SYSTEM</button>
            </div>
        `;
        document.getElementById('main-container').appendChild(this.ui);
        this.ui.querySelector('#restart-game-btn').onclick = () => this.startGame();
    }

    async init() {
        await this.loadSprites();
        this.setupShaders();
        this.createLaserTips();
    }

    async loadSprites() {
        const load = (f) => new Promise(res => this.textureLoader.load(`/static/${f}`, res, undefined, () => res(null)));[this.ghostTexture, this.ghost2Texture, this.djTexture, this.bombTexture] = await Promise.all([
            load('ghost.png'), load('ghost2.png'), load('dj_bot.png'), load('bomb.png')
        ]);
    }

    setupShaders() {
        this.laserMaterial = new THREE.ShaderMaterial({
            uniforms: { time: { value: 0 }, intensity: { value: 1 }, color: { value: new THREE.Color(0.1, 0.1, 1.0) } },
            vertexShader: `varying vec2 vUv; uniform float time; void main() { vUv = uv; vec3 pos = position; pos.x += sin(time * 20.0 + position.y * 0.1) * 1.8 * (1.0 - abs(uv.y - 0.5) * 2.0); gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0); }`,
            fragmentShader: `uniform float time, intensity; uniform vec3 color; varying vec2 vUv; void main() { float centerDist = abs(vUv.y - 0.5) * 2.0; float beam = 1.0 - smoothstep(0.0, 0.4, centerDist); float core = 1.0 - smoothstep(0.0, 0.15, centerDist); float pulse = sin(time * 25.0) * 0.3 + 0.7; vec3 finalColor = color * (beam * 2.0 + core * 6.0) * pulse * intensity; gl_FragColor = vec4(finalColor, (beam * 2.5 + core * 2.0) * intensity * pulse); }`,
            transparent: true, blending: THREE.AdditiveBlending
        });

        this.laserTipMaterialCyan = new THREE.ShaderMaterial({
            uniforms: { time: { value: 0 }, intensity: { value: 1 } },
            vertexShader: `varying vec2 vUv; uniform float time; void main() { vUv = uv; vec3 pos = position; float swirl = sin(time * 8.0) * 0.8; pos.x += cos(time * 10.0 + pos.y * 0.5) * swirl; pos.y += sin(time * 12.0 + pos.x * 0.5) * swirl; gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0); }`,
            fragmentShader: `uniform float time, intensity; varying vec2 vUv; void main() { vec2 center = vUv - 0.5; float dist = length(center), angle = atan(center.y, center.x); float swirl = sin(angle * 6.0 + time * 15.0 + dist * 20.0) * 0.5 + 0.5; float spiral = sin(angle * 3.0 - time * 8.0 + dist * 15.0) * 0.5 + 0.5; float core = 1.0 - smoothstep(0.0, 0.2, dist); float ring = smoothstep(0.2, 0.6, dist) - smoothstep(0.3, 0.6, dist); float pulse = sin(time * 20.0) * 0.8 + 1.7; vec3 color1 = vec3(0.2, 0.2, 1.0), color2 = vec3(0.2, 0.8, 1.0), color3 = vec3(1.0, 0.8, 0.2); vec3 finalColor = mix(color1, color2, swirl) * core + mix(color2, color3, spiral) * ring; finalColor *= pulse * intensity * 2.0; gl_FragColor = vec4(finalColor, (core + ring * 1.2) * pulse * intensity); }`,
            transparent: true, blending: THREE.AdditiveBlending
        });

        this.explosionMaterial = new THREE.ShaderMaterial({
            uniforms: { time: { value: 0 }, progress: { value: 0 }, intensity: { value: 2 } },
            vertexShader: `varying vec2 vUv; uniform float time, progress; void main() { vUv = uv; vec3 pos = position * (1.0 + progress * 1.0); gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0); }`,
            fragmentShader: `uniform float time, progress, intensity; varying vec2 vUv; void main() { vec2 center = vUv - 0.5; float dist = length(center), angle = atan(center.y, center.x); float rays = sin(angle * 12.0 + time * 20.0) * 0.5 + 0.5; float blast = 1.0 - smoothstep(0.0, progress, dist); float ring = smoothstep(progress * 0.7, progress, dist) * (1.0 - smoothstep(progress, progress * 1.2, dist)); vec3 colors[4]; colors[0] = vec3(1.0, 0.0, 1.0); colors[1] = vec3(0.0, 1.0, 1.0); colors[2] = vec3(1.0, 1.0, 0.0); colors[3] = vec3(1.0, 0.0, 0.0); float colorProgress = dist / progress; vec3 finalColor = colorProgress < 0.33 ? mix(colors[0], colors[1], colorProgress * 3.0) : colorProgress < 0.66 ? mix(colors[1], colors[2], (colorProgress - 0.33) * 3.0) : mix(colors[2], colors[3], (colorProgress - 0.66) * 3.0); vec3 rainbowRing = vec3(sin(angle * 3.0 + time * 10.0) * 0.5 + 0.5, sin(angle * 3.0 + time * 10.0 + 2.094) * 0.5 + 0.5, sin(angle * 3.0 + time * 10.0 + 4.188) * 0.5 + 0.5); finalColor = mix(finalColor, rainbowRing, ring * 1.0) * (blast + ring * rays) * intensity * (1.2 - progress * 0.6); gl_FragColor = vec4(finalColor, (blast + ring) * intensity * (1.0 - progress)); }`,
            transparent: true, blending: THREE.AdditiveBlending
        });
    }

    createLaserTips() {
        const createTip = (material) => {
            const m = new THREE.Mesh(new THREE.CircleGeometry(85, 48), material);
            m.position.z = 55;
            m.visible = false;
            this.scene.add(m);
            return m;
        };
        this.player.laserTip = createTip(this.laserTipMaterialCyan);
    }

    async startGame() {                          
        if (this.initPromise) {
            await this.initPromise;               
        }
        
        if (!document.getElementById('laser-game-overlay')) {
            this.buildUI();
        }
        
        this.score = 0; 
        this.gameStarted = true; 
        this.gameOver = false;
        document.getElementById('game-score').style.display = 'block';
        document.getElementById('game-score').innerText = "SCORE: 0";
        document.getElementById('game-over-screen').style.display = 'none';[this.enemies, this.lasers, this.particles, this.djs].forEach(arr => {
            arr.forEach(obj => this.scene.remove(obj)); 
            arr.length = 0;
        });

        this.djPositions.forEach(pos => {
            const djObj = new THREE.Mesh(new THREE.PlaneGeometry(95, 95), new THREE.MeshBasicMaterial({ map: this.djTexture, transparent: true, alphaTest: 0.1 }));
            djObj.userData = { alive: true, rel: pos }; 
            this.scene.add(djObj); 
            this.djs.push(djObj);
        });

        this.player.calibrated = false;
        this.calibrationHistory =[];
        this.animate();
        playTone(440, 'sine', 0.2);
    }

    updatePlayer(landmarks, player) {
        const left = landmarks[468], right = landmarks[473];
        if (!left || !right) return;

        const curCenter = { x: (left.x + right.x) / 2, y: (left.y + right.y) / 2 };
        const eyeDistance = Math.hypot(right.x - left.x, right.y - left.y);

        player.leftEye = { x: left.x, y: left.y };
        player.rightEye = { x: right.x, y: right.y };

        const currentFaceData = { center: curCenter, distance: eyeDistance, timestamp: Date.now() };
        this.calibrationHistory.push(currentFaceData);
        if (this.calibrationHistory.length > this.maxCalibrationHistory) this.calibrationHistory.shift();

        if (!player.calibrated) {
            player.faceCenter = { ...curCenter };
            this.baseFaceDistance = eyeDistance;
            player.calibrated = true;
            return;
        }

        this.checkForRecalibration(currentFaceData);

        player.currentFaceCenter = { ...curCenter };
        const distanceRatio = this.baseFaceDistance / eyeDistance;
        const sensitivityScale = Math.max(0.5, Math.min(2.0, distanceRatio));

        const dx = (curCenter.x - player.faceCenter.x) / (0.08 * sensitivityScale);
        const dy = (curCenter.y - player.faceCenter.y) / (0.05 * sensitivityScale);

        player.smoothGaze.x += ((0.5 + dx) - player.smoothGaze.x) * 0.15;
        player.smoothGaze.y += ((0.5 + dy) - player.smoothGaze.y) * 0.15;

        const isMirrored = typeof window.isVideoMirrored !== 'undefined' ? window.isVideoMirrored : true;
        const getX = (v) => (isMirrored ? (1 - v) : v) * window.innerWidth;

        const uiL = document.getElementById('pl'), uiR = document.getElementById('pr');
        uiL.style.display = uiR.style.display = 'block';
        uiL.style.left = getX(left.x) + "px"; uiL.style.top = left.y * window.innerHeight + "px";
        uiR.style.left = getX(right.x) + "px"; uiR.style.top = right.y * window.innerHeight + "px";

        const topLip = landmarks[13], botLip = landmarks[14];
        player.mouth.isOpen = Math.abs(botLip.y - topLip.y) > 0.045;
        const uiM = document.getElementById('pm');
        uiM.style.display = player.mouth.isOpen ? 'block' : 'none';
        if (player.mouth.isOpen) {
            player.mouth.x = (1 - topLip.x);
            player.mouth.y = topLip.y;
            uiM.style.left = getX(topLip.x) + "px";
            uiM.style.top = topLip.y * window.innerHeight + "px";
        }

        if (player.laserTip) {
            player.laserTip.visible = true;
            player.laserTip.position.x = (player.smoothGaze.x - 0.5) * window.innerWidth;
            player.laserTip.position.y = -(player.smoothGaze.y - 0.5) * window.innerHeight;
        }
    }

    checkForRecalibration(currentFaceData) {
        const now = Date.now();
        if (now - this.lastRecalibrationTime < this.recalibrationCooldown) return;
        if (this.calibrationHistory.length < this.stabilityFrames) return;

        const positionChange = Math.hypot(currentFaceData.center.x - this.player.faceCenter.x, currentFaceData.center.y - this.player.faceCenter.y);
        const distanceChange = Math.abs(currentFaceData.distance - this.baseFaceDistance) / this.baseFaceDistance;

        if (positionChange > this.positionChangeThreshold || distanceChange > this.distanceChangeThreshold) {
            if (!this.pendingRecalibration) {
                this.pendingRecalibration = true;
                this.currentStabilityCount = 0;
            }
            this.checkPositionStability();
        } else {
            this.pendingRecalibration = false;
            this.currentStabilityCount = 0;
        }
    }

    checkPositionStability() {
        const recentFrames = this.calibrationHistory.slice(-this.stabilityFrames);
        const avgCenter = { x: recentFrames.reduce((s, f) => s + f.center.x, 0) / recentFrames.length, y: recentFrames.reduce((s, f) => s + f.center.y, 0) / recentFrames.length };
        const avgDistance = recentFrames.reduce((s, f) => s + f.distance, 0) / recentFrames.length;

        const centerVariance = recentFrames.reduce((max, f) => Math.max(max, Math.hypot(f.center.x - avgCenter.x, f.center.y - avgCenter.y)), 0);
        const distanceVariance = recentFrames.reduce((max, f) => Math.max(max, Math.abs(f.distance - avgDistance) / avgDistance), 0);

        if (centerVariance < 0.022 && distanceVariance < 0.09) {
            this.currentStabilityCount++;
            if (this.currentStabilityCount >= this.stabilityFrames) {
                this.performRecalibration(avgCenter, avgDistance);
            }
        } else {
            this.currentStabilityCount = 0;
        }
    }

    performRecalibration(newCenter, newDistance) {
        this.player.faceCenter = { ...newCenter };
        this.baseFaceDistance = newDistance;
        this.lastRecalibrationTime = Date.now();
        this.pendingRecalibration = false;
        this.currentStabilityCount = 0;
    }

    spawnEnemy() {
        const isBomb = Math.random() < 0.18;
        const enemy = new THREE.Mesh(
            new THREE.PlaneGeometry(85, 85),
            new THREE.MeshBasicMaterial({ map: isBomb ? this.bombTexture : (Math.random() > 0.5 ? this.ghost2Texture : this.ghostTexture), transparent: true, alphaTest: 0.1 })
        );
        enemy.position.set((Math.random() - 0.5) * window.innerWidth * 0.9, -window.innerHeight/2 - 80, 0);
        enemy.userData = { 
            type: isBomb ? 'bomb' : 'ghost', 
            health: isBomb ? 3 : 100, 
            speed: isBomb ? 95 : 55 + Math.random() * 35,
            bobSpeed: 5 + Math.random() * 4,
            bobAmount: 25 + Math.random() * 18,
            rotationSpeed: 3 + Math.random() * 3,
            rotationAmount: (20 + Math.random() * 15) * Math.PI / 180,
            timeOffset: Math.random() * Math.PI * 2,
            flashDuration: 0
        };
        this.scene.add(enemy); 
        this.enemies.push(enemy);
    }

    createLaser(startX, startY, endX, endY, playerColor) {
        const distance = Math.hypot(endX - startX, endY - startY) * 3.5;
        const material = this.laserMaterial.clone();
        material.uniforms.color.value = new THREE.Color(playerColor === 'magenta' ? 1 : 0.1, 0.1, playerColor === 'cyan' ? 1 : 0.1);
        
        const laser = new THREE.Mesh(new THREE.CylinderGeometry(4, 4, distance, 8), material);
        
        laser.position.set((startX + endX) / 2, (startY + endY) / 2, 30);
        laser.rotation.z = Math.atan2(endY - startY, endX - startX) - Math.PI / 2;
        laser.userData = { life: 0.1, maxLife: 0.1 }; 
        this.scene.add(laser);
        this.lasers.push(laser);
    }

    getParticleTexture() {
        if (!this._particleTex) {
            const canvas = document.createElement('canvas');
            canvas.width = 64; canvas.height = 64;
            const ctx = canvas.getContext('2d');
            
            const gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
            gradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
            gradient.addColorStop(0.2, 'rgba(255, 255, 255, 0.8)');
            gradient.addColorStop(0.5, 'rgba(255, 255, 255, 0.2)');
            gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
            
            ctx.fillStyle = gradient;
            ctx.fillRect(0, 0, 64, 64);
            
            this._particleTex = new THREE.CanvasTexture(canvas);
        }
        return this._particleTex;
    }

    createParticles(x, y, count = 12, colorType = 'cyan') {
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(count * 3);
        const lives = new Float32Array(count);
        const velocities = new Float32Array(count * 3);
        for (let i = 0; i < count; i++) {
            const idx = i * 3;
            positions[idx] = x; positions[idx+1] = y; positions[idx+2] = 30;
            lives[i] = 1;
            const angle = Math.random() * Math.PI * 2;
            const speed = 80 + Math.random() * 220;
            velocities[idx] = Math.cos(angle) * speed;
            velocities[idx+1] = Math.sin(angle) * speed;
            velocities[idx+2] = (Math.random() - 0.5) * 60;
        }
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('life', new THREE.BufferAttribute(lives, 1));
        geometry.setAttribute('velocity', new THREE.BufferAttribute(velocities, 3));
        
        let colorHex = 0x00ffff;
        if (colorType === 'magenta') colorHex = 0xff00ff;
        if (colorType === 'yellow') colorHex = 0xffff00;
        if (colorType === 'white') colorHex = 0xffffff;

        const particleMesh = new THREE.Points(geometry, new THREE.PointsMaterial({ 
            size: 32, 
            color: colorHex, 
            map: this.getParticleTexture(),
            transparent: true, 
            depthWrite: false, 
            opacity: 1.0,
            blending: THREE.AdditiveBlending 
        }));
        particleMesh.userData = { life: 0.5, lives }; 
        this.scene.add(particleMesh);
        this.particles.push(particleMesh);
    }

    createExplosion(x, y) {
        const exp = new THREE.Mesh(new THREE.CircleGeometry(320, 48), this.explosionMaterial.clone());
        exp.position.set(x, y, 40);
        exp.userData = { life: 1.0 };
        this.scene.add(exp);
        this.particles.push(exp);
        playTone(120, 'sawtooth', 0.45, 0.4);
    }

    fireLaser(player) {
        if (!player.calibrated) return;
        const tx = (player.smoothGaze.x - 0.5) * window.innerWidth;
        const ty = -(player.smoothGaze.y - 0.5) * window.innerHeight;
        const lx = (player.leftEye.x - 0.5) * window.innerWidth;
        const ly = -(player.leftEye.y - 0.5) * window.innerHeight;
        const rx = (player.rightEye.x - 0.5) * window.innerWidth;
        const ry = -(player.rightEye.y - 0.5) * window.innerHeight;

        this.createLaser(lx, ly, tx, ty, player.color);
        this.createLaser(rx, ry, tx, ty, player.color);
        this.checkHit(tx, ty, player.color);
        playTone(820, 'sine', 0.04, 0.035);
    }

    checkHit(x, y, playerColor = 'cyan') {
        for (let i = this.enemies.length - 1; i >= 0; i--) {
            const e = this.enemies[i];
            if (e.userData.type === 'bomb' && Math.hypot(e.position.x - x, e.position.y - y) < 110) {
                e.userData.health--;
                this.createParticles(e.position.x, e.position.y, 6, 'yellow');
                if (e.userData.health <= 0) this.explodeBomb(e);
                return;
            }
            if (e.userData.type === 'ghost' && Math.hypot(e.position.x - x, e.position.y - y) < 95) {
                this.scene.remove(e);
                this.enemies.splice(i, 1);
                this.score++;
                document.getElementById('game-score').innerText = "SCORE: " + this.score;
                this.createParticles(x, y, 12, playerColor);
                playTone(620, 'square', 0.06);
                return;
            }
        }
    }

    explodeBomb(bomb) {
        this.createExplosion(bomb.position.x, bomb.position.y);
        this.scene.remove(bomb);
        this.enemies = this.enemies.filter(e => {
            if (e === bomb) return false;
            if (e.userData.type === 'ghost' && Math.hypot(e.position.x - bomb.position.x, e.position.y - bomb.position.y) < 340) {
                this.scene.remove(e);
                this.score++;
                this.createParticles(e.position.x, e.position.y, 8, 'white');
                return false;
            }
            return true;
        });
        document.getElementById('game-score').innerText = "SCORE: " + this.score;
    }

    checkMouthEating() {
        const p = this.player;
        if (!p.mouth.isOpen || !p.calibrated) return;
        const mx = (p.mouth.x - 0.5) * window.innerWidth;
        const my = -(p.mouth.y - 0.5) * window.innerHeight;
        
        this.enemies = this.enemies.filter(e => {
            if (Math.hypot(e.position.x - mx, e.position.y - my) < 135) {
                this.scene.remove(e);
                if (e.userData.type === 'ghost') {
                    this.score++;
                }
                this.createParticles(e.position.x, e.position.y, 14, p.color);
                document.getElementById('game-score').innerText = "SCORE: " + this.score;
                playTone(280, 'triangle', 0.12, 0.2);
                return false;
            }
            return true;
        });
    }

    checkDjCollisions() {
        for (let i = this.enemies.length - 1; i >= 0; i--) {
            const e = this.enemies[i];
            for (const djObj of this.djs) {
                if (djObj.userData.alive && Math.hypot(e.position.x - djObj.position.x, e.position.y - djObj.position.y) < 55) {
                    djObj.userData.alive = false;
                    djObj.visible = false;
                    this.scene.remove(e);
                    this.enemies.splice(i, 1);
                    this.createParticles(djObj.position.x, djObj.position.y, 18, 'white');
                    if (this.djs.every(dj => !dj.userData.alive)) this.triggerGameOver();
                    playTone(180, 'sawtooth', 0.6, 0.3);
                    return;
                }
            }
        }
    }

    triggerGameOver() {
        this.gameOver = true; 
        this.gameStarted = false;
        document.getElementById('game-over-screen').style.display = 'block';
        document.getElementById('final-score').innerText = this.score;
        playTone(90, 'square', 1.1, 0.6);

        this.lasers.forEach(l => this.scene.remove(l)); this.lasers.length = 0;
        this.enemies.forEach(e => this.scene.remove(e)); this.enemies.length = 0;
    }

    update(dt) {
        if (this.gameOver) return;
        const now = Date.now();
        const time = now * 0.001;

        if (this.player.calibrated) {
            const fx = (this.player.currentFaceCenter.x - 0.5) * window.innerWidth;
            const fy = -(this.player.currentFaceCenter.y - 0.5) * window.innerHeight;
            this.djs.forEach(djObj => {
                if (djObj.userData.alive) {
                    djObj.position.x = fx + djObj.userData.rel.x * window.innerWidth;
                    djObj.position.y = fy - djObj.userData.rel.y * window.innerHeight;
                }
            });
        }

        if (now - this.lastEnemySpawn > this.enemySpawnInterval) {
            this.spawnEnemy();
            this.lastEnemySpawn = now;
            this.enemySpawnInterval = Math.max(520, this.enemySpawnInterval - 18);
        }
        if (now - this.lastBombSpawn > this.bombSpawnInterval) {
            this.spawnEnemy(); 
            this.lastBombSpawn = now;
            this.bombSpawnInterval = 6200 + Math.random() * 4500;
        }
        
        if (this.player.calibrated && now - this.player.lastLaserTime > 165) {
            this.fireLaser(this.player);
            this.player.lastLaserTime = now;
        }

        this.checkMouthEating();
        this.checkDjCollisions();

        this.enemies.forEach((e, i) => {
            const target = this.djs.find(djObj => djObj.userData.alive);
            if (target) {
                const dx = target.position.x - e.position.x;
                const dy = target.position.y - e.position.y;
                const dist = Math.hypot(dx, dy);
                if (dist > 5) {
                    e.position.x += (dx / dist) * e.userData.speed * dt * 0.8;
                    e.position.y += (dy / dist) * e.userData.speed * dt * 0.8;
                }
                if (dist < 48) {
                    if (e.userData.type === 'bomb') this.triggerGameOver();
                    else {
                        target.userData.alive = false;
                        target.visible = false;
                        this.scene.remove(e);
                        this.enemies.splice(i, 1);
                        if (this.djs.filter(djObj => djObj.userData.alive).length === 0) this.triggerGameOver();
                    }
                }
            }
            e.position.y += Math.sin(time * e.userData.bobSpeed + e.userData.timeOffset) * e.userData.bobAmount * dt;
            e.rotation.z = Math.sin(time * e.userData.rotationSpeed + e.userData.timeOffset) * e.userData.rotationAmount;
        });

        this.lasers = this.lasers.filter(l => {
            l.userData.life -= dt;
            if (l.material.uniforms) l.material.uniforms.intensity.value = l.userData.life / l.userData.maxLife;
            if (l.userData.life <= 0) { this.scene.remove(l); return false; }
            return true;
        });

        this.particles = this.particles.filter(p => {
            p.userData.life -= dt;
            
            if (p.material.uniforms?.progress) {
                p.material.uniforms.progress.value = 1 - p.userData.life;
            } else if (p.material.opacity !== undefined) {
                p.material.opacity = Math.max(0, p.userData.life * 2.0);
            }
            
            if (p.userData.lives) {
                const lives = p.userData.lives;
                for (let i = 0; i < lives.length; i++) lives[i] = Math.max(0, lives[i] - dt * 2.0); 
                p.geometry.attributes.life.needsUpdate = true;
            }
            if (p.userData.life <= 0) { this.scene.remove(p); return false; }
            return true;
        });
    }

    animate() {
        if (!this.gameStarted) return;
        requestAnimationFrame(() => this.animate());

        if (window.arState.landmarker && this.video.readyState >= 2 && this.video.currentTime !== window.arState.lastVideoTime) {
            window.arState.lastVideoTime = this.video.currentTime;
            const res = window.arState.landmarker.detectForVideo(this.video, performance.now());
            
            if (res.faceLandmarks && res.faceLandmarks[0]) {
                this.updatePlayer(res.faceLandmarks[0], this.player);
            } else {['pl','pr','pm'].forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; }); 
                this.player.calibrated = false; 
            }
        }

        this.update(0.016);

        const t = Date.now() * 0.001;
        [this.laserMaterial, this.explosionMaterial].forEach(m => { if (m?.uniforms?.time) m.uniforms.time.value = t; });
        if (this.player.laserTip?.material?.uniforms?.time) this.player.laserTip.material.uniforms.time.value = t;

        this.renderer.render(this.scene, this.camera);
    }
}

let activeGame = null;
window.toggleAR = async () => {
    window.arState.active = !window.arState.active;
    if (window.arState.active) {
        window.arState.videoElement = document.getElementById("video-feed"); 
        window.arState.overlayCanvas = document.getElementById("ar-overlay"); 
        await window.setupAR(); 
        if (!activeGame) activeGame = new LaserGame();
        await activeGame.startGame();            
    } else {
        if (activeGame) {
            activeGame.gameStarted = false;
            activeGame.gameOver = true;
            if (document.getElementById('laser-game-overlay')) document.getElementById('laser-game-overlay').remove();[activeGame.enemies, activeGame.lasers, activeGame.particles, activeGame.djs].forEach(arr => {
                arr.forEach(obj => activeGame.scene.remove(obj)); 
                arr.length = 0;
            });
            
            setTimeout(() => {
                if (activeGame && activeGame.renderer) activeGame.renderer.clear();
            }, 50);
        }
    }
};
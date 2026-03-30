import * as THREE from 'https://unpkg.com/three@0.150.1/build/three.module.js';
import { HandLandmarker, FilesetResolver } from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.32/+esm";

window.arState = window.arState || { 
    active: false, 
    videoElement: null, 
    overlayCanvas: null, 
    landmarker: null,
    lastVideoTime: -1
};

// --- SETUP MEDIAPIPE HAND TRACKING ---
window.setupAR = async () => {
    if (window.arState.landmarker) return true;
    const vision = await FilesetResolver.forVisionTasks("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.32/wasm");
    window.arState.landmarker = await HandLandmarker.createFromOptions(vision, { 
        baseOptions: { 
            modelAssetPath: "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task", 
            delegate: "GPU" 
        }, 
        runningMode: "VIDEO", 
        numHands: 1
    });
    return true;
};

class InteractiveTextAR {
    constructor() {
        this.canvas = window.arState.overlayCanvas;
        this.video = window.arState.videoElement;
        
        const isMirrored = typeof window.isVideoMirrored !== 'undefined' ? window.isVideoMirrored : true;
        this.canvas.style.transformOrigin = "center center";
        this.canvas.style.transform = isMirrored ? "scaleX(-1)" : "none";

        // --- THREE.JS SETUP ---
        this.scene = new THREE.Scene();
        // Use Orthographic camera to map 1:1 with screen pixels
        this.camera = new THREE.OrthographicCamera(-window.innerWidth/2, window.innerWidth/2, window.innerHeight/2, -window.innerHeight/2, 1, 1000);
        this.camera.position.z = 100;
        
        this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, alpha: true, antialias: true });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setClearColor(0x000000, 0);

        // Lights for the Gem
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambientLight);
        const dirLight = new THREE.DirectionalLight(0xffffff, 1.5);
        dirLight.position.set(100, 100, 100);
        this.scene.add(dirLight);

        // Create the Red Low-Poly Gem (Dodecahedron)
        const geometry = new THREE.DodecahedronGeometry(60, 0);
        const material = new THREE.MeshStandardMaterial({ 
            color: 0xff0033, 
            roughness: 0.2, 
            metalness: 0.1,
            flatShading: true 
        });
        this.gem = new THREE.Mesh(geometry, material);
        this.gem.scale.set(0, 0, 0); // Hidden initially
        this.scene.add(this.gem);

        // --- STATE & PHYSICS VARIABLES ---
        this.gameStarted = false;
        this.handPos = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
        this.targetGemScale = 0;
        this.currentGemScale = 0;
        this.words =[];
        
        this.buildUI();
        this.setupText("the future of text layout is not css");

        // Handle Window Resize for Text Layout
        window.addEventListener('resize', this.onWindowResize.bind(this));
        
        this.animate();
    }

    buildUI() {
        if (document.getElementById('ar-text-overlay')) document.getElementById('ar-text-overlay').remove();
        
        this.ui = document.createElement('div');
        this.ui.id = 'ar-text-overlay';
        this.ui.style.cssText = 'position:absolute; top:0; left:0; width:100%; height:100%; z-index:2005; display:flex; flex-direction:column; justify-content:center; align-items:center; pointer-events:none; overflow:hidden;';
        
        // Container where the repelling words will live
        this.textContainer = document.createElement('div');
        this.textContainer.style.cssText = 'width: 80%; text-align: center; display: flex; flex-wrap: wrap; justify-content: center; gap: 20px;';
        this.ui.appendChild(this.textContainer);

        // The text input box at the bottom
        this.inputBox = document.createElement('input');
        this.inputBox.type = 'text';
        this.inputBox.placeholder = "type here...";
        this.inputBox.style.cssText = 'position:absolute; bottom: 50px; width: 300px; padding: 12px 20px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.4); background: rgba(0,0,0,0.4); color: white; font-family: "Share Tech Mono", monospace; font-size: 16px; text-align: center; pointer-events: auto; outline: none; backdrop-filter: blur(10px);';
        
        this.inputBox.addEventListener('input', (e) => {
            this.setupText(e.target.value || "type something");
        });

        this.ui.appendChild(this.inputBox);
        document.getElementById('main-stage').appendChild(this.ui);
    }

    setupText(textString) {
        this.textContainer.innerHTML = '';
        this.words =[];

        const wordsArray = textString.split(' ');
        
        wordsArray.forEach(wordStr => {
            const span = document.createElement('span');
            span.innerText = wordStr;
            span.style.cssText = `
                color: transparent;
                -webkit-text-stroke: 3px #ccff00;
                font-family: 'Inter', 'Share Tech Mono', sans-serif;
                font-size: 8vw;
                font-weight: 900;
                text-transform: lowercase;
                display: inline-block;
                will-change: transform;
            `;
            this.textContainer.appendChild(span);

            this.words.push({
                element: span,
                baseX: 0,
                baseY: 0,
                currentOffsetX: 0,
                currentOffsetY: 0
            });
        });

        // Use a timeout to allow the browser to flow the text, then measure bases
        setTimeout(() => this.measureBasePositions(), 50);
    }

    measureBasePositions() {
        this.words.forEach(wordObj => {
            // Reset transforms to get natural layout positions
            wordObj.element.style.transform = `translate(0px, 0px)`;
            const rect = wordObj.element.getBoundingClientRect();
            // Store the center of the word in screen space
            wordObj.baseX = rect.left + rect.width / 2;
            wordObj.baseY = rect.top + rect.height / 2;
        });
    }

    onWindowResize() {
        this.camera.left = -window.innerWidth / 2;
        this.camera.right = window.innerWidth / 2;
        this.camera.top = window.innerHeight / 2;
        this.camera.bottom = -window.innerHeight / 2;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.measureBasePositions();
    }

    updatePhysics() {
        const repelRadius = 250; // How far the gem pushes text
        const maxPush = 150;     // Max pixels a word can be pushed

        this.words.forEach(wordObj => {
            let targetOffsetX = 0;
            let targetOffsetY = 0;

            // Only apply force if the gem is visible (pinched)
            if (this.currentGemScale > 0.1) {
                const dx = wordObj.baseX - this.handPos.x;
                const dy = wordObj.baseY - this.handPos.y;
                const dist = Math.hypot(dx, dy);

                if (dist < repelRadius && dist > 0) {
                    const force = Math.pow((repelRadius - dist) / repelRadius, 1.5); // Exponential falloff
                    targetOffsetX = (dx / dist) * force * maxPush;
                    targetOffsetY = (dy / dist) * force * maxPush;
                }
            }

            // Lerp (smoothly move) current offset towards target offset
            wordObj.currentOffsetX += (targetOffsetX - wordObj.currentOffsetX) * 0.15;
            wordObj.currentOffsetY += (targetOffsetY - wordObj.currentOffsetY) * 0.15;

            // Apply to DOM
            wordObj.element.style.transform = `translate(${wordObj.currentOffsetX}px, ${wordObj.currentOffsetY}px)`;
        });
    }

    animate() {
        if (!this.gameStarted) return;
        requestAnimationFrame(() => this.animate());

        const isMirrored = typeof window.isVideoMirrored !== 'undefined' ? window.isVideoMirrored : true;

        if (window.arState.landmarker && this.video.readyState >= 2 && this.video.currentTime !== window.arState.lastVideoTime) {
            window.arState.lastVideoTime = this.video.currentTime;
            const res = window.arState.landmarker.detectForVideo(this.video, performance.now());
            
            if (res.landmarks && res.landmarks[0]) {
                const hand = res.landmarks[0];
                const thumbTip = hand[4];
                const indexTip = hand[8];

                // Calculate pinch distance
                const pinchDist = Math.hypot(thumbTip.x - indexTip.x, thumbTip.y - indexTip.y);
                const isPinched = pinchDist < 0.08;

                // Midpoint between thumb and index
                const midX = (thumbTip.x + indexTip.x) / 2;
                const midY = (thumbTip.y + indexTip.y) / 2;

                // Convert normalized hand coords to Screen Pixels
                const screenX = isMirrored ? (1 - midX) * window.innerWidth : midX * window.innerWidth;
                const screenY = midY * window.innerHeight;

                // Smoothly update hand tracking position
                this.handPos.x += (screenX - this.handPos.x) * 0.3;
                this.handPos.y += (screenY - this.handPos.y) * 0.3;

                this.targetGemScale = isPinched ? 1 : 0;
            } else {
                this.targetGemScale = 0; // Hide gem if hand lost
            }
        }

        // Smoothly scale the Gem
        this.currentGemScale += (this.targetGemScale - this.currentGemScale) * 0.2;
        this.gem.scale.set(this.currentGemScale, this.currentGemScale, this.currentGemScale);

        // Update Gem Position in Three.js (map Screen space to Ortho space)
        this.gem.position.x = this.handPos.x - window.innerWidth / 2;
        this.gem.position.y = -(this.handPos.y - window.innerHeight / 2);

        // Rotate Gem
        this.gem.rotation.x += 0.02;
        this.gem.rotation.y += 0.03;

        // Apply Repulsion Physics to Text
        this.updatePhysics();

        this.renderer.render(this.scene, this.camera);
    }

    startGame() {
        this.gameStarted = true;
    }

    stop() {
        this.gameStarted = false;
        if (this.ui) this.ui.remove();
        window.removeEventListener('resize', this.onWindowResize.bind(this));
    }
}

let activeApp = null;

// --- EXPORTED TOGGLE FUNCTION FOR APP.PY ---
window.toggleAR = async () => {
    window.arState.active = !window.arState.active;
    
    const videoEl = document.getElementById("video-feed");

    if (window.arState.active) {
        window.arState.videoElement = videoEl; 
        window.arState.overlayCanvas = document.getElementById("ar-overlay"); 
        
        // Apply the Black & White filter to match the video vibe
        videoEl.style.filter = "grayscale(100%) contrast(120%) brightness(0.9)";

        await window.setupAR(); 
        
        if (!activeApp) activeApp = new InteractiveTextAR();
        activeApp.startGame();            
    } else {
        // Restore normal video styling
        videoEl.style.filter = "contrast(110%) brightness(0.9)";

        if (activeApp) {
            activeApp.stop();
            setTimeout(() => {
                if (activeApp && activeApp.renderer) activeApp.renderer.clear();
                activeApp = null;
            }, 50);
        }
    }
};

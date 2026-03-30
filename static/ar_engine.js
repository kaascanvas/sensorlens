import * as THREE from 'https://unpkg.com/three@0.150.1/build/three.module.js';
import { HandLandmarker, FilesetResolver } from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.32/+esm";

window.arState = window.arState || { 
    active: false, 
    videoElement: null, 
    overlayCanvas: null, 
    landmarker: null,
    lastVideoTime: -1
};

// --- INJECT GOOGLE FONT ---
const fontLink = document.createElement('link');
fontLink.rel = 'stylesheet';
fontLink.href = 'https://fonts.googleapis.com/css2?family=Titan+One&display=swap';
document.head.appendChild(fontLink);

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
        numHands: 2 // Upgraded to 2 hands for the create/scale gestures
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
        this.camera = new THREE.OrthographicCamera(-window.innerWidth/2, window.innerWidth/2, window.innerHeight/2, -window.innerHeight/2, 1, 1000);
        this.camera.position.z = 100;
        
        this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, alpha: true, antialias: true });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setClearColor(0x000000, 0);

        // Lighting for solid shapes
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
        this.scene.add(ambientLight);
        const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
        dirLight.position.set(200, 300, 200);
        this.scene.add(dirLight);

        // --- STATE & PHYSICS VARIABLES ---
        this.gameStarted = false;
        this.words =[];
        
        // --- GESTURE VARIABLES ---
        this.shapes =[];
        this.currentShape = null;
        this.isPinchingDouble = false;
        this.shapeScale = 1;
        this.originalDistance = null;
        this.selectedShape = null;
        this.shapeCreatedThisPinch = false;
        this.lastShapeCreationTime = 0;
        this.shapeCreationCooldown = 1000;
        
        this.neonColors =[0xFF00FF, 0x00FFFF, 0xFF3300, 0x39FF14, 0xFF0099, 0x00FF00, 0xFF6600, 0xFFFF00];
        this.colorIndex = 0;

        this.buildUI();
        this.setupText("the future of text layout is not css");

        window.addEventListener('resize', this.onWindowResize.bind(this));
        
        this.animate();
    }

    buildUI() {
        if (document.getElementById('ar-text-overlay')) document.getElementById('ar-text-overlay').remove();
        
        this.ui = document.createElement('div');
        this.ui.id = 'ar-text-overlay';
        this.ui.style.cssText = 'position:absolute; top:0; left:0; width:100%; height:100%; z-index:2005; display:flex; flex-direction:column; justify-content:center; align-items:center; pointer-events:none; overflow:hidden; padding: 40px; box-sizing: border-box;';
        
        // Container where the repelling words will live (Fills screen, wraps text)
        this.textContainer = document.createElement('div');
        this.textContainer.style.cssText = 'width: 100%; height: 100%; text-align: center; display: flex; flex-wrap: wrap; justify-content: center; align-content: center; gap: 2vw;';
        this.ui.appendChild(this.textContainer);

        // Recycle Bin
        this.recycleBin = document.createElement('img');
        this.recycleBin.src = '/static/recyclebin.png'; // Make sure you have this file!
        this.recycleBin.alt = '🗑️';
        this.recycleBin.style.cssText = 'position:absolute; bottom: 40px; right: 40px; width: 80px; height: 80px; opacity: 0.5; transition: 0.3s ease; object-fit: contain; filter: drop-shadow(0 0 10px rgba(255,0,0,0));';
        this.ui.appendChild(this.recycleBin);

        // The text input box at the bottom
        this.inputBox = document.createElement('input');
        this.inputBox.type = 'text';
        this.inputBox.placeholder = "type here...";
        this.inputBox.style.cssText = 'position:absolute; bottom: 50px; width: 300px; padding: 12px 20px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.4); background: rgba(0,0,0,0.6); color: white; font-family: "Share Tech Mono", monospace; font-size: 16px; text-align: center; pointer-events: auto; outline: none; backdrop-filter: blur(10px); box-shadow: 0 10px 30px rgba(0,0,0,0.5);';
        
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
                font-family: 'Titan One', sans-serif;
                font-size: clamp(3rem, 8vw, 12rem); /* Adapts to screen size */
                line-height: 1.1;
                text-transform: lowercase;
                display: inline-block;
                will-change: transform;
                text-shadow: 0 0 15px rgba(204, 255, 0, 0.2);
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

        // Delay measurement to let the browser reflow the flexbox
        setTimeout(() => this.measureBasePositions(), 100);
    }

    measureBasePositions() {
        this.words.forEach(wordObj => {
            wordObj.element.style.transform = `translate(0px, 0px)`;
            const rect = wordObj.element.getBoundingClientRect();
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

    // --- 3D SHAPE GENERATION ---
    getNextNeonColor() {
        const color = this.neonColors[this.colorIndex];
        this.colorIndex = (this.colorIndex + 1) % this.neonColors.length;
        return color;
    }

    createRandomShape(screenX, screenY) {
        const geometries =[
            new THREE.BoxGeometry(60, 60, 60),
            new THREE.SphereGeometry(40, 32, 32),
            new THREE.ConeGeometry(40, 80, 32),
            new THREE.DodecahedronGeometry(45, 0)
        ];
        const geometry = geometries[Math.floor(Math.random() * geometries.length)];
        const color = this.getNextNeonColor();
        const group = new THREE.Group();

        // Solid Fill
        const material = new THREE.MeshStandardMaterial({ 
            color: color, 
            roughness: 0.3,
            metalness: 0.2
        });
        const fillMesh = new THREE.Mesh(geometry, material);

        // White Wireframe Overlay
        const wireframeMaterial = new THREE.MeshBasicMaterial({ color: 0xffffff, wireframe: true, transparent: true, opacity: 0.6 });
        const wireframeMesh = new THREE.Mesh(geometry, wireframeMaterial);
        // Slightly scale up wireframe to prevent z-fighting
        wireframeMesh.scale.set(1.02, 1.02, 1.02);

        group.add(fillMesh);
        group.add(wireframeMesh);
        
        group.position.x = screenX - window.innerWidth / 2;
        group.position.y = -(screenY - window.innerHeight / 2);
        group.position.z = 20;

        this.scene.add(group);
        this.shapes.push(group);
        return group;
    }

    findNearestShape(screenX, screenY) {
        let minDist = Infinity;
        let closest = null;
        const threeX = screenX - window.innerWidth / 2;
        const threeY = -(screenY - window.innerHeight / 2);

        this.shapes.forEach(shape => {
            const dist = Math.hypot(shape.position.x - threeX, shape.position.y - threeY);
            // Grab threshold based on scale
            if (dist < 80 * shape.scale.x && dist < minDist) {
                minDist = dist;
                closest = shape;
            }
        });
        return closest;
    }

    isInRecycleBinZone(screenX, screenY) {
        const binRect = this.recycleBin.getBoundingClientRect();
        // Add a 20px forgiving padding around the bin
        return (
            screenX >= binRect.left - 20 &&
            screenX <= binRect.right + 20 &&
            screenY >= binRect.top - 20 &&
            screenY <= binRect.bottom + 20
        );
    }

    // --- PHYSICS ENGINE ---
    updatePhysics() {
        const repelRadius = 280; 
        const maxPush = 200;     

        this.words.forEach(wordObj => {
            let targetOffsetX = 0;
            let targetOffsetY = 0;

            // Calculate repulsion for ALL active shapes
            this.shapes.forEach(shape => {
                // Convert Three.js coords back to Screen space
                const shapeScreenX = shape.position.x + window.innerWidth / 2;
                const shapeScreenY = -(shape.position.y - window.innerHeight / 2);

                const dx = wordObj.baseX - shapeScreenX;
                const dy = wordObj.baseY - shapeScreenY;
                const dist = Math.hypot(dx, dy);

                // Multiply repel radius by the shape's scale so big shapes push more
                const effectiveRadius = repelRadius * Math.max(0.5, shape.scale.x);

                if (dist < effectiveRadius && dist > 0) {
                    const force = Math.pow((effectiveRadius - dist) / effectiveRadius, 1.8); 
                    targetOffsetX += (dx / dist) * force * maxPush;
                    targetOffsetY += (dy / dist) * force * maxPush;
                }
            });

            // Smoothly move current offset towards target offset
            wordObj.currentOffsetX += (targetOffsetX - wordObj.currentOffsetX) * 0.15;
            wordObj.currentOffsetY += (targetOffsetY - wordObj.currentOffsetY) * 0.15;

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
            
            // Helper to get Screen Coordinates from normalized landmarks
            const getScreenPos = (landmark) => ({
                x: (isMirrored ? (1 - landmark.x) : landmark.x) * window.innerWidth,
                y: landmark.y * window.innerHeight
            });

            const isPinch = (hand) => Math.hypot(hand[4].x - hand[8].x, hand[4].y - hand[8].y) < 0.06;

            if (res.landmarks && res.landmarks.length > 0) {
                
                // TWO HANDS DETECTED: CREATE & SCALE
                if (res.landmarks.length === 2) {
                    const[l, r] = res.landmarks;
                    const leftPinch = isPinch(l);
                    const rightPinch = isPinch(r);
                    
                    const leftPos = getScreenPos(l[8]);
                    const rightPos = getScreenPos(r[8]);
                    const distBetweenHands = Math.hypot(leftPos.x - rightPos.x, leftPos.y - rightPos.y);
                    const indexesClose = distBetweenHands < 180; // pixels

                    if (leftPinch && rightPinch) {
                        const centerX = (leftPos.x + rightPos.x) / 2;
                        const centerY = (leftPos.y + rightPos.y) / 2;

                        if (!this.isPinchingDouble) {
                            const now = Date.now();
                            if (!this.shapeCreatedThisPinch && indexesClose && now - this.lastShapeCreationTime > this.shapeCreationCooldown) {
                                this.currentShape = this.createRandomShape(centerX, centerY);
                                this.lastShapeCreationTime = now;
                                this.shapeCreatedThisPinch = true;
                                this.originalDistance = distBetweenHands;
                            }
                        } else if (this.currentShape && this.originalDistance) {
                            // Scale shape based on hand distance
                            this.shapeScale = Math.max(0.2, distBetweenHands / this.originalDistance);
                            this.currentShape.scale.set(this.shapeScale, this.shapeScale, this.shapeScale);
                            
                            // Keep shape centered between hands while scaling
                            this.currentShape.position.x = centerX - window.innerWidth / 2;
                            this.currentShape.position.y = -(centerY - window.innerHeight / 2);
                        }

                        this.isPinchingDouble = true;
                        this.recycleBin.style.opacity = '0.5';
                        this.recycleBin.style.filter = 'drop-shadow(0 0 0px rgba(255,0,0,0))';
                    } else {
                        this.isPinchingDouble = false;
                        this.shapeCreatedThisPinch = false;
                        this.originalDistance = null;
                        this.currentShape = null;
                    }
                } 
                
                // SINGLE HAND (OR INDEPENDENT HANDS): DRAG & DELETE
                if (!this.isPinchingDouble) {
                    let anyHandPinching = false;
                    let activeHandPos = null;

                    for (const hand of res.landmarks) {
                        if (isPinch(hand)) {
                            anyHandPinching = true;
                            activeHandPos = getScreenPos(hand[8]);
                            
                            if (!this.selectedShape) {
                                this.selectedShape = this.findNearestShape(activeHandPos.x, activeHandPos.y);
                            }

                            if (this.selectedShape) {
                                // Drag the shape
                                this.selectedShape.position.x = activeHandPos.x - window.innerWidth / 2;
                                this.selectedShape.position.y = -(activeHandPos.y - window.innerHeight / 2);

                                // Check Recycle Bin
                                const inBin = this.isInRecycleBinZone(activeHandPos.x, activeHandPos.y);
                                
                                // Turn wireframe red if in bin
                                this.selectedShape.children.forEach(child => {
                                    if (child.material && child.material.wireframe) {
                                        child.material.color.setHex(inBin ? 0xff0000 : 0xffffff);
                                    }
                                });

                                if (inBin) {
                                    this.recycleBin.style.opacity = '1';
                                    this.recycleBin.style.filter = 'drop-shadow(0 0 20px rgba(255,0,0,0.8))';
                                    this.recycleBin.style.transform = 'scale(1.2)';
                                } else {
                                    this.recycleBin.style.opacity = '0.5';
                                    this.recycleBin.style.filter = 'drop-shadow(0 0 0px rgba(255,0,0,0))';
                                    this.recycleBin.style.transform = 'scale(1)';
                                }
                            }
                            break; // Only handle one pinch drag at a time
                        }
                    }

                    // Release pinch logic
                    if (!anyHandPinching) {
                        if (this.selectedShape && activeHandPos && this.isInRecycleBinZone(activeHandPos.x, activeHandPos.y)) {
                            // Destroy Shape
                            this.scene.remove(this.selectedShape);
                            this.shapes = this.shapes.filter(s => s !== this.selectedShape);
                        } else if (this.selectedShape) {
                            // Reset wireframe color
                            this.selectedShape.children.forEach(child => {
                                if (child.material && child.material.wireframe) {
                                    child.material.color.setHex(0xffffff);
                                }
                            });
                        }
                        this.selectedShape = null;
                        this.recycleBin.style.opacity = '0.5';
                        this.recycleBin.style.filter = 'drop-shadow(0 0 0px rgba(255,0,0,0))';
                        this.recycleBin.style.transform = 'scale(1)';
                    }
                }
            } else {
                // No hands detected
                this.isPinchingDouble = false;
                this.selectedShape = null;
            }
        }

        // Rotate all idle shapes
        this.shapes.forEach(shape => {
            if (shape !== this.selectedShape && shape !== this.currentShape) {
                shape.rotation.x += 0.01;
                shape.rotation.y += 0.01;
            }
        });

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

window.toggleAR = async () => {
    window.arState.active = !window.arState.active;
    const videoEl = document.getElementById("video-feed");

    if (window.arState.active) {
        window.arState.videoElement = videoEl; 
        window.arState.overlayCanvas = document.getElementById("ar-overlay"); 
        
        // B&W Filter
        videoEl.style.filter = "grayscale(100%) contrast(120%) brightness(0.9)";

        await window.setupAR(); 
        
        if (!activeApp) activeApp = new InteractiveTextAR();
        activeApp.startGame();            
    } else {
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

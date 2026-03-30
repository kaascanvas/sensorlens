const fontLink = document.createElement('link');
fontLink.rel = 'stylesheet';
fontLink.href = 'https://fonts.googleapis.com/css2?family=Rubik+Mono+One&display=swap';
document.head.appendChild(fontLink);

window.arState = window.arState || { 
    active: false, 
    videoElement: null, 
    overlayCanvas: null 
};

window.setupAR = async () => {
    return true; 
};

class DJTextOverlay {
    constructor() {
        this.video = window.arState.videoElement;
        this.currentText = "lens dna DJ flyer text";

        this.buildUI();
        this.setupText(this.currentText);

        this.resizeHandler = this.adjustFontSize.bind(this);
        window.addEventListener('resize', this.resizeHandler);
    }

    buildUI() {
        if (document.getElementById('ar-text-overlay')) {
            document.getElementById('ar-text-overlay').remove();
        }
        
        this.ui = document.createElement('div');
        this.ui.id = 'ar-text-overlay';
        this.ui.style.cssText = 'position:absolute; top:0; left:0; width:100%; height:100%; z-index:2005; display:flex; flex-direction:column; justify-content:center; align-items:center; pointer-events:none; overflow:hidden;';
        
        if (!document.getElementById('dj-pulse-style')) {
            const style = document.createElement('style');
            style.id = 'dj-pulse-style';
            style.innerHTML = `
                @keyframes djPulse {
                    0% { transform: scale(1); }
                    50% { transform: scale(1.03); }
                    100% { transform: scale(1); }
                }
                .dj-text-container {
                    animation: djPulse 1.2s infinite cubic-bezier(0.25, 0.46, 0.45, 0.94);
                }
            `;
            document.head.appendChild(style);
        }

        this.textContainer = document.createElement('div');
        this.textContainer.className = 'dj-text-container';
        this.textContainer.style.cssText = 'position: absolute; top: 10%; left: 5%; width: 90%; height: 70%; text-align: center; display: flex; flex-wrap: wrap; justify-content: center; align-content: center; gap: 1vw;';
        this.ui.appendChild(this.textContainer);

        this.inputBox = document.createElement('input');
        this.inputBox.type = 'text';
        this.inputBox.placeholder = "type here...";
        this.inputBox.style.cssText = 'position:absolute; bottom: 50px; width: 80%; max-width: 400px; padding: 15px 20px; border-radius: 12px; border: 2px solid #ccff00; background: rgba(0,0,0,0.7); color: #ccff00; font-family: "Share Tech Mono", monospace; font-size: 18px; text-align: center; pointer-events: auto; outline: none; backdrop-filter: blur(10px); box-shadow: 0 10px 30px rgba(0,0,0,0.5), 0 0 15px rgba(204,255,0,0.2); text-transform: lowercase;';
        
        this.inputBox.addEventListener('input', (e) => {
            this.currentText = e.target.value || "LENS DNA";
            this.setupText(this.currentText);
        });

        this.ui.appendChild(this.inputBox);
        document.getElementById('main-stage').appendChild(this.ui);
    }

    setupText(textString) {
        this.textContainer.innerHTML = '';
        const wordsArray = textString.split(' ');
        
        wordsArray.forEach(wordStr => {
            const span = document.createElement('span');
            span.innerText = wordStr;
            span.style.cssText = `
                color: #ccff00;
                -webkit-text-stroke: 2px #000;
                text-shadow: 4px 4px 0px #000, 0 0 20px rgba(204, 255, 0, 0.3);
                font-family: 'Rubik Mono One', sans-serif;
                line-height: 1.1;
                text-transform: lowercase;
                display: inline-block;
                margin: 0 10px;
                will-change: transform;
            `;
            this.textContainer.appendChild(span);
        });

        this.adjustFontSize();
    }

    adjustFontSize() {
        if (!this.textContainer) return;
        
        const textLength = this.currentText.length || 1;
        const width = this.textContainer.clientWidth;
        const height = this.textContainer.clientHeight;
        
        const area = width * height;
        const areaPerChar = area / (textLength * 1.5); 
        
        let optimalFontSize = Math.sqrt(areaPerChar);
        
        const maxFont = height * 0.35; 
        const minFont = 24;
        optimalFontSize = Math.max(minFont, Math.min(optimalFontSize, maxFont));
        
        Array.from(this.textContainer.children).forEach(span => {
            span.style.fontSize = `${optimalFontSize}px`;
        });
    }

    stop() {
        if (this.ui) this.ui.remove();
        window.removeEventListener('resize', this.resizeHandler);
    }
}

let activeApp = null;

window.toggleAR = async () => {
    window.arState.active = !window.arState.active;
    
    const videoEl = document.getElementById("video-feed");
    const overlayCanvas = document.getElementById("ar-overlay");

    if (window.arState.active) {
        window.arState.videoElement = videoEl; 
        
        if (overlayCanvas) {
            const ctx = overlayCanvas.getContext('2d');
            ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
            overlayCanvas.style.display = 'none';
        }

        videoEl.style.filter = "grayscale(100%) contrast(120%) brightness(0.9)";
        
        if (!activeApp) activeApp = new DJTextOverlay();
    } else {
        videoEl.style.filter = "contrast(110%) brightness(0.9)";
        if (overlayCanvas) overlayCanvas.style.display = 'block';

        if (activeApp) {
            activeApp.stop();
            activeApp = null;
        }
    }
};

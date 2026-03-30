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
        this.words =[];
        this.resizeObserver = null;
        this.currentText = "the future of text layout is not css";

        this.buildUI();
        this.setupText(this.currentText);

        window.addEventListener('resize', this.adjustFontSize.bind(this));
    }

    buildUI() {
        if (document.getElementById('ar-text-overlay')) {
            document.getElementById('ar-text-overlay').remove();
        }
        
        this.ui = document.createElement('div');
        this.ui.id = 'ar-text-overlay';
        this.ui.style.cssText = 'position:absolute; top:0; left:0; width:100%; height:100%; z-index:2005; display:flex; flex-direction:column; justify-content:center; align-items:center; pointer-events:none; overflow:hidden;';
        
        // CSS Animation for a subtle "club beat" pulse
        const style = document.createElement('style');
        style.innerHTML = `
            @keyframes djPulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.02); }
                100% { transform: scale(1); }
            }
            .dj-text-container {
                animation: djPulse 1.5s infinite ease-in-out;
            }
        `;
        document.head.appendChild(style);

        this.textContainer = document.createElement('div');
        this.textContainer.className = 'dj-text-container';
        this.textContainer.style.cssText = 'position: absolute; top: 5%; left: 5%; width: 90%; height: 75%; text-align: center; display: flex; flex-wrap: wrap; justify-content: center; align-content: center; gap: 1vw;';
        this.ui.appendChild(this.textContainer);

        this.inputBox = document.createElement('input');
        this.inputBox.type = 'text';
        this.inputBox.placeholder = "type here...";
        this.inputBox.style.cssText = 'position:absolute; bottom: 50px; width: 80%; max-width: 400px; padding: 15px 20px; border-radius: 12px; border: 2px solid #ccff00; background: rgba(0,0,0,0.7); color: #ccff00; font-family: "Share Tech Mono", monospace; font-size: 18px; text-align: center; pointer-events: auto; outline: none; backdrop-filter: blur(10px); box-shadow: 0 10px 30px rgba(0,0,0,0.5), 0 0 15px rgba(204,255,0,0.2); text-transform: uppercase;';
        
        this.inputBox.addEventListener('input', (e) => {
            this.currentText = e.target.value || "TYPE SOMETHING";
            this.setupText(this.currentText);
        });

        this.ui.appendChild(this.inputBox);
        document.getElementById('main-stage').appendChild(this.ui);
    }

    setupText(textString) {
        this.textContainer.innerHTML = '';
        this.words =

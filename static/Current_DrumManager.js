import * as Tone from 'https://esm.sh/tone';

let players = null;
let loopPlayer = null; // Used for the "sweeping rhythm" in AI Mode (drums.wav)
let isLoaded = false;
let sequence = null;
let beatIndex = 0;
let activeDrums = new Set();

// The improved, more varied and syncopated drum patterns
let drumPattern = {
    // Syncopated kick pattern
    'kick':[true, false, false, false, false, true, false, false, true, false, false, true, false, true, false, false],
    // Snare on the backbeat (beats 2 and 4)
    'snare':[false, false, false, false, true, false, false, false, false, false, false, false, true, false, false, false],
    // Open hi-hat feel on the off-beats
    'hihat':[false, true, false, true, false, true, false, true, false, true, false, true, false, true, false, true],
    // Clap layered with snare, plus syncopated hit
    'clap':[false, false, false, false, true, false, false, true, false, false, false, false, true, false, false, false]
};

const fingerToDrumMap = {
    'index': 'kick', 'middle': 'snare', 'ring': 'hihat', 'pinky': 'clap'
};

export function loadSamples() {
    return new Promise((resolve, reject) => {
        if (isLoaded) return resolve();

        // Load the new sweeping rhythm specifically for the AI
        loopPlayer = new Tone.Player({
            url: '/static/assets/drums.wav',
            loop: true,
            autostart: false,
            volume: -Infinity // Starts silent until AI kicks in
        }).toDestination();
        
        // Sync the background loop so it respects the tempo
        loopPlayer.sync().start(0);

        players = new Tone.Players({
            urls: {
                kick: '/static/assets/kick.wav',
                snare: '/static/assets/snare.wav',
                hihat: '/static/assets/hihat.wav',
                clap: '/static/assets/clap.wav',
                // Keep FX oneshots available for gestures
                vox_hey: '/static/assets/vox_hey.wav',
                vox_drop: '/static/assets/vox_drop.wav',
                crash: '/static/assets/crash.wav',
                vox: '/static/assets/vox.wav'
            },
            onload: () => {
                isLoaded = true;
                players.player('kick').volume.value = -6; 
                players.player('snare').volume.value = 0;
                players.player('hihat').volume.value = -2; 
                players.player('clap').volume.value = 0;
                
                // Set volumes for oneshots
                try {
                    players.player('crash').volume.value = -2;
                    players.player('vox_hey').volume.value = 2;
                    players.player('vox_drop').volume.value = 4;
                } catch(e){}

                console.log("🔥 All Drum & Loop samples loaded.");
                resolve();
            },
            onerror: (e) => reject(e)
        }).toDestination();
    });
}

export function startSequence() {
    if (!isLoaded || sequence) return;
    sequence = new Tone.Sequence((time, step) => {
        beatIndex = step; 
        Object.entries(drumPattern).forEach(([drum, pattern]) => {
            if (activeDrums.has(drum) && pattern[step]) {
                try { players.player(drum).start(time); } catch (e) {}
            }
        });
    }, Array.from({ length: 16 }, (_, i) => i), "16n").start(0);
}

// Fade the drums.wav loop in or out (used by AI)
export function setAILoop(isActive) {
    if (!loopPlayer || !loopPlayer.loaded) return;
    if (isActive) {
        loopPlayer.volume.rampTo(-4, 0.5); // Fade in to a nice background level
    } else {
        loopPlayer.volume.rampTo(-Infinity, 0.5); // Fade out
    }
}

export function playOneShot(drumName) {
    if (isLoaded && players.has(drumName)) {
        try { players.player(drumName).start(); } catch(e){}
    }
}

export function updateActiveDrums(fingerStates) {
    activeDrums.clear();
    for (const [finger, isUp] of Object.entries(fingerStates)) {
        if (isUp) activeDrums.add(fingerToDrumMap[finger]);
    }
}

export function enableRide(isEnabled) {
    if (isEnabled) activeDrums.add('hihat');
    else activeDrums.delete('hihat');
}

export function getActiveDrums() { return activeDrums; }
export function getFingerToDrumMap() { return fingerToDrumMap; }
export function getCurrentBeat() { return beatIndex; }
export function getDrumPattern() { return drumPattern; }
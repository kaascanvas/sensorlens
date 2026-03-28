import * as Tone from 'https://esm.sh/tone';

export class MusicManager {
    constructor() {
        this.polySynth = null;
        this.reverb = null;
        this.stereoDelay = null; 
        this.analyser = null; 
        this.isStarted = false;
        this.activePatterns = new Map();
        this.handVolumes = new Map();

        this.synthPresets =[
            // Preset 1: Clean Sine Wave (Default)
            {
                harmonicity: 4, modulationIndex: 3, oscillator: { type: 'sine' },
                envelope: { attack: 0.01, decay: 0.2, sustain: 0.5, release: 1.0 },
                modulation: { type: 'sine' },
                modulationEnvelope: { attack: 0.1, decay: 0.01, sustain: 1, release: 0.5 }
            },
            // Preset 2: Buzzy Sawtooth
            {
                harmonicity: 1, modulationIndex: 8, oscillator: { type: 'sawtooth' },
                envelope: { attack: 0.01, decay: 0.15, sustain: 0.05, release: 0.2 },
                modulation: { type: 'square' },
                modulationEnvelope: { attack: 0.05, decay: 0.2, sustain: 0.4, release: 0.6 }
            },
            // Preset 3: Funk Electric Piano (Rhodes-like)
            {
                harmonicity: 2, modulationIndex: 12, oscillator: { type: 'sine' },
                envelope: { attack: 0.02, decay: 0.3, sustain: 0.2, release: 0.8 },
                modulation: { type: 'sine' },
                modulationEnvelope: { attack: 0.05, decay: 0.2, sustain: 0.1, release: 0.8 },
                effects: { reverbWet: 0.3, delayWet: 0.1 }
            }
        ];
        this.currentSynthIndex = 0;
    }

    async start() {
        if (this.isStarted) return;
        
        await Tone.start();
        this.reverb = new Tone.Reverb({ decay: 5, preDelay: 0.0, wet: 0.8 }).toDestination();
        this.stereoDelay = new Tone.FeedbackDelay("8n", 0.5).connect(this.reverb);
        this.stereoDelay.wet.value = 0; 
        
        this.analyser = new Tone.Analyser('waveform', 1024);
        this.polySynth = new Tone.PolySynth(Tone.FMSynth, this.synthPresets[this.currentSynthIndex]);
        this.polySynth.connect(this.analyser);
        this.analyser.connect(this.stereoDelay);
        this.polySynth.volume.value = 0;
        
        this.isStarted = true;
        Tone.Transport.bpm.value = 100;
        Tone.Transport.start();
        console.log("Tone.js AudioContext started and PolySynth is ready.");
    }

    startArpeggio(handId, rootNote) {
        if (!this.polySynth || this.activePatterns.has(handId)) return;
        
        const chord = Tone.Frequency(rootNote).harmonize([0, 3, 5, 7, 10, 12]);
        const arpeggioNotes = chord.map(freq => Tone.Frequency(freq).toNote());
        
        const pattern = new Tone.Pattern((time, note) => {
            const velocity = this.handVolumes.get(handId) || 0.2;
            this.polySynth.triggerAttackRelease(note, "16n", time, velocity);
        }, arpeggioNotes, "upDown");
        
        pattern.interval = "16n"; 
        pattern.start(0); 
        this.activePatterns.set(handId, { pattern: pattern, currentRoot: rootNote });
    }

    updateArpeggioVolume(handId, velocity) {
        if (this.polySynth && this.activePatterns.has(handId)) {
            const clampedVelocity = Math.max(0, Math.min(1, velocity));
            this.handVolumes.set(handId, clampedVelocity);
            this.polySynth.volume.value = Tone.gainToDb(clampedVelocity);
        }
    }

    updateArpeggio(handId, newRootNote) {
        const activePattern = this.activePatterns.get(handId);
        if (!this.polySynth || !activePattern || activePattern.currentRoot === newRootNote) return;
        
        const newChord = Tone.Frequency(newRootNote).harmonize([0, 3, 5, 7, 10, 12]);
        activePattern.pattern.values = newChord.map(freq => Tone.Frequency(freq).toNote());
        activePattern.currentRoot = newRootNote;
    }

    stopArpeggio(handId) {
        const activePattern = this.activePatterns.get(handId);
        if (activePattern) {
            activePattern.pattern.stop(0); 
            activePattern.pattern.dispose(); 
            this.activePatterns.delete(handId);
            this.handVolumes.delete(handId); 
            if (this.activePatterns.size === 0) {
                this.polySynth.volume.value = -Infinity;
            }
        }
    }

    cycleSynth() {
        if (!this.polySynth) return;
        
        this.activePatterns.forEach((value, key) => this.stopArpeggio(key));
        this.polySynth.dispose();
        
        this.currentSynthIndex = (this.currentSynthIndex + 1) % this.synthPresets.length;
        const newPreset = this.synthPresets[this.currentSynthIndex];
        
        this.polySynth = new Tone.PolySynth(Tone.FMSynth, newPreset);
        this.polySynth.connect(this.analyser);
        this.polySynth.volume.value = 0; 
        
        this.reverb.wet.value = newPreset.effects?.reverbWet ?? 0.8;
        this.stereoDelay.wet.value = newPreset.effects?.delayWet ?? 0;
        console.log(`Switched to synth preset: ${this.currentSynthIndex}`);
    }

    getAnalyser() {
        return this.analyser;
    }
}
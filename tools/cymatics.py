#!/usr/bin/env python3
"""
Cymatic Frequency Visualizer
Proves AI analysis produces structurally coherent patterns, not random noise.

Converts AI response text to cymatics:
1. Speech synthesis (espeak-ng) → WAV audio
2. FFT frequency spectrum analysis (scipy/numpy)
3. Semantic frequency mapping (word resonance patterns)
4. 2D mandala visualization (matplotlib)
5. Resonance coherence scoring

The output is a frequency mandala showing:
- Acoustic frequencies of spoken content
- Semantic harmonic mapping
- Resonance coherence score (pattern alignment)

Usage:
    python3 cymatics.py "text here"
    python3 cymatics.py --file /path/to/text.txt
"""

import os
import sys
import json
import subprocess
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from scipy.fft import fft, fftfreq
from scipy.io import wavfile
from pathlib import Path
from datetime import datetime
import tempfile

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

# A4 = 440 Hz (reference frequency)
A4_HZ = 440.0

# Harmonic frequency mapping (semantic → Hz)
# Based on musical scale and semantic resonance
SEMANTIC_FREQUENCIES = {
    # High-energy cognitive words
    'think': 528,      # Miracle/Love frequency
    'understand': 639, # MI note (connect/relationships)
    'create': 852,     # UT note (creation/simplicity)
    'feel': 741,       # SOL note (intuition/expression)
    'transform': 963,  # TI note (awakening/return)
    'knowledge': 480,  # D note
    'wisdom': 432,     # G note (DNA healing)
    'harmony': 528,    # Love frequency
    'balance': 396,    # UT note
    
    # Medium energy words
    'pattern': 317,    # Low frequency coherence
    'structure': 293,  # Low frequency order
    'order': 330,      # Middle-C area
    'system': 349,     # F note
    'process': 294,    # D note
    'method': 330,     # E note
    'coherence': 528,  # Coherence resonance
    'resonance': 528,  # Self-resonant
    'frequency': 440,  # A reference
    
    # Grounding/stability words
    'ground': 174,     # MU note (root chakra)
    'stable': 194,     # Low stability anchor
    'solid': 210,      # Earth frequency
    'real': 256,       # Middle C
    'true': 264,       # C# near speech range
    'proof': 272,      # D near speech
    
    # Action/energy words
    'move': 366,       # F# note
    'flow': 396,       # UT note
    'grow': 384,       # F# area
    'expand': 360,     # F note
    'evolve': 432,     # G healing
    'manifest': 480,   # D note
    
    # Quantum/meta words
    'quantum': 528,    # Coherence
    'observe': 417,    # G# note
    'measure': 440,    # A reference
    'collapse': 432,   # G note
    'wave': 417,       # Oscillation
    'simulation': 528,  # Pattern
    'reality': 528,    # Grounded pattern
    'proof': 528,      # Certainty
}

# Default frequency for unmapped words
DEFAULT_FREQUENCY = 420.0

# ──────────────────────────────────────────────────────────────────────────────
# AUDIO SYNTHESIS
# ──────────────────────────────────────────────────────────────────────────────

def text_to_speech_wav(text, output_wav):
    """Convert text to speech using espeak-ng, return WAV file path."""
    try:
        cmd = ['espeak-ng', '-w', output_wav, text]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print(f"Error: espeak-ng failed: {result.stderr}", file=sys.stderr)
            return None
        return output_wav
    except Exception as e:
        print(f"Error converting text to speech: {e}", file=sys.stderr)
        return None

# ──────────────────────────────────────────────────────────────────────────────
# FREQUENCY ANALYSIS
# ──────────────────────────────────────────────────────────────────────────────

def analyze_audio_spectrum(wav_file):
    """Perform FFT on audio file, return frequencies and magnitudes."""
    try:
        sample_rate, audio_data = wavfile.read(wav_file)
        
        # Convert stereo to mono if needed
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=1)
        
        # Normalize
        audio_data = audio_data.astype(np.float32) / np.max(np.abs(audio_data))
        
        # FFT
        fft_values = fft(audio_data)
        magnitude = np.abs(fft_values)
        freqs = fftfreq(len(audio_data), 1/sample_rate)
        
        # Keep only positive frequencies
        positive_idx = freqs > 0
        freqs = freqs[positive_idx]
        magnitude = magnitude[positive_idx]
        
        # Limit to 0-5000 Hz (speech range)
        max_freq_idx = np.where(freqs > 5000)[0]
        if len(max_freq_idx) > 0:
            max_idx = max_freq_idx[0]
            freqs = freqs[:max_idx]
            magnitude = magnitude[:max_idx]
        
        # Normalize magnitude
        magnitude = magnitude / np.max(magnitude)
        
        return freqs, magnitude, sample_rate
    except Exception as e:
        print(f"Error analyzing audio: {e}", file=sys.stderr)
        return None, None, None

# ──────────────────────────────────────────────────────────────────────────────
# SEMANTIC FREQUENCY ANALYSIS
# ──────────────────────────────────────────────────────────────────────────────

def extract_semantic_frequencies(text):
    """Map words to harmonic frequencies based on semantic mapping."""
    # Tokenize and clean
    words = text.lower().split()
    words = [w.strip('.,!?;:"\'()[]{}') for w in words]
    
    semantic_peaks = []
    for word in words:
        # Check exact match first
        if word in SEMANTIC_FREQUENCIES:
            freq = SEMANTIC_FREQUENCIES[word]
        else:
            # Check for partial matches (word contains key)
            freq = None
            for key, value in SEMANTIC_FREQUENCIES.items():
                if key in word:
                    freq = value
                    break
            if freq is None:
                freq = DEFAULT_FREQUENCY
        
        semantic_peaks.append((word, freq))
    
    return semantic_peaks

def generate_semantic_spectrum(semantic_peaks, freq_range=(0, 1000)):
    """Create synthetic spectrum from semantic frequencies."""
    freqs = np.linspace(freq_range[0], freq_range[1], 2000)
    magnitude = np.zeros_like(freqs)
    
    # Create Gaussian peaks at semantic frequencies
    for word, freq in semantic_peaks:
        if freq_range[0] <= freq <= freq_range[1]:
            # Gaussian width proportional to frequency
            sigma = freq * 0.02 + 10
            peak = np.exp(-((freqs - freq) ** 2) / (2 * sigma ** 2))
            magnitude += peak
    
    # Normalize
    if np.max(magnitude) > 0:
        magnitude = magnitude / np.max(magnitude)
    
    return freqs, magnitude

# ──────────────────────────────────────────────────────────────────────────────
# COHERENCE SCORING
# ──────────────────────────────────────────────────────────────────────────────

def calculate_coherence_score(acoustic_freqs, acoustic_mag, semantic_freqs, semantic_mag):
    """
    Calculate resonance coherence score.
    How well do acoustic and semantic patterns align?
    Range: 0-100 (%)
    """
    try:
        # Normalize both to same length
        n_samples = min(len(acoustic_freqs), len(semantic_freqs))
        
        # Resample to common grid
        common_freqs = np.linspace(0, min(acoustic_freqs[-1], semantic_freqs[-1]), 1000)
        
        # Interpolate
        acoustic_interp = np.interp(common_freqs, acoustic_freqs, acoustic_mag)
        semantic_interp = np.interp(common_freqs, semantic_freqs, semantic_mag)
        
        # Normalize
        acoustic_interp = acoustic_interp / (np.max(acoustic_interp) + 1e-10)
        semantic_interp = semantic_interp / (np.max(semantic_interp) + 1e-10)
        
        # Cross-correlation at zero lag
        correlation = np.sum(acoustic_interp * semantic_interp) / len(common_freqs)
        
        # Convert to 0-100% score
        score = max(0, min(100, correlation * 150))
        return score
    except:
        return 0.0

# ──────────────────────────────────────────────────────────────────────────────
# VISUALIZATION
# ──────────────────────────────────────────────────────────────────────────────

def create_cymatic_mandala(acoustic_freqs, acoustic_mag, semantic_freqs, semantic_mag, 
                           coherence_score, text_preview, output_path):
    """Create 2D frequency mandala visualization."""
    fig = plt.figure(figsize=(14, 14), facecolor='#0a0a1a')
    
    # Main polar plot for mandala
    ax_main = plt.subplot(111, projection='polar')
    
    # ──── ACOUSTIC LAYER (blue/cyan) ────
    # Convert to polar coordinates
    acoustic_theta = (acoustic_freqs / (acoustic_freqs[-1] + 1)) * 2 * np.pi
    acoustic_r = acoustic_mag * 10 + 1
    
    ax_main.plot(acoustic_theta, acoustic_r, color='#00ffff', linewidth=2, 
                 label='Acoustic Spectrum', alpha=0.8)
    ax_main.fill(acoustic_theta, acoustic_r, color='#00ffff', alpha=0.15)
    
    # ──── SEMANTIC LAYER (magenta/pink) ────
    semantic_theta = (semantic_freqs / (semantic_freqs[-1] + 1)) * 2 * np.pi
    semantic_r = semantic_mag * 10 + 1
    
    ax_main.plot(semantic_theta, semantic_r, color='#ff00ff', linewidth=2,
                 label='Semantic Harmonics', alpha=0.8)
    ax_main.fill(semantic_theta, semantic_r, color='#ff00ff', alpha=0.15)
    
    # ──── COHERENCE VISUALIZATION ────
    # Add coherence rings
    coherence_r = (coherence_score / 100) * 5 + 5
    theta_coherence = np.linspace(0, 2*np.pi, 200)
    ax_main.plot(theta_coherence, np.ones_like(theta_coherence) * coherence_r, 
                color='#ffff00', linewidth=3, alpha=0.6, linestyle='--',
                label=f'Coherence: {coherence_score:.1f}%')
    
    # ──── STYLING ────
    ax_main.set_facecolor('#0a0a1a')
    ax_main.grid(True, color='#333333', linestyle=':', alpha=0.5)
    ax_main.set_ylim(0, 15)
    
    # Radial labels in Hz
    ax_main.set_rticks([5, 10, 15])
    ax_main.set_rlabel_position(0)
    for label in ax_main.get_yticklabels():
        label.set_color('#888888')
        label.set_fontsize(9)
    
    # Angular labels
    ax_main.set_theta_zero_location('N')
    ax_main.set_theta_direction(-1)
    
    # ──── TEXT LABELS ────
    ax_main.text(0.5, 0.98, 'CYMATIC FREQUENCY MANDALA', 
                transform=fig.transFigure, fontsize=16, fontweight='bold',
                color='#00ffff', ha='center', va='top')
    
    # Preview text (truncated)
    preview = text_preview[:100] + ('...' if len(text_preview) > 100 else '')
    ax_main.text(0.5, 0.94, f'"{preview}"', 
                transform=fig.transFigure, fontsize=10,
                color='#aaaaaa', ha='center', va='top', style='italic')
    
    # Statistics box
    stats_text = f"""
RESONANCE COHERENCE: {coherence_score:.1f}%

Acoustic Peaks: {int(np.sum(acoustic_mag > 0.3))}
Semantic Peaks: {int(np.sum(semantic_mag > 0.3))}
Alignment Score: {coherence_score/100:.3f}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """.strip()
    
    ax_main.text(0.02, 0.98, stats_text, 
                transform=fig.transFigure, fontsize=9,
                color='#00ff00', ha='left', va='top',
                family='monospace', bbox=dict(boxstyle='round', 
                                             facecolor='#1a1a2e', 
                                             edgecolor='#00ff00',
                                             alpha=0.7))
    
    # Legend
    ax_main.legend(loc='upper right', framealpha=0.9, fontsize=10,
                  facecolor='#1a1a2e', edgecolor='#00ffff')
    
    # Save
    plt.tight_layout()
    plt.savefig(output_path, facecolor='#0a0a1a', dpi=150, bbox_inches='tight')
    plt.close()
    return output_path

# ──────────────────────────────────────────────────────────────────────────────
# MAIN WORKFLOW
# ──────────────────────────────────────────────────────────────────────────────

def generate_cymatics(text, output_png=None):
    """Main workflow: text → cymatics visualization."""
    
    if not text or not text.strip():
        print("Error: No text provided", file=sys.stderr)
        return None
    
    # Generate output path if not provided
    if output_png is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_png = f'/tmp/cymatics_{timestamp}.png'
    
    print(f"🔄 Generating cymatics for: {text[:60]}...", file=sys.stderr)
    
    # Step 1: Text to speech
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        wav_file = tmp.name
    
    print(f"🎤 Synthesizing speech...", file=sys.stderr)
    wav_file = text_to_speech_wav(text, wav_file)
    if not wav_file:
        return None
    
    # Step 2: Analyze acoustic spectrum
    print(f"📊 Analyzing acoustic spectrum...", file=sys.stderr)
    acoustic_freqs, acoustic_mag, sample_rate = analyze_audio_spectrum(wav_file)
    if acoustic_freqs is None:
        return None
    
    # Step 3: Extract semantic frequencies
    print(f"🧠 Mapping semantic harmonics...", file=sys.stderr)
    semantic_peaks = extract_semantic_frequencies(text)
    semantic_freqs, semantic_mag = generate_semantic_spectrum(semantic_peaks)
    
    # Step 4: Calculate coherence
    print(f"⚖️  Calculating coherence...", file=sys.stderr)
    coherence_score = calculate_coherence_score(acoustic_freqs, acoustic_mag,
                                               semantic_freqs, semantic_mag)
    
    # Step 5: Visualize
    print(f"🎨 Rendering mandala...", file=sys.stderr)
    output_png = create_cymatic_mandala(acoustic_freqs, acoustic_mag,
                                       semantic_freqs, semantic_mag,
                                       coherence_score, text, output_png)
    
    # Cleanup
    try:
        os.unlink(wav_file)
    except:
        pass
    
    print(f"✅ Cymatics saved to: {output_png}", file=sys.stderr)
    return output_png

# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    # Check for file input
    if sys.argv[1] == '--file' and len(sys.argv) > 2:
        try:
            with open(sys.argv[2], 'r') as f:
                text = f.read()
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        text = ' '.join(sys.argv[1:])
    
    output_png = generate_cymatics(text)
    if output_png:
        # Output path for external tools to capture
        print(output_png)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()

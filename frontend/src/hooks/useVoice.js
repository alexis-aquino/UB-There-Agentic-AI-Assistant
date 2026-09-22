import { useCallback, useEffect, useRef, useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/**
 * Plays synthesised speech and measures it for lip sync.
 *
 * The browser's speechSynthesis cannot be routed into the Web Audio API, so a mouth
 * driven by it can only be faked on a timer. Fetching real audio from the backend and
 * running it through an AnalyserNode gives an actual amplitude to open the jaw with.
 * speechSynthesis stays as a fallback for when the voice service is unavailable — the
 * jaw then falls back to an approximation, which is the best that path allows.
 */
export default function useVoice({ enabled = true } = {}) {
  const [speaking, setSpeaking] = useState(false);
  const [jawOpen, setJawOpen] = useState(0);
  const [usingFallback, setUsingFallback] = useState(false);
  const [error, setError] = useState(null);

  const contextRef = useRef(null);
  const sourceRef = useRef(null);
  const analyserRef = useRef(null);
  const frameRef = useRef(0);
  const fallbackTimerRef = useRef(0);

  const cleanupAudio = useCallback(() => {
    cancelAnimationFrame(frameRef.current);
    window.clearInterval(fallbackTimerRef.current);
    if (sourceRef.current) {
      try {
        sourceRef.current.onended = null;
        sourceRef.current.stop();
      } catch {
        /* already stopped */
      }
      sourceRef.current = null;
    }
    setJawOpen(0);
    setSpeaking(false);
  }, []);

  const stop = useCallback(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    cleanupAudio();
  }, [cleanupAudio]);

  useEffect(() => stop, [stop]);

  /** Last-resort path: browser voice, jaw approximated on a timer. */
  const speakWithBrowser = useCallback((text) => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1;
    utterance.onstart = () => {
      setSpeaking(true);
      setUsingFallback(true);
      fallbackTimerRef.current = window.setInterval(() => {
        setJawOpen(0.25 + Math.random() * 0.55);
      }, 120);
    };
    const finish = () => {
      window.clearInterval(fallbackTimerRef.current);
      setJawOpen(0);
      setSpeaking(false);
    };
    utterance.onend = finish;
    utterance.onerror = finish;
    window.speechSynthesis.speak(utterance);
  }, []);

  const speak = useCallback(
    async (text) => {
      if (!enabled || !text) return;
      stop();
      setError(null);

      try {
        const response = await fetch(`${API_URL}/api/speak`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text }),
        });

        if (!response.ok) {
          const detail = await response.json().catch(() => ({}));
          throw new Error(detail.detail ?? `Voice service returned ${response.status}`);
        }

        const buffer = await response.arrayBuffer();

        if (!contextRef.current) {
          const Ctx = window.AudioContext || window.webkitAudioContext;
          contextRef.current = new Ctx();
        }
        const context = contextRef.current;
        // Browsers suspend audio until a user gesture; a click already happened by now.
        if (context.state === 'suspended') await context.resume();

        const decoded = await context.decodeAudioData(buffer.slice(0));

        const source = context.createBufferSource();
        source.buffer = decoded;

        const analyser = context.createAnalyser();
        analyser.fftSize = 1024;
        analyser.smoothingTimeConstant = 0.55;

        source.connect(analyser);
        analyser.connect(context.destination);

        sourceRef.current = source;
        analyserRef.current = analyser;
        setUsingFallback(false);
        setSpeaking(true);

        const samples = new Uint8Array(analyser.fftSize);
        const measure = () => {
          frameRef.current = requestAnimationFrame(measure);
          analyser.getByteTimeDomainData(samples);

          // RMS around the 128 midpoint gives loudness; scaled so speech reaches ~1.
          let sum = 0;
          for (let i = 0; i < samples.length; i += 1) {
            const deviation = (samples[i] - 128) / 128;
            sum += deviation * deviation;
          }
          const rms = Math.sqrt(sum / samples.length);
          setJawOpen(Math.min(1, rms * 3.4));
        };
        measure();

        source.onended = () => cleanupAudio();
        source.start();
      } catch (err) {
        setError(err.message);
        speakWithBrowser(text);
      }
    },
    [enabled, stop, cleanupAudio, speakWithBrowser],
  );

  return { speak, stop, speaking, jawOpen, usingFallback, error };
}

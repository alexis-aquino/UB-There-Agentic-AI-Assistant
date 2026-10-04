import { useCallback, useEffect, useRef, useState } from 'react';
import { API_URL } from '../api.js';

// Anything shorter is merged into the next sentence, so speech doesn't come out choppy.
const MIN_SENTENCE = 24;
// The first piece of a reply may end at a comma once it's this long, so talking starts as
// soon as the first clause is written instead of waiting for a long first sentence.
const MIN_FIRST_CLAUSE = 24;

/**
 * Complete sentences in `text` from `from` onward; `final` also takes the unfinished tail.
 * `firstPiece` lets the very first piece end at a clause (comma, colon, semicolon).
 */
function takeSentences(text, from, final, firstPiece = false) {
  const sentences = [];
  let start = from;
  if (firstPiece) {
    const clause = /[,;:]\s+/g;
    clause.lastIndex = from + MIN_FIRST_CLAUSE;
    const sentenceEnd = text.slice(from).search(/[.!?]+["')\]”’]*\s+/);
    const match = clause.exec(text);
    if (match && (sentenceEnd < 0 || match.index < from + sentenceEnd)) {
      const end = match.index + match[0].length;
      sentences.push(text.slice(start, end).trim());
      start = end;
    }
  }
  // A sentence ends at . ! ? (plus closing quotes/brackets) followed by whitespace.
  const boundary = /[.!?]+["')\]”’]*\s+/g;
  boundary.lastIndex = from;
  let match;
  while ((match = boundary.exec(text))) {
    const end = match.index + match[0].length;
    const sentence = text.slice(start, end).trim();
    if (sentence.length >= MIN_SENTENCE) {
      sentences.push(sentence);
      start = end;
    }
  }
  if (final && text.slice(start).trim()) {
    sentences.push(text.slice(start).trim());
    start = text.length;
  }
  return { sentences, next: start };
}

// Markdown symbols would be read out loud ("asterisk asterisk").
const speakable = (text) => text.replace(/[*_#`]+/g, '').replace(/\s+/g, ' ').trim();

/**
 * Reads replies aloud with the backend's AI voice, one sentence at a time: the first
 * sentence plays as soon as it is synthesised while the next is prepared, so speech starts
 * in a fraction of a second instead of after the whole reply. Works on streamed replies too —
 * feed it the text as it grows. The browser's own voice is the fallback if the server can't.
 */
export default function useVoice({ enabled = true, voice = null } = {}) {
  const [speaking, setSpeaking] = useState(false);
  const [loading, setLoading] = useState(false);
  const [usingFallback, setUsingFallback] = useState(false);

  const contextRef = useRef(null);
  const sourceRef = useRef(null);
  const queueRef = useRef([]); // { text, voice, audio: Promise<AudioBuffer|null> }
  const playingRef = useRef(false);
  const finishedRef = useRef(true); // no more sentences coming
  const consumedRef = useRef(0); // characters of the streamed reply already queued
  const generationRef = useRef(0); // bumped by stop(); stale work checks it and bails
  const voiceRef = useRef(voice);
  voiceRef.current = voice;

  const audioContext = () => {
    if (!contextRef.current) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      contextRef.current = new Ctx();
    }
    return contextRef.current;
  };

  const fetchAudio = useCallback(async (text, voiceId) => {
    try {
      const response = await fetch(`${API_URL}/api/speak`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice: voiceId }),
      });
      if (!response.ok) return null;
      return await audioContext().decodeAudioData(await response.arrayBuffer());
    } catch {
      return null;
    }
  }, []);

  const playBuffer = (buffer, generation) =>
    new Promise((resolve) => {
      if (generation !== generationRef.current) return resolve();
      const source = audioContext().createBufferSource();
      source.buffer = buffer;
      source.connect(audioContext().destination);
      source.onended = () => {
        sourceRef.current = null;
        resolve();
      };
      sourceRef.current = source;
      source.start();
    });

  const playWithBrowser = (text, generation) =>
    new Promise((resolve) => {
      if (generation !== generationRef.current || !('speechSynthesis' in window)) return resolve();
      setUsingFallback(true);
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.onend = () => resolve();
      utterance.onerror = () => resolve();
      window.speechSynthesis.speak(utterance);
    });

  const pump = useCallback(async () => {
    if (playingRef.current) return;
    playingRef.current = true;
    const generation = generationRef.current;
    try {
      const context = audioContext();
      // Browsers suspend audio until a user gesture; a click already happened by now.
      if (context.state === 'suspended') await context.resume();

      while (generation === generationRef.current && queueRef.current.length) {
        const item = queueRef.current[0];
        if (!item.audio) item.audio = fetchAudio(item.text, item.voice);
        // Prepare the next sentence while this one plays.
        const upcoming = queueRef.current[1];
        if (upcoming && !upcoming.audio) upcoming.audio = fetchAudio(upcoming.text, upcoming.voice);

        const buffer = await item.audio;
        if (generation !== generationRef.current) return;
        setLoading(false);
        setSpeaking(true);
        if (buffer) {
          setUsingFallback(false);
          await playBuffer(buffer, generation);
        } else {
          await playWithBrowser(item.text, generation);
        }
        queueRef.current.shift();
      }
    } finally {
      if (generation === generationRef.current) {
        playingRef.current = false;
        if (queueRef.current.length) pump();
        else if (finishedRef.current) setSpeaking(false);
      }
    }
  }, [fetchAudio]);

  const enqueue = useCallback(
    (sentences, voiceId) => {
      for (const sentence of sentences) {
        const text = speakable(sentence);
        if (text) queueRef.current.push({ text, voice: voiceId, audio: null });
      }
      if (queueRef.current.length) {
        if (!playingRef.current) setLoading(true);
        // Synthesise the playing sentence and the next one right away, so there's no gap
        // between sentences waiting for audio.
        for (const item of queueRef.current.slice(0, 2)) {
          if (!item.audio) item.audio = fetchAudio(item.text, item.voice);
        }
        pump();
      }
    },
    [pump, fetchAudio],
  );

  const stop = useCallback(() => {
    generationRef.current += 1;
    queueRef.current = [];
    finishedRef.current = true;
    consumedRef.current = 0;
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel();
    if (sourceRef.current) {
      try {
        sourceRef.current.onended = null;
        sourceRef.current.stop();
      } catch {
        /* already stopped */
      }
      sourceRef.current = null;
    }
    playingRef.current = false;
    setLoading(false);
    setSpeaking(false);
  }, []);

  useEffect(() => stop, [stop]);

  /** Speak a whole reply (e.g. "Read aloud"). `options.voice` overrides; `force` ignores mute. */
  const speak = useCallback(
    (text, options = {}) => {
      if ((!enabled && !options.force) || !text) return;
      stop();
      finishedRef.current = true;
      enqueue(takeSentences(text, 0, true, true).sentences, options.voice ?? voiceRef.current);
    },
    [enabled, stop, enqueue],
  );

  /** Start speaking a reply that is still streaming in. */
  const beginStream = useCallback(() => {
    stop();
    if (enabled) finishedRef.current = false;
  }, [stop, enabled]);

  /** Give the reply so far; complete sentences are queued as soon as they appear. */
  const feedStream = useCallback(
    (textSoFar) => {
      if (finishedRef.current) return;
      const firstPiece = consumedRef.current === 0;
      const { sentences, next } = takeSentences(textSoFar, consumedRef.current, false, firstPiece);
      consumedRef.current = next;
      enqueue(sentences, voiceRef.current);
    },
    [enqueue],
  );

  /** The reply is complete: queue whatever is left. */
  const endStream = useCallback(
    (finalText) => {
      if (finishedRef.current) return;
      const { sentences } = takeSentences(finalText, consumedRef.current, true, consumedRef.current === 0);
      finishedRef.current = true;
      enqueue(sentences, voiceRef.current);
      if (!queueRef.current.length && !playingRef.current) setSpeaking(false);
    },
    [enqueue],
  );

  return { speak, stop, beginStream, feedStream, endStream, speaking, loading, usingFallback };
}

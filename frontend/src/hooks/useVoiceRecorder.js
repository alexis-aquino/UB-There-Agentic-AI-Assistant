import { useCallback, useRef, useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export const SAMPLE_SCRIPT =
  'Hello, I am the University of Batangas student assistant. I can answer questions '
  + 'about grading, attendance, enrolment and tuition. Please ask me anything you need '
  + 'to know about the student handbook, and I will look it up for you.';

/**
 * Records a reference clip for voice cloning. XTTS is zero-shot, so around thirty
 * seconds of clean speech is enough — there is no training run.
 */
export default function useVoiceRecorder() {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(0);
  const streamRef = useRef(null);

  const stop = useCallback(() => {
    window.clearInterval(timerRef.current);
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      recorderRef.current.stop();
    }
    setRecording(false);
  }, []);

  const start = useCallback(async () => {
    setError(null);
    setStatus(null);
    setSeconds(0);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;

      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };

      recorder.onstop = async () => {
        // Release the microphone, or the browser keeps showing the recording indicator.
        streamRef.current?.getTracks().forEach((track) => track.stop());

        const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
        const form = new FormData();
        form.append('file', blob, 'my_voice.webm');

        setStatus('Uploading…');
        try {
          const response = await fetch(`${API_URL}/api/voice/sample`, {
            method: 'POST',
            body: form,
          });
          const data = await response.json();
          if (!response.ok) throw new Error(data.detail ?? 'Upload failed');
          setStatus(`Saved ${(data.bytes / 1024).toFixed(0)} KB. ${data.note}`);
        } catch (err) {
          setError(err.message);
          setStatus(null);
        }
      };

      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
      timerRef.current = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch (err) {
      setError(
        err.name === 'NotAllowedError'
          ? 'Microphone access was denied. Allow it in the browser address bar and try again.'
          : err.message,
      );
    }
  }, []);

  return { start, stop, recording, seconds, status, error };
}

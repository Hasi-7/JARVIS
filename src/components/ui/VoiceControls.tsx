import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';
import type { VoiceStatusResponse } from '@/lib/api';
import { Icon } from '@/components/ui/Icon';
import { StatusDot } from '@/components/ui/StatusDot';

/**
 * Local voice I/O (D1).
 *
 * Speech-to-text runs on the backend via faster-whisper — audio is captured here,
 * posted once, and transcribed on this machine. It is never sent to a cloud
 * speech service. The transcript populates the composer for review; it is NEVER
 * auto-sent and never routed to a tool.
 *
 * Text-to-speech uses the browser's SpeechSynthesis API with local system voices.
 */

interface VoiceControlsProps {
  onTranscript: (text: string) => void;
  onStateChange?: (state: 'idle' | 'listening' | 'thinking') => void;
  speakText?: string | null;
  speakEnabled: boolean;
  onToggleSpeak: () => void;
  disabled?: boolean;
}

export function VoiceControls({
  onTranscript,
  onStateChange,
  speakText,
  speakEnabled,
  onToggleSpeak,
  disabled,
}: VoiceControlsProps) {
  const [status, setStatus]       = useState<VoiceStatusResponse | null>(null);
  const [recording, setRecording] = useState(false);
  const [busy, setBusy]           = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [elapsed, setElapsed]     = useState(0);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef   = useRef<BlobPart[]>([]);
  const timerRef    = useRef<number | null>(null);
  const spokenRef   = useRef<string | null>(null);

  useEffect(() => {
    api.voiceStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  // Speak assistant replies through local system voices.
  useEffect(() => {
    if (!speakEnabled || !speakText || speakText === spokenRef.current) return;
    if (typeof window === 'undefined' || !window.speechSynthesis) return;
    spokenRef.current = speakText;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(speakText.slice(0, 4000));
    utterance.rate = 1.02;
    window.speechSynthesis.speak(utterance);
  }, [speakText, speakEnabled]);

  useEffect(() => () => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    if (typeof window !== 'undefined' && window.speechSynthesis) window.speechSynthesis.cancel();
  }, []);

  const stopTimer = () => {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setElapsed(0);
  };

  const finish = useCallback(async (blob: Blob) => {
    setBusy(true);
    onStateChange?.('thinking');
    try {
      const result = await api.transcribeAudio(blob, 'clip.webm');
      if (result.text.trim()) {
        onTranscript(result.text.trim());
      } else {
        setError('No speech was detected in that clip.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Transcription failed.');
    } finally {
      setBusy(false);
      onStateChange?.('idle');
    }
  }, [onTranscript, onStateChange]);

  const start = async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('This browser does not expose microphone capture.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];

      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        chunksRef.current = [];
        if (blob.size > 0) void finish(blob);
      };

      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
      onStateChange?.('listening');

      const max = status?.maxAudioSeconds ?? 300;
      timerRef.current = window.setInterval(() => {
        setElapsed((n) => {
          if (n + 1 >= max) stop();
          return n + 1;
        });
      }, 1000);
    } catch {
      setError('Microphone access was denied.');
      onStateChange?.('idle');
    }
  };

  const stop = () => {
    stopTimer();
    setRecording(false);
    const recorder = recorderRef.current;
    recorderRef.current = null;
    if (recorder && recorder.state !== 'inactive') recorder.stop();
  };

  const available = status?.available === true;
  const label = recording ? `Stop (${elapsed}s)` : busy ? 'Transcribing…' : 'Hold to speak';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s2)', flexWrap: 'wrap' }}>
        <button
          className={`btn btn-sm ${recording ? '' : 'btn-ghost'}`}
          onClick={recording ? stop : start}
          disabled={disabled || busy || !available}
          title={status?.message ?? 'Checking local speech-to-text…'}
          style={recording ? { background: 'var(--red-bg)', borderColor: 'var(--red-line)' } : undefined}
        >
          <StatusDot tone={recording ? 'red' : busy ? 'amber' : available ? 'green' : 'grey'} />
          {label}
        </button>

        <button
          className="btn btn-sm btn-ghost"
          onClick={onToggleSpeak}
          title="Read assistant replies aloud using local system voices"
        >
          <Icon name={speakEnabled ? 'check' : 'x'} size={12} />
          Speak replies
        </button>

        {available && (
          <span className="mono" style={{ fontSize: 10, color: 'var(--txt-3)' }}>
            {status?.model} · on-device
          </span>
        )}
      </div>

      {!available && status && (
        <div style={{ fontSize: 10.5, color: 'var(--txt-2)' }}>{status.message}</div>
      )}

      {error && (
        <div style={{ fontSize: 10.5, color: 'var(--red)' }}>{error}</div>
      )}

      {available && (
        <div style={{ fontSize: 10, color: 'var(--txt-3)', lineHeight: 1.45 }}>
          Audio is transcribed on this machine and never uploaded. The transcript fills
          the composer for you to review — it is not sent automatically.
        </div>
      )}
    </div>
  );
}

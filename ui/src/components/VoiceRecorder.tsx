'use client';

/**
 * VoiceRecorder — record audio from the microphone and produce a File.
 *
 * Uses `MediaRecorder` + `getUserMedia({ audio: true })`.
 * Draws a live waveform on a canvas during recording using the Web Audio API.
 * The caller receives the recorded `File` via `onRecording`.
 */

import { useRef, useState, useCallback, useEffect } from 'react';
import { Mic, Square, Play, Pause, Trash2, AudioLines, AlertCircle, Loader2 } from 'lucide-react';

interface VoiceRecorderProps {
  /** Called when a recording is produced or cleared. */
  onRecording: (file: File | null) => void;
  /** Currently recorded file (controlled) */
  recordedFile: File | null;
}

type RecordingState = 'idle' | 'requesting' | 'recording' | 'done';

/** Format seconds as mm:ss */
const fmt = (s: number) =>
  `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

export default function VoiceRecorder({ onRecording, recordedFile }: VoiceRecorderProps) {
  const [state, setState]     = useState<RecordingState>('idle');
  const [elapsed, setElapsed] = useState(0);
  const [playback, setPlayback] = useState<'idle' | 'playing' | 'paused'>('idle');
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError]     = useState<string | null>(null);
  const [mimeType, setMimeType] = useState('audio/webm');

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef        = useRef<Blob[]>([]);
  const streamRef        = useRef<MediaStream | null>(null);
  const timerRef         = useRef<ReturnType<typeof setInterval> | null>(null);
  const canvasRef        = useRef<HTMLCanvasElement>(null);
  const analyserRef      = useRef<AnalyserNode | null>(null);
  const audioCtxRef      = useRef<AudioContext | null>(null);
  const rafRef           = useRef<number>(0);
  const audioElemRef     = useRef<HTMLAudioElement | null>(null);

  // --------------------------------------------------------------------------
  // Waveform visualiser
  // --------------------------------------------------------------------------

  const drawWaveform = useCallback(() => {
    const canvas  = canvasRef.current;
    const analyser = analyserRef.current;
    if (!canvas || !analyser) return;

    const ctx   = canvas.getContext('2d');
    if (!ctx) return;

    const buf   = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteTimeDomainData(buf);

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Background
    ctx.fillStyle = 'rgba(0,0,0,0)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw waveform
    const gradient = ctx.createLinearGradient(0, 0, canvas.width, 0);
    gradient.addColorStop(0,   '#6366f1');
    gradient.addColorStop(0.5, '#a855f7');
    gradient.addColorStop(1,   '#ec4899');

    ctx.beginPath();
    ctx.strokeStyle = gradient;
    ctx.lineWidth   = 2.5;
    ctx.lineJoin    = 'round';

    const sliceW = canvas.width / buf.length;
    let x = 0;
    for (let i = 0; i < buf.length; i++) {
      const v = buf[i] / 128;
      const y = (v * canvas.height) / 2;
      if (i === 0) ctx.moveTo(x, y);
      else         ctx.lineTo(x, y);
      x += sliceW;
    }
    ctx.stroke();

    rafRef.current = requestAnimationFrame(drawWaveform);
  }, []);

  const stopVisualiser = useCallback(() => {
    cancelAnimationFrame(rafRef.current);
    audioCtxRef.current?.close();
    audioCtxRef.current = null;
    analyserRef.current = null;
  }, []);

  // --------------------------------------------------------------------------
  // Start recording
  // --------------------------------------------------------------------------

  const startRecording = async () => {
    setError(null);
    setState('requesting');

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      streamRef.current = stream;

      // Pick the best supported MIME type
      const preferred = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
      const chosen = preferred.find(m => MediaRecorder.isTypeSupported(m)) ?? '';
      setMimeType(chosen || 'audio/webm');

      const mr = new MediaRecorder(stream, chosen ? { mimeType: chosen } : undefined);
      mediaRecorderRef.current = mr;
      chunksRef.current = [];

      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data); };

      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: chosen || 'audio/webm' });
        const ext  = (chosen || 'audio/webm').includes('ogg') ? 'ogg' : chosen.includes('mp4') ? 'mp4' : 'webm';
        const ts   = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
        const file = new File([blob], `voice-${ts}.${ext}`, { type: chosen || 'audio/webm' });
        const url  = URL.createObjectURL(blob);
        setAudioUrl(url);
        onRecording(file);
        setState('done');

        // Stop stream tracks
        streamRef.current?.getTracks().forEach(t => t.stop());
        stopVisualiser();
      };

      mr.start(100); // collect chunks every 100 ms

      // Set up Web Audio analyser for waveform
      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      audioCtxRef.current = audioCtx;
      const source  = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      analyserRef.current = analyser;
      drawWaveform();

      // Elapsed time counter
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);

      setState('recording');
    } catch (err: any) {
      const msg =
        err.name === 'NotAllowedError'  ? 'Microphone permission denied. Please allow mic access in your browser.' :
        err.name === 'NotFoundError'    ? 'No microphone found on this device.' :
        `Microphone error: ${err.message}`;
      setError(msg);
      setState('idle');
    }
  };

  // --------------------------------------------------------------------------
  // Stop recording
  // --------------------------------------------------------------------------

  const stopRecording = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    mediaRecorderRef.current?.stop();
  };

  // --------------------------------------------------------------------------
  // Discard
  // --------------------------------------------------------------------------

  const discard = () => {
    if (audioUrl) { URL.revokeObjectURL(audioUrl); setAudioUrl(null); }
    if (audioElemRef.current) { audioElemRef.current.pause(); audioElemRef.current.src = ''; }
    setPlayback('idle');
    setElapsed(0);
    setState('idle');
    onRecording(null);
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach(t => t.stop());
      stopVisualiser();
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --------------------------------------------------------------------------
  // Playback
  // --------------------------------------------------------------------------

  const togglePlayback = () => {
    const audio = audioElemRef.current;
    if (!audio || !audioUrl) return;
    if (!audio.src) audio.src = audioUrl;

    if (playback === 'playing') {
      audio.pause();
      setPlayback('paused');
    } else {
      audio.play();
      setPlayback('playing');
    }
  };

  // --------------------------------------------------------------------------
  // Draw idle waveform placeholder
  // --------------------------------------------------------------------------

  useEffect(() => {
    if (state !== 'idle' && state !== 'done') return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.beginPath();
    ctx.strokeStyle = 'rgba(255,255,255,0.1)';
    ctx.lineWidth = 2;
    const mid = canvas.height / 2;
    ctx.moveTo(0, mid);
    for (let x = 0; x < canvas.width; x += 8) {
      ctx.lineTo(x, mid + (Math.random() - 0.5) * (state === 'done' ? 24 : 2));
    }
    ctx.stroke();
  }, [state]);

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  return (
    <div className="flex flex-col gap-5">
      {/* Waveform display */}
      <div className={`
        relative rounded-2xl overflow-hidden border transition-all duration-500
        ${state === 'recording'
          ? 'bg-gradient-to-br from-red-950/60 to-purple-950/60 border-red-500/30 shadow-lg shadow-red-500/10'
          : state === 'done'
            ? 'bg-gradient-to-br from-emerald-950/40 to-purple-950/40 border-emerald-500/20'
            : 'bg-black/20 border-white/10'
        }
      `}>
        {/* Canvas */}
        <canvas
          ref={canvasRef}
          width={640}
          height={120}
          className="w-full"
        />

        {/* Elapsed time / status overlay */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          {state === 'idle' && !error && (
            <div className="flex flex-col items-center gap-2">
              <div className="w-14 h-14 rounded-full bg-white/5 border border-white/10 flex items-center justify-center">
                <Mic className="w-7 h-7 text-white/30" />
              </div>
              <span className="text-sm text-white/30">Press record to start</span>
            </div>
          )}

          {state === 'requesting' && (
            <div className="flex flex-col items-center gap-2">
              <Loader2 className="w-8 h-8 text-primary-400 animate-spin" />
              <span className="text-sm text-white/50">Requesting microphone…</span>
            </div>
          )}

          {state === 'recording' && (
            <div className="flex flex-col items-center gap-1">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
                <span className="text-2xl font-mono font-bold text-white tracking-widest">
                  {fmt(elapsed)}
                </span>
              </div>
              <span className="text-xs text-red-400/70">Recording…</span>
            </div>
          )}

          {state === 'done' && recordedFile && (
            <div className="flex flex-col items-center gap-1">
              <div className="flex items-center gap-2">
                <AudioLines className="w-5 h-5 text-emerald-400" />
                <span className="text-lg font-mono font-semibold text-white">{fmt(elapsed)}</span>
              </div>
              <span className="text-xs text-emerald-400/70">
                {(recordedFile.size / 1024).toFixed(0)} KB · {mimeType.split('/')[1]?.split(';')[0] ?? 'audio'}
              </span>
            </div>
          )}
        </div>

        {/* Error overlay */}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/70 p-6">
            <div className="text-center">
              <AlertCircle className="w-8 h-8 text-red-400 mx-auto mb-2" />
              <p className="text-sm text-red-300">{error}</p>
              <button
                onClick={() => { setError(null); setState('idle'); }}
                className="mt-3 px-3 py-1.5 rounded-lg bg-white/10 text-white/60 text-xs hover:bg-white/20 transition-all"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Hidden audio element for playback */}
      <audio
        ref={audioElemRef}
        src={audioUrl ?? undefined}
        onEnded={() => setPlayback('idle')}
        className="hidden"
      />

      {/* Controls */}
      {state === 'idle' && (
        <button
          onClick={startRecording}
          disabled={!!error}
          className="
            w-full flex items-center justify-center gap-3 py-4 rounded-2xl font-semibold text-base
            bg-gradient-to-r from-red-500 via-pink-500 to-accent-500
            text-white shadow-lg shadow-red-500/30
            hover:shadow-xl hover:shadow-red-500/40 hover:scale-[1.01]
            active:scale-[0.99] transition-all duration-200
            disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100
          "
        >
          <Mic className="w-6 h-6" />
          Start Recording
        </button>
      )}

      {state === 'recording' && (
        <button
          onClick={stopRecording}
          className="
            w-full flex items-center justify-center gap-3 py-4 rounded-2xl font-semibold text-base
            bg-white/5 border border-red-500/40
            text-red-400 hover:bg-red-500/10 hover:border-red-500/60
            active:scale-[0.99] transition-all duration-200 animate-pulse
          "
        >
          <Square className="w-5 h-5 fill-red-400" />
          Stop Recording
        </button>
      )}

      {state === 'requesting' && (
        <div className="w-full flex items-center justify-center gap-3 py-4 rounded-2xl bg-white/5 border border-white/10 text-white/40">
          <Loader2 className="w-5 h-5 animate-spin" />
          Waiting for permission…
        </div>
      )}

      {state === 'done' && (
        <div className="flex gap-3">
          {/* Playback */}
          <button
            onClick={togglePlayback}
            className={`
              flex-1 flex items-center justify-center gap-2 py-3 rounded-2xl font-medium text-sm transition-all
              ${playback === 'playing'
                ? 'bg-accent-500/20 border border-accent-500/40 text-accent-400'
                : 'bg-white/5 border border-white/10 text-white/70 hover:bg-white/10 hover:text-white'
              }
            `}
          >
            {playback === 'playing'
              ? <><Pause className="w-4 h-4" /> Pause</>
              : <><Play  className="w-4 h-4" /> Play</>
            }
          </button>

          {/* Discard */}
          <button
            onClick={discard}
            className="flex items-center justify-center gap-2 px-5 py-3 rounded-2xl font-medium text-sm bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition-all"
          >
            <Trash2 className="w-4 h-4" />
            Discard
          </button>
        </div>
      )}

      {state === 'done' && (
        <p className="text-center text-xs text-white/30">
          Recording ready — fill in a name above and press Upload
        </p>
      )}
    </div>
  );
}

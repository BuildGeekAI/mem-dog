'use client';

/**
 * VideoRecorder — record video + audio from the device camera and produce a File.
 *
 * Uses `MediaRecorder` + `getUserMedia({ video: true, audio: true })`.
 * Shows a live camera preview while recording and a full playback player when done.
 * The caller receives the recorded `File` via `onRecording`.
 */

import { useRef, useState, useCallback, useEffect } from 'react';
import { Square, Trash2, Film, AlertCircle, Loader2, SwitchCamera, Video } from 'lucide-react';

interface VideoRecorderProps {
  /** Called when a recording is produced or cleared. */
  onRecording: (file: File | null) => void;
  /** Currently recorded file (controlled) */
  recordedFile: File | null;
}

type RecordingState = 'idle' | 'requesting' | 'recording' | 'done';

/** Format seconds as mm:ss */
const fmt = (s: number) =>
  `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

export default function VideoRecorder({ onRecording, recordedFile }: VideoRecorderProps) {
  const [state, setState]       = useState<RecordingState>('idle');
  const [elapsed, setElapsed]   = useState(0);
  const [error, setError]       = useState<string | null>(null);
  const [mimeType, setMimeType] = useState('video/webm');
  const [facingMode, setFacingMode] = useState<'user' | 'environment'>('environment');
  const [videoUrl, setVideoUrl] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef        = useRef<Blob[]>([]);
  const streamRef        = useRef<MediaStream | null>(null);
  const timerRef         = useRef<ReturnType<typeof setInterval> | null>(null);
  const liveVideoRef     = useRef<HTMLVideoElement>(null);

  // --------------------------------------------------------------------------
  // Stream helpers
  // --------------------------------------------------------------------------

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
    if (liveVideoRef.current) {
      liveVideoRef.current.srcObject = null;
    }
  }, []);

  // --------------------------------------------------------------------------
  // Start recording
  // --------------------------------------------------------------------------

  const startRecording = async () => {
    setError(null);
    setState('requesting');

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode,
          width:  { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: true,
      });
      streamRef.current = stream;

      // Show live feed
      if (liveVideoRef.current) {
        liveVideoRef.current.srcObject = stream;
        await liveVideoRef.current.play();
      }

      // Pick best supported MIME type
      const preferred = [
        'video/webm;codecs=vp9,opus',
        'video/webm;codecs=vp8,opus',
        'video/webm',
        'video/mp4',
      ];
      const chosen = preferred.find(m => MediaRecorder.isTypeSupported(m)) ?? '';
      const finalMime = chosen || 'video/webm';
      setMimeType(finalMime);

      const mr = new MediaRecorder(stream, chosen ? { mimeType: chosen } : undefined);
      mediaRecorderRef.current = mr;
      chunksRef.current = [];

      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data); };

      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: finalMime });
        const ext  = finalMime.includes('mp4') ? 'mp4' : 'webm';
        const ts   = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
        const file = new File([blob], `video-${ts}.${ext}`, { type: finalMime });
        const url  = URL.createObjectURL(blob);
        setVideoUrl(url);
        onRecording(file);
        setState('done');
        stopStream();
      };

      mr.start(100); // collect chunks every 100 ms

      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000);
      setState('recording');
    } catch (err: any) {
      const msg =
        err.name === 'NotAllowedError'  ? 'Camera/microphone permission denied. Please allow access in your browser.' :
        err.name === 'NotFoundError'    ? 'No camera found on this device.' :
        err.name === 'NotReadableError' ? 'Camera is in use by another application.' :
        `Camera error: ${err.message}`;
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
  // Discard / re-record
  // --------------------------------------------------------------------------

  const discard = () => {
    if (videoUrl) { URL.revokeObjectURL(videoUrl); setVideoUrl(null); }
    setElapsed(0);
    setState('idle');
    onRecording(null);
  };

  // --------------------------------------------------------------------------
  // Cleanup on unmount
  // --------------------------------------------------------------------------

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      stopStream();
      // eslint-disable-next-line react-hooks/exhaustive-deps
      if (videoUrl) URL.revokeObjectURL(videoUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  const fileLabel = recordedFile
    ? `${(recordedFile.size / 1024 / 1024).toFixed(1)} MB · ${mimeType.split('/')[1]?.split(';')[0] ?? 'video'}`
    : 'Ready';

  return (
    <div className="flex flex-col gap-5">

      {/* ── Viewfinder / playback ──────────────────────────────────────── */}
      <div className={`
        relative rounded-2xl overflow-hidden bg-black aspect-video w-full max-h-[420px]
        shadow-2xl border transition-all duration-500
        ${state === 'recording'
          ? 'border-red-500/40 shadow-lg shadow-red-500/10'
          : state === 'done'
            ? 'border-emerald-500/20'
            : 'border-white/10'
        }
      `}>

        {/* Live camera feed — hidden once recording is done */}
        <video
          ref={liveVideoRef}
          playsInline
          muted
          autoPlay
          className={`
            w-full h-full object-cover transition-opacity duration-300
            ${state === 'done' ? 'opacity-0 pointer-events-none absolute inset-0' : 'opacity-100'}
          `}
        />

        {/* Recorded video playback */}
        {state === 'done' && videoUrl && (
          <video
            src={videoUrl}
            controls
            className="absolute inset-0 w-full h-full object-contain bg-black"
          />
        )}

        {/* Idle placeholder */}
        {state === 'idle' && !error && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/60">
            <div className="flex flex-col items-center gap-2">
              <div className="w-14 h-14 rounded-full bg-white/5 border border-white/10 flex items-center justify-center">
                <Film className="w-7 h-7 text-white/30" />
              </div>
              <span className="text-sm text-white/30">Press record to start</span>
            </div>
          </div>
        )}

        {/* Permission request overlay */}
        {state === 'requesting' && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/70">
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="w-8 h-8 text-primary-400 animate-spin" />
              <span className="text-sm text-white/50">Requesting camera access…</span>
            </div>
          </div>
        )}

        {/* Live recording indicator */}
        {state === 'recording' && (
          <div className="absolute top-3 left-3 flex items-center gap-2 px-3 py-1.5 rounded-full bg-black/50 border border-red-500/40 backdrop-blur-sm">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
            <span className="text-sm font-mono font-bold text-white tracking-widest">
              {fmt(elapsed)}
            </span>
          </div>
        )}

        {/* Camera flip — only in idle so we don't disrupt an active recording */}
        {state === 'idle' && !error && (
          <button
            onClick={() => setFacingMode(f => f === 'user' ? 'environment' : 'user')}
            title="Switch camera"
            className="absolute top-3 right-3 w-9 h-9 rounded-full bg-black/50 border border-white/20 flex items-center justify-center text-white/80 hover:bg-black/70 transition-all backdrop-blur-sm"
          >
            <SwitchCamera className="w-4 h-4" />
          </button>
        )}

        {/* Done badge */}
        {state === 'done' && recordedFile && (
          <div className="absolute top-3 left-3 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-500/20 border border-emerald-500/40 backdrop-blur-sm">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="text-xs font-semibold text-emerald-300">Video ready</span>
          </div>
        )}

        {/* Error overlay */}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/80 p-4">
            <div className="text-center">
              <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />
              <p className="text-sm text-red-300">{error}</p>
              <button
                onClick={() => { setError(null); setState('idle'); }}
                className="mt-4 px-4 py-2 rounded-lg bg-white/10 text-white/70 text-sm hover:bg-white/20 transition-all"
              >
                Try again
              </button>
            </div>
          </div>
        )}

        {/* Corner guides — idle only */}
        {state === 'idle' && !error && (
          <>
            <div className="absolute top-3  left-3  w-8 h-8 border-t-2 border-l-2 border-white/30 rounded-tl-md" />
            <div className="absolute top-3  right-14 w-8 h-8 border-t-2 border-r-2 border-white/30 rounded-tr-md" />
            <div className="absolute bottom-3 left-3  w-8 h-8 border-b-2 border-l-2 border-white/30 rounded-bl-md" />
            <div className="absolute bottom-3 right-3  w-8 h-8 border-b-2 border-r-2 border-white/30 rounded-br-md" />
          </>
        )}
      </div>

      {/* ── Controls ───────────────────────────────────────────────────── */}

      {state === 'idle' && (
        <button
          onClick={startRecording}
          disabled={!!error}
          className="
            w-full flex items-center justify-center gap-3 py-4 rounded-2xl
            font-semibold text-base
            bg-gradient-to-r from-red-500 via-rose-500 to-orange-500
            text-white shadow-lg shadow-red-500/30
            hover:shadow-xl hover:shadow-red-500/40 hover:scale-[1.01]
            active:scale-[0.99] transition-all duration-200
            disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100
          "
        >
          <Video className="w-6 h-6" />
          Start Recording
        </button>
      )}

      {state === 'requesting' && (
        <div className="w-full flex items-center justify-center gap-3 py-4 rounded-2xl bg-white/5 border border-white/10 text-white/40">
          <Loader2 className="w-5 h-5 animate-spin" />
          Waiting for permission…
        </div>
      )}

      {state === 'recording' && (
        <button
          onClick={stopRecording}
          className="
            w-full flex items-center justify-center gap-3 py-4 rounded-2xl
            font-semibold text-base
            bg-white/5 border border-red-500/40
            text-red-400 hover:bg-red-500/10 hover:border-red-500/60
            active:scale-[0.99] transition-all duration-200 animate-pulse
          "
        >
          <Square className="w-5 h-5 fill-red-400" />
          Stop Recording
        </button>
      )}

      {state === 'done' && (
        <div className="flex gap-3">
          <button
            onClick={discard}
            className="
              flex items-center justify-center gap-2 px-5 py-3 rounded-2xl
              font-medium text-sm
              bg-red-500/10 border border-red-500/20 text-red-400
              hover:bg-red-500/20 transition-all
            "
          >
            <Trash2 className="w-4 h-4" />
            Re-record
          </button>
          <div className="flex-1 flex items-center justify-center gap-2 py-3 rounded-2xl font-medium text-sm bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
            <Film className="w-4 h-4" />
            {fileLabel}
          </div>
        </div>
      )}

      {state === 'done' && (
        <p className="text-center text-xs text-white/30">
          Video ready — fill in a name above and press Upload
        </p>
      )}
    </div>
  );
}

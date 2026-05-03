'use client';

/**
 * CameraCapture — live camera preview with snapshot and retake.
 *
 * Opens the device camera via `getUserMedia`, streams it to a <video>,
 * and on capture draws the current frame to a hidden <canvas> to produce
 * a `File` (image/jpeg).  The caller receives the `File` via `onCapture`.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { Camera, RefreshCw, SwitchCamera, ZoomIn, ZoomOut, AlertCircle, Loader2, X } from 'lucide-react';

interface CameraCaptureProps {
  /** Called when a photo is captured. Pass `null` to clear the capture. */
  onCapture: (file: File | null) => void;
  /** Currently captured file (controlled) */
  capturedFile: File | null;
}

type FacingMode = 'user' | 'environment';

export default function CameraCapture({ onCapture, capturedFile }: CameraCaptureProps) {
  const videoRef  = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animRef   = useRef<number>(0);

  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [facingMode, setFacingMode] = useState<FacingMode>('environment');
  const [error, setError]   = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [flash, setFlash]   = useState(false);
  const [zoom, setZoom]     = useState(1);

  // --------------------------------------------------------------------------
  // Start / stop camera stream
  // --------------------------------------------------------------------------

  const stopStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    cancelAnimationFrame(animRef.current);
  }, []);

  const startStream = useCallback(async (facing: FacingMode) => {
    stopStream();
    setError(null);
    setLoading(true);

    try {
      const constraints: MediaStreamConstraints = {
        video: {
          facingMode: facing,
          width:  { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch (err: any) {
      const msg =
        err.name === 'NotAllowedError'  ? 'Camera permission denied. Please allow camera access in your browser.' :
        err.name === 'NotFoundError'    ? 'No camera found on this device.' :
        err.name === 'NotReadableError' ? 'Camera is in use by another application.' :
        `Camera error: ${err.message}`;
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [stopStream]);

  // Start stream when component mounts (or facing mode changes)
  useEffect(() => {
    if (!capturedFile) {
      startStream(facingMode);
    }
    return () => stopStream();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facingMode]);

  // Stop stream when a captured file is shown
  useEffect(() => {
    if (capturedFile) {
      stopStream();
    } else if (!capturedFile && !loading) {
      startStream(facingMode);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [capturedFile]);

  // --------------------------------------------------------------------------
  // Capture
  // --------------------------------------------------------------------------

  const capture = () => {
    const video  = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width  = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Apply zoom crop
    if (zoom > 1) {
      const sw = video.videoWidth  / zoom;
      const sh = video.videoHeight / zoom;
      const sx = (video.videoWidth  - sw) / 2;
      const sy = (video.videoHeight - sh) / 2;
      ctx.drawImage(video, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
    } else {
      ctx.drawImage(video, 0, 0);
    }

    // Flash effect
    setFlash(true);
    setTimeout(() => setFlash(false), 200);

    canvas.toBlob((blob) => {
      if (!blob) return;
      const ts   = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      const file = new File([blob], `photo-${ts}.jpg`, { type: 'image/jpeg' });
      const url  = URL.createObjectURL(blob);
      setPreviewUrl(url);
      onCapture(file);
    }, 'image/jpeg', 0.92);
  };

  const retake = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
    onCapture(null);
    startStream(facingMode);
  };

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  const hasDualCamera = typeof navigator !== 'undefined' &&
    'mediaDevices' in navigator;

  return (
    <div className="flex flex-col gap-4">
      {/* Viewfinder / preview area */}
      <div className="relative rounded-2xl overflow-hidden bg-black aspect-video w-full max-h-[420px] shadow-2xl border border-white/10">

        {/* Live camera feed (hidden when showing captured photo) */}
        <video
          ref={videoRef}
          playsInline
          muted
          autoPlay
          className={`w-full h-full object-cover transition-opacity duration-300 ${capturedFile ? 'opacity-0' : 'opacity-100'}`}
          style={{ transform: facingMode === 'user' ? 'scaleX(-1)' : 'none' }}
        />

        {/* Captured image preview */}
        {previewUrl && (
          <img
            src={previewUrl}
            alt="Captured photo"
            className="absolute inset-0 w-full h-full object-cover"
          />
        )}

        {/* Loading overlay */}
        {loading && !capturedFile && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/60">
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="w-8 h-8 text-primary-400 animate-spin" />
              <span className="text-sm text-white/60">Starting camera…</span>
            </div>
          </div>
        )}

        {/* Error overlay */}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/80 p-4">
            <div className="text-center">
              <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />
              <p className="text-sm text-red-300">{error}</p>
              <button
                onClick={() => startStream(facingMode)}
                className="mt-4 px-4 py-2 rounded-lg bg-white/10 text-white/70 text-sm hover:bg-white/20 transition-all"
              >
                Try again
              </button>
            </div>
          </div>
        )}

        {/* Shutter flash */}
        {flash && (
          <div className="absolute inset-0 bg-white animate-[flash_0.15s_ease-out]" />
        )}

        {/* Corner guides (hidden when captured) */}
        {!capturedFile && !loading && !error && (
          <>
            <div className="absolute top-3 left-3 w-8 h-8 border-t-2 border-l-2 border-white/30 rounded-tl-md" />
            <div className="absolute top-3 right-3 w-8 h-8 border-t-2 border-r-2 border-white/30 rounded-tr-md" />
            <div className="absolute bottom-3 left-3 w-8 h-8 border-b-2 border-l-2 border-white/30 rounded-bl-md" />
            <div className="absolute bottom-3 right-3 w-8 h-8 border-b-2 border-r-2 border-white/30 rounded-br-md" />
          </>
        )}

        {/* Captured badge */}
        {capturedFile && (
          <div className="absolute top-3 left-3 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-500/20 border border-emerald-500/40 backdrop-blur-sm">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="text-xs font-semibold text-emerald-300">Photo captured</span>
          </div>
        )}

        {/* Camera controls overlay (top-right) */}
        {!capturedFile && !error && (
          <div className="absolute top-3 right-3 flex flex-col gap-2">
            {hasDualCamera && (
              <button
                onClick={() => setFacingMode(f => f === 'user' ? 'environment' : 'user')}
                title="Switch camera"
                className="w-9 h-9 rounded-full bg-black/50 border border-white/20 flex items-center justify-center text-white/80 hover:bg-black/70 transition-all backdrop-blur-sm"
              >
                <SwitchCamera className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={() => setZoom(z => Math.min(3, +(z + 0.5).toFixed(1)))}
              title="Zoom in"
              disabled={zoom >= 3}
              className="w-9 h-9 rounded-full bg-black/50 border border-white/20 flex items-center justify-center text-white/80 hover:bg-black/70 transition-all backdrop-blur-sm disabled:opacity-30"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
            <button
              onClick={() => setZoom(z => Math.max(1, +(z - 0.5).toFixed(1)))}
              title="Zoom out"
              disabled={zoom <= 1}
              className="w-9 h-9 rounded-full bg-black/50 border border-white/20 flex items-center justify-center text-white/80 hover:bg-black/70 transition-all backdrop-blur-sm disabled:opacity-30"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Zoom level badge */}
        {!capturedFile && zoom > 1 && (
          <div className="absolute bottom-3 left-3 px-2 py-0.5 rounded-full bg-black/50 text-xs text-white/70 backdrop-blur-sm">
            {zoom.toFixed(1)}×
          </div>
        )}
      </div>

      {/* Hidden canvas for capture */}
      <canvas ref={canvasRef} className="hidden" />

      {/* Action buttons */}
      {!capturedFile ? (
        <button
          onClick={capture}
          disabled={loading || !!error}
          className="
            relative w-full flex items-center justify-center gap-3 py-4 rounded-2xl font-semibold text-base
            bg-gradient-to-r from-primary-500 via-accent-500 to-pink-500
            text-white shadow-lg shadow-primary-500/30
            hover:shadow-xl hover:shadow-primary-500/40 hover:scale-[1.01]
            active:scale-[0.99] transition-all duration-200
            disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100
          "
        >
          <Camera className="w-6 h-6" />
          Take Photo
        </button>
      ) : (
        <div className="flex gap-3">
          <button
            onClick={retake}
            className="flex-1 flex items-center justify-center gap-2 py-3 rounded-2xl font-medium text-sm bg-white/5 border border-white/10 text-white/70 hover:bg-white/10 hover:text-white transition-all"
          >
            <RefreshCw className="w-4 h-4" />
            Retake
          </button>
          <div className="flex-1 flex items-center justify-center gap-2 py-3 rounded-2xl font-medium text-sm bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
            <Camera className="w-4 h-4" />
            {capturedFile.name}
          </div>
        </div>
      )}

      {/* File info */}
      {capturedFile && (
        <p className="text-center text-xs text-white/30">
          {(capturedFile.size / 1024).toFixed(0)} KB · JPEG · Ready to upload
        </p>
      )}
    </div>
  );
}

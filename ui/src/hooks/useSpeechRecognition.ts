'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * React hook that wraps the browser Web Speech API for dictation.
 *
 * Returns live transcript state and start/stop controls.  When the
 * browser does not support the API (anything other than Chrome/Edge),
 * ``isSupported`` is ``false`` and the controls are no-ops.
 *
 * Each time the recogniser produces a final result its transcript is
 * passed to the ``onResult`` callback so the caller can append it to
 * existing text (rather than replacing it).
 */
export interface UseSpeechRecognitionOptions {
  /** BCP-47 language tag (default ``"en-US"``). */
  lang?: string;
  /** Called with the final transcript every time a phrase is recognised. */
  onResult?: (transcript: string) => void;
}

export interface UseSpeechRecognitionReturn {
  /** Whether the browser supports the Web Speech API. */
  isSupported: boolean;
  /** Whether the recogniser is actively listening. */
  isListening: boolean;
  /** Interim (in-progress) transcript shown while the user is still speaking. */
  interimTranscript: string;
  /** Most recent error message, or ``null``. */
  error: string | null;
  /** Begin listening. No-op if already listening or unsupported. */
  startListening: () => void;
  /** Stop listening. No-op if not listening. */
  stopListening: () => void;
}

function getBrowserSpeechRecognition(): SpeechRecognitionConstructor | null {
  if (typeof window === 'undefined') return null;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

export function useSpeechRecognition(
  options: UseSpeechRecognitionOptions = {},
): UseSpeechRecognitionReturn {
  const { lang = 'en-US', onResult } = options;

  const [isSupported] = useState(() => getBrowserSpeechRecognition() !== null);
  const [isListening, setIsListening] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const onResultRef = useRef(onResult);
  onResultRef.current = onResult;

  // Track whether the user explicitly asked to stop so the onend
  // handler knows not to auto-restart.
  const stoppingRef = useRef(false);

  const startListening = useCallback(() => {
    const SpeechRecognitionCtor = getBrowserSpeechRecognition();
    if (!SpeechRecognitionCtor) return;

    // Tear down any prior instance
    if (recognitionRef.current) {
      try { recognitionRef.current.abort(); } catch { /* ignore */ }
    }

    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = lang;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setIsListening(true);
      setError(null);
      stoppingRef.current = false;
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          onResultRef.current?.(result[0].transcript);
        } else {
          interim += result[0].transcript;
        }
      }
      setInterimTranscript(interim);
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === 'aborted' || event.error === 'no-speech') return;
      setError(
        event.error === 'not-allowed'
          ? 'Microphone access denied. Please allow microphone permissions.'
          : `Speech recognition error: ${event.error}`,
      );
      setIsListening(false);
    };

    recognition.onend = () => {
      // If the user didn't explicitly stop, the recogniser may have
      // timed out -- restart automatically so dictation feels continuous.
      if (!stoppingRef.current && recognitionRef.current === recognition) {
        try {
          recognition.start();
          return;
        } catch {
          // Ignore -- fall through to mark as stopped
        }
      }
      setIsListening(false);
      setInterimTranscript('');
    };

    recognitionRef.current = recognition;

    try {
      recognition.start();
    } catch (err: any) {
      setError(err.message || 'Failed to start speech recognition');
    }
  }, [lang]);

  const stopListening = useCallback(() => {
    stoppingRef.current = true;
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch { /* ignore */ }
    }
    setIsListening(false);
    setInterimTranscript('');
  }, []);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      stoppingRef.current = true;
      if (recognitionRef.current) {
        try { recognitionRef.current.abort(); } catch { /* ignore */ }
      }
    };
  }, []);

  return {
    isSupported,
    isListening,
    interimTranscript,
    error,
    startListening,
    stopListening,
  };
}

'use client';

/**
 * useModuleSettings — the shared load/save/reset lifecycle for module
 * settings pages. Every module page (rich or schema-driven) uses this.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { endpoints, ApiRequestError } from '@/lib/api';
import type { Settings } from '@/lib/types';

export function useModuleSettings(gid: string, module: string, defaults?: Settings) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saved, setSaved] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const defaultsRef = useRef<Settings | undefined>(defaults);
  defaultsRef.current = defaults;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await endpoints.settings(gid, module);
        if (cancelled) return;
        const merged = { ...(defaultsRef.current ?? {}), ...res.settings };
        setSettings(merged);
        setSaved(merged);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'could not load settings');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [gid, module]);

  const update = useCallback((patch: Settings) => {
    setSettings((s) => (s ? { ...s, ...patch } : s));
  }, []);

  const patch = useCallback(
    async (patchObj: Settings): Promise<Settings | null> => {
      setSaving(true);
      setError(null);
      try {
        const res = await endpoints.patchSettings(gid, module, patchObj);
        const merged = { ...(defaultsRef.current ?? {}), ...res.settings };
        setSettings(merged);
        setSaved(merged);
        return merged;
      } catch (e) {
        setError(e instanceof ApiRequestError ? e.message : 'save failed');
        return null;
      } finally {
        setSaving(false);
      }
    },
    [gid, module],
  );

  /** Save all dirty keys (settings vs saved diff). */
  const save = useCallback(async (): Promise<boolean> => {
    if (!settings || !saved) return false;
    const diff: Settings = {};
    for (const k of Object.keys(settings)) {
      if (JSON.stringify(settings[k]) !== JSON.stringify(saved[k])) {
        diff[k] = settings[k];
      }
    }
    if (Object.keys(diff).length === 0) return true;
    return (await patch(diff)) !== null;
  }, [settings, saved, patch]);

  const revert = useCallback(() => {
    setSettings(saved ? { ...saved } : null);
    setError(null);
  }, [saved]);

  const resetDefaults = useCallback(async (): Promise<boolean> => {
    if (!defaultsRef.current) return false;
    return (await patch({ ...defaultsRef.current })) !== null;
  }, [patch]);

  const dirty =
    !!settings &&
    !!saved &&
    Object.keys(settings).some(
      (k) => JSON.stringify(settings[k]) !== JSON.stringify(saved[k]),
    );

  return {
    settings, saved, loading, saving, error,
    dirty, update, save, patch, revert, resetDefaults,
    setSettings,
  };
}

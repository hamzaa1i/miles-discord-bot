'use client';

/**
 * useModuleSettings — the shared load/save/reset lifecycle for module
 * settings pages. Every module page (rich or schema-driven) uses this.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { endpoints, ApiRequestError, retryableStatus } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import type { Settings } from '@/lib/types';

export function useModuleSettings(gid: string, module: string, defaults?: Settings) {
  const toast = useToast();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saved, setSaved] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /**
   * True while a permission-check hiccup (backend 503: Discord was
   * unreachable to verify manage_guild) is being retried. Pages show
   * "verifying permissions…" instead of a scary error card.
   */
  const [verifying, setVerifying] = useState(false);
  const defaultsRef = useRef<Settings | undefined>(defaults);
  defaultsRef.current = defaults;

  useEffect(() => {
    let cancelled = false;
    const load = async (attempt: number): Promise<void> => {
      setLoading(true);
      try {
        const res = await endpoints.settings(gid, module);
        if (cancelled) return;
        const merged = { ...(defaultsRef.current ?? {}), ...res.settings };
        setSettings(merged);
        setSaved(merged);
        setError(null);
        setVerifying(false);
      } catch (e) {
        if (cancelled) return;
        const retryable =
          (e instanceof ApiRequestError && retryableStatus(e.status)) ||
          !(e instanceof ApiRequestError);
        if (retryable && attempt === 0) {
          // one automatic retry after a short beat — usually enough for
          // the transient Discord-verification blip to clear
          setVerifying(true);
          await new Promise((r) => setTimeout(r, 1000));
          if (!cancelled) return load(1);
          return;
        }
        setVerifying(false);
        setError(e instanceof Error ? e.message : 'could not load settings');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load(0);
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
        const msg = e instanceof ApiRequestError ? e.message : 'save failed';
        setError(msg);
        // every failed mutation gets a red toast (the save bar repeats it
        // inline, but a toast confirms it even when the bar is offscreen)
        toast.push(msg, 'error');
        return null;
      } finally {
        setSaving(false);
      }
    },
    [gid, module, toast],
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
    settings, saved, loading, saving, error, verifying,
    dirty, update, save, patch, revert, resetDefaults,
    setSettings,
  };
}

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
  /** Live mirrors of settings/saved — patch() must read the values at
   * CALL time (not closure-capture time) to snapshot unsaved edits made
   * in earlier events before its async response lands. */
  const settingsRef = useRef<Settings | null>(null);
  const savedRef = useRef<Settings | null>(null);
  settingsRef.current = settings;
  savedRef.current = saved;

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

  /**
   * PATCH settings and reconcile local + server state.
   *
   * PHASE O.2 — state-preservation semantics: the server response is
   * AUTHORITATIVE for the fields this patch covers, but a partial
   * immediate patch (the enable toggle sends only {enabled}) must not
   * discard unrelated unsaved local edits (selected channel, drafted
   * message, picked role…). Before the request we snapshot every dirty
   * key NOT included in the patch; after the response those keys are
   * re-applied on top of the fresh server state so they stay dirty and
   * Save can still commit them.
   *
   * Consequences:
   *  - fields in the patch body always take the server's value (the
   *    server may normalize, e.g. milestone_last pinning);
   *  - fields the server changed that were NOT locally dirty are
   *    accepted as-is (fresh server state, no stale echo);
   *  - fields both locally-dirty AND server-changed keep the local
   *    value: the user's edit stays visible and unsaved — last write
   *    wins on Save, exactly the pre-existing save() contract;
   *  - saved always mirrors the true server state, so dirty/revert
   *    remain honest.
   *
   * opts.preserveDirty=false (used by resetDefaults) drops the
   * snapshot so a reset really yields a clean state.
   */
  const patch = useCallback(
    async (
      patchObj: Settings,
      opts: { preserveDirty?: boolean } = {},
    ): Promise<Settings | null> => {
      const preserveDirty = opts.preserveDirty !== false;
      setSaving(true);
      setError(null);
      const before = settingsRef.current;
      const prevSaved = savedRef.current;
      const preserved: Settings = {};
      if (preserveDirty && before && prevSaved) {
        const patchKeys = new Set(Object.keys(patchObj));
        for (const k of Object.keys(before)) {
          if (
            !patchKeys.has(k) &&
            JSON.stringify(before[k]) !== JSON.stringify(prevSaved[k])
          ) {
            preserved[k] = before[k];
          }
        }
      }
      try {
        const res = await endpoints.patchSettings(gid, module, patchObj);
        const merged = { ...(defaultsRef.current ?? {}), ...res.settings };
        setSaved(merged);
        const next = { ...merged, ...preserved };
        setSettings(next);
        return next;
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
    // a reset must produce a CLEAN defaults state — do not preserve
    // dirty fields through it
    return (
      await patch({ ...defaultsRef.current }, { preserveDirty: false })
    ) !== null;
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

'use client';

/**
 * lib/guild.tsx — per-guild context: overview + channel/role pickers data.
 * Provided by app/servers/[guildId]/layout.tsx so every module page
 * can read guild metadata and render ChannelPicker/RolePicker without
 * re-fetching.
 *
 * Live-testing hardening:
 *  - overview/resources retry automatically on 429/502/503/504 (the
 *    backend answers 503 when Discord couldn't be reached to verify
 *    permissions — retrying beats showing a misleading error).
 *  - resources get a 5-minute sessionStorage cache per guild so pickers
 *    stay instant across page switches.
 *  - resourcesLoading/resourcesError are separate from overview state —
 *    a picker that can't load channels now SAYS so instead of silently
 *    rendering "no text channels".
 */

import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { endpoints, ApiRequestError, getWithRetry, retryableStatus } from './api';
import type { GuildOverview, GuildResources, AuditEntry } from './types';

const RESOURCES_TTL_MS = 5 * 60 * 1000;
const RESOURCES_CACHE_KEY = 'aurelia.resources.v2';

interface GuildState {
  guildId: string;
  overview: GuildOverview | null;
  resources: GuildResources | null;
  resourcesLoading: boolean;
  resourcesError: string | null;
  audit: AuditEntry[];
  loading: boolean;
  error: string | null;
  reloadOverview: () => Promise<void>;
  reloadResources: () => Promise<void>;
  reloadAudit: () => Promise<void>;
}

const GuildContext = createContext<GuildState>({
  guildId: '',
  overview: null,
  resources: null,
  resourcesLoading: false,
  resourcesError: null,
  audit: [],
  loading: true,
  error: null,
  reloadOverview: async () => {},
  reloadResources: async () => {},
  reloadAudit: async () => {},
});

function readCachedResources(gid: string): GuildResources | null {
  try {
    const raw = sessionStorage.getItem(`${RESOURCES_CACHE_KEY}.${gid}`);
    if (!raw) return null;
    const { data, at } = JSON.parse(raw) as { data: GuildResources; at: number };
    if (Date.now() - at > RESOURCES_TTL_MS) return null;
    return data;
  } catch {
    return null;
  }
}

function writeCachedResources(gid: string, data: GuildResources) {
  try {
    sessionStorage.setItem(
      `${RESOURCES_CACHE_KEY}.${gid}`,
      JSON.stringify({ data, at: Date.now() }),
    );
  } catch {
    // storage full / disabled — cache is best-effort
  }
}

export function GuildProvider({ guildId, children }: { guildId: string; children: React.ReactNode }) {
  const [overview, setOverview] = useState<GuildOverview | null>(null);
  const [resources, setResources] = useState<GuildResources | null>(() =>
    readCachedResources(guildId),
  );
  const [resourcesLoading, setResourcesLoading] = useState(true);
  const [resourcesError, setResourcesError] = useState<string | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reloadOverview = useCallback(async () => {
    try {
      setOverview(await endpoints.overview(guildId));
      setError(null);
    } catch (e) {
      if (e instanceof ApiRequestError) setError(e.message);
      else if (e instanceof Error) setError(e.message);
    }
  }, [guildId]);

  const reloadResources = useCallback(async () => {
    setResourcesLoading(true);
    setResourcesError(null);
    try {
      const res = await getWithRetry<GuildResources>(`/guild/${guildId}/resources`, {
        retries: 2,
        delayMs: 900,
      });
      setResources(res);
      writeCachedResources(guildId, res);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'could not load channels';
      setResourcesError(msg);
      // keep the cached copy if it exists — stale beats empty
      setResources((cur) => cur ?? readCachedResources(guildId));
    } finally {
      setResourcesLoading(false);
    }
  }, [guildId]);

  const reloadAudit = useCallback(async () => {
    try {
      const res = await endpoints.audit(guildId);
      setAudit(res.entries ?? []);
    } catch {
      // audit is best-effort
    }
  }, [guildId]);

  useEffect(() => {
    let cancelled = false;
    setResources(readCachedResources(guildId));
    setResourcesLoading(true);
    (async () => {
      setLoading(true);
      try {
        const [ov, res] = await Promise.all([
          endpoints.overview(guildId),
          getWithRetry<GuildResources>(`/guild/${guildId}/resources`, {
            retries: 2,
            delayMs: 900,
          }),
        ]);
        if (cancelled) return;
        setOverview(ov);
        setResources(res);
        setResourcesError(null);
        writeCachedResources(guildId, res);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        // which half failed? a failed resources fetch shouldn't blank the
        // overview — try them separately before giving up.
        try {
          const ov = await getWithRetry<GuildOverview>(`/guild/${guildId}/overview`, {
            retries: 1,
            delayMs: 800,
          });
          if (!cancelled) {
            setOverview(ov);
            setError(null);
          }
        } catch (e2) {
          if (!cancelled) {
            setError(
              e2 instanceof Error ? e2.message : 'could not load this server',
            );
          }
        }
        if (!cancelled && e instanceof ApiRequestError && !retryableStatus(e.status)) {
          setResourcesError(e.message);
        } else if (!cancelled) {
          setResourcesError(
            e instanceof Error ? e.message : 'could not load channels',
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          setResourcesLoading(false);
        }
      }
      void reloadAudit();
    })();
    return () => {
      cancelled = true;
    };
  }, [guildId, reloadAudit]);

  return (
    <GuildContext.Provider
      value={{
        guildId,
        overview,
        resources,
        resourcesLoading,
        resourcesError,
        audit,
        loading,
        error,
        reloadOverview,
        reloadResources,
        reloadAudit,
      }}
    >
      {children}
    </GuildContext.Provider>
  );
}

export function useGuild() {
  return useContext(GuildContext);
}

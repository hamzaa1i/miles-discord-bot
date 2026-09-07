'use client';

/**
 * SaveBar — sticky bottom bar with dirty-state awareness:
 * save / reset changes / reset to defaults.
 */

import { cn } from '@/lib/format';
import { Icon } from '@/components/icons';

export function SaveBar({
  dirty,
  saving,
  onSave,
  onRevert,
  onResetDefaults,
  error,
  note = 'changes apply immediately after saving',
}: {
  dirty: boolean;
  saving: boolean;
  onSave: () => void;
  onRevert?: () => void;
  onResetDefaults?: () => void;
  error?: string | null;
  note?: string;
}) {
  return (
    <div
      className={cn(
        'sticky bottom-4 z-30 mt-6 flex flex-col gap-3 rounded-card border bg-veloura-card/95 p-4 backdrop-blur transition-all sm:flex-row sm:items-center sm:justify-between',
        dirty ? 'border-veloura-pink/50 shadow-glow' : 'border-veloura-border',
      )}
    >
      <div className="min-w-0 text-sm">
        {error ? (
          <p className="flex items-center gap-2 text-veloura-danger">
            <Icon name="shieldAlert" size={14} />
            {error}
          </p>
        ) : dirty ? (
          <p className="flex items-center gap-2 text-veloura-pink">
            <Icon name="pencil" size={14} />
            unsaved changes
          </p>
        ) : (
          <p className="text-veloura-muted/80">{note}</p>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {onResetDefaults && (
          <button
            type="button"
            onClick={onResetDefaults}
            disabled={saving}
            className="veloura-button-ghost !min-h-[40px] px-4 text-xs"
          >
            reset to defaults
          </button>
        )}
        {onRevert && dirty && (
          <button
            type="button"
            onClick={onRevert}
            disabled={saving}
            className="veloura-button-ghost !min-h-[40px] px-4 text-xs"
          >
            revert
          </button>
        )}
        <button
          type="button"
          onClick={onSave}
          disabled={!dirty || saving}
          className="veloura-button-primary !min-h-[40px] px-6 text-xs"
        >
          {saving ? (
            'saving…'
          ) : (
            <>
              <Icon name="check" size={14} />
              save changes
            </>
          )}
        </button>
      </div>
    </div>
  );
}

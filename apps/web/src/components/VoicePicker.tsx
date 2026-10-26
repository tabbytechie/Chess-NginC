/**
 * A themed voice picker for spoken narration (REVIEW-009 + the coach voice).
 *
 * It replaces the browser's unstyled native <select> — whose popup is drawn by
 * the OS and cannot be matched to the design — with a small popover that reads
 * as part of the app: a chip trigger showing the current voice, then a themed
 * list grouped by engine, the active one checked, and any voice the backend
 * cannot yet serve (no key) dimmed and labelled rather than silently failing.
 *
 * Accessible: the trigger is a button (aria-haspopup/aria-expanded) and the
 * panel is a listbox of options (aria-selected), closed by Escape or a click
 * outside. It is presentational only — the caller owns the value and onChange.
 */
import { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown, Sparkles } from 'lucide-react';

export type VoicePickerOption = {
  id: string;
  name: string;
  kind: 'eleven' | 'browser';
  available: boolean;
};

type Props = {
  /** Accessible name for the control (and its popup). */
  label: string;
  value: string;
  options: VoicePickerOption[];
  onChange: (id: string) => void;
  /** Insert group headings by engine (the coach offers browser + ElevenLabs). */
  groups?: boolean;
  /** A reset entry rendered first (the coach's "system default" = empty id). */
  defaultOption?: { value: string; label: string };
  disabled?: boolean;
  placeholder?: string;
};

const GROUP_LABEL: Record<VoicePickerOption['kind'], string> = {
  eleven: 'Free ElevenLabs voices',
  browser: 'Browser voices',
};

/** Group options by engine, keeping first-appearance order. */
function sections(
  options: VoicePickerOption[],
): { kind: VoicePickerOption['kind']; items: VoicePickerOption[] }[] {
  const order: VoicePickerOption['kind'][] = [];
  const buckets = new Map<VoicePickerOption['kind'], VoicePickerOption[]>();
  for (const option of options) {
    let bucket = buckets.get(option.kind);
    if (!bucket) {
      bucket = [];
      buckets.set(option.kind, bucket);
      order.push(option.kind);
    }
    bucket.push(option);
  }
  return order.map((kind) => ({ kind, items: buckets.get(kind) ?? [] }));
}

export default function VoicePicker({
  label,
  value,
  options,
  onChange,
  groups = false,
  defaultOption,
  disabled = false,
  placeholder = 'Choose a voice',
}: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  const selected = options.find((option) => option.id === value);
  const shownName =
    selected?.name ??
    (defaultOption && value === defaultOption.value ? defaultOption.label : placeholder);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  function choose(id: string) {
    onChange(id);
    setOpen(false);
  }

  const optionRow = (option: VoicePickerOption) => {
    const isSelected = option.id === value;
    // A browser voice is always speakable; an ElevenLabs voice needs a key.
    const usable = option.kind === 'browser' || option.available;
    return (
      <button
        key={`${option.kind}-${option.id}`}
        type="button"
        role="option"
        aria-selected={isSelected}
        disabled={!usable}
        className={`voice-option${isSelected ? ' selected' : ''}`}
        onClick={() => usable && choose(option.id)}
      >
        {option.kind === 'eleven' && (
          <Sparkles size={13} className="voice-option-mark" aria-hidden="true" />
        )}
        <span className="voice-option-name">{option.name}</span>
        {option.kind === 'eleven' && !option.available && (
          <span className="voice-option-hint">needs a key</span>
        )}
        {isSelected && <Check size={14} className="voice-option-check" aria-hidden="true" />}
      </button>
    );
  };

  return (
    <div className="voice-picker" ref={rootRef}>
      <button
        type="button"
        className="voice-trigger"
        aria-label={label}
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="voice-trigger-name">{shownName}</span>
        <ChevronDown
          size={14}
          className={`voice-trigger-caret${open ? ' open' : ''}`}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div className="voice-menu" role="listbox" aria-label={label}>
          {defaultOption && (
            <button
              type="button"
              role="option"
              aria-selected={value === defaultOption.value}
              className={`voice-option voice-option-default${
                value === defaultOption.value ? ' selected' : ''
              }`}
              onClick={() => choose(defaultOption.value)}
            >
              <span className="voice-option-name">{defaultOption.label}</span>
              {value === defaultOption.value && (
                <Check size={14} className="voice-option-check" aria-hidden="true" />
              )}
            </button>
          )}

          {options.length === 0 && !defaultOption && (
            <p className="voice-empty">No voices to show right now.</p>
          )}

          {groups
            ? sections(options).map((section) => (
                <div
                  key={section.kind}
                  className="voice-group"
                  role="group"
                  aria-label={GROUP_LABEL[section.kind]}
                >
                  <div className="voice-group-label">{GROUP_LABEL[section.kind]}</div>
                  {section.items.map(optionRow)}
                </div>
              ))
            : options.map(optionRow)}
        </div>
      )}
    </div>
  );
}

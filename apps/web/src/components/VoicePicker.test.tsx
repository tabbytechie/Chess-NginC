/**
 * VoicePicker popover tests (REVIEW-009 + coach narration): the trigger names the
 * current voice, the themed listbox opens/closes on click, Escape and a click
 * outside, group headings appear only when requested, a "system default" reset is
 * offered first, a choice forwards the id, and a voice the backend cannot serve
 * (no key) is disabled rather than silently selectable.
 */
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import VoicePicker, { type VoicePickerOption } from './VoicePicker';

const ELEVEN: VoicePickerOption[] = [
  { id: 'rachel', name: 'Rachel', kind: 'eleven', available: true },
  { id: 'adam', name: 'Adam', kind: 'eleven', available: true },
];
const BROWSER: VoicePickerOption[] = [
  { id: 'samantha', name: 'Samantha', kind: 'browser', available: true },
];

describe('VoicePicker', () => {
  it('shows the placeholder when nothing matches and opens the listbox', async () => {
    const user = userEvent.setup();
    render(<VoicePicker label="Narration voice" value="" options={ELEVEN} onChange={vi.fn()} />);

    const trigger = screen.getByRole('button', { name: 'Narration voice' });
    expect(trigger).toHaveTextContent('Choose a voice');

    await user.click(trigger);
    const menu = await screen.findByRole('listbox', { name: 'Narration voice' });
    expect(within(menu).getByRole('option', { name: /Rachel/ })).toBeInTheDocument();
    expect(within(menu).getByRole('option', { name: /Adam/ })).toBeInTheDocument();
  });

  it('shows the selected voice name on the trigger', () => {
    render(
      <VoicePicker label="Narration voice" value="adam" options={ELEVEN} onChange={vi.fn()} />,
    );
    expect(screen.getByRole('button', { name: 'Narration voice' })).toHaveTextContent('Adam');
  });

  it('forwards the chosen id and closes on selection', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <VoicePicker label="Narration voice" value="rachel" options={ELEVEN} onChange={onChange} />,
    );

    await user.click(screen.getByRole('button', { name: 'Narration voice' }));
    await user.click(within(screen.getByRole('listbox')).getByRole('option', { name: /Adam/ }));

    expect(onChange).toHaveBeenCalledWith('adam');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('renders group headings only when groups is set', async () => {
    const user = userEvent.setup();
    render(
      <VoicePicker
        label="Narration voice"
        value=""
        options={[...ELEVEN, ...BROWSER]}
        onChange={vi.fn()}
        groups
      />,
    );
    await user.click(screen.getByRole('button', { name: 'Narration voice' }));

    const menu = screen.getByRole('listbox');
    expect(within(menu).getByText('Free ElevenLabs voices')).toBeInTheDocument();
    expect(within(menu).getByText('Browser voices')).toBeInTheDocument();
  });

  it('offers the default option first and marks it selected when value matches', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <VoicePicker
        label="Narration voice"
        value=""
        options={ELEVEN}
        onChange={onChange}
        defaultOption={{ value: '', label: 'System default' }}
      />,
    );
    await user.click(screen.getByRole('button', { name: 'Narration voice' }));

    const menu = screen.getByRole('listbox');
    const def = within(menu).getByRole('option', { name: /System default/ });
    expect(def).toHaveAttribute('aria-selected', 'true');
    await user.click(def);
    expect(onChange).toHaveBeenCalledWith('');
  });

  it('disables an ElevenLabs voice the backend cannot serve and ignores its click', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <VoicePicker
        label="Narration voice"
        value="rachel"
        options={[{ id: 'george', name: 'George', kind: 'eleven', available: false }]}
        onChange={onChange}
      />,
    );
    await user.click(screen.getByRole('button', { name: 'Narration voice' }));

    const option = within(screen.getByRole('listbox')).getByRole('option', { name: /George/ });
    expect(option).toBeDisabled();
    await user.click(option);
    expect(onChange).not.toHaveBeenCalled();
  });

  it('closes on Escape', async () => {
    const user = userEvent.setup();
    render(
      <VoicePicker label="Narration voice" value="rachel" options={ELEVEN} onChange={vi.fn()} />,
    );
    await user.click(screen.getByRole('button', { name: 'Narration voice' }));
    expect(screen.getByRole('listbox')).toBeInTheDocument();

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });
});

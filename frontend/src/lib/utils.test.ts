import { describe, it, expect } from 'vitest';
import { cn } from './utils';

describe('cn utility', () => {
  it('merges class strings', () => {
    expect(cn('foo', 'bar')).toBe('foo bar');
  });

  it('deduplicates conflicting tailwind classes', () => {
    expect(cn('px-4', 'px-8')).toBe('px-8');
  });

  it('handles conditional classes', () => {
    expect(cn('base', false && 'hidden', 'visible')).toBe('base visible');
  });

  it('handles undefined and null', () => {
    expect(cn('base', undefined, null)).toBe('base');
  });

  it('handles array inputs', () => {
    expect(cn(['foo', 'bar'])).toBe('foo bar');
  });

  it('handles object inputs', () => {
    expect(cn({ foo: true, bar: false })).toBe('foo');
  });

  it('returns empty string for no arguments', () => {
    expect(cn()).toBe('');
  });
});

import { type KeyboardEvent, useEffect, useId, useRef, useState } from 'react'

import { discoverDrugTerms, discoverReactionTerms } from '../api/client'
import type { SourceTerm } from '../api/types'

const MINIMUM_QUERY_LENGTH = 2
const SUGGESTION_LIMIT = 10
const DEBOUNCE_MILLISECONDS = 250

type SearchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; items: SourceTerm[] }
  | { status: 'error' }

interface SourceTermComboboxProps {
  id: string
  label: string
  kind: 'drugs' | 'reactions'
  value: string
  onChange: (value: string) => void
}

export function SourceTermCombobox({
  id,
  label,
  kind,
  value,
  onChange,
}: SourceTermComboboxProps) {
  const generatedId = useId()
  const listboxId = `${id}-${generatedId}-suggestions`
  const statusId = `${id}-${generatedId}-status`
  const [search, setSearch] = useState<SearchState>({ status: 'idle' })
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const [retry, setRetry] = useState(0)
  const skipNextSearch = useRef(false)

  const normalizedQuery = value.trim()

  useEffect(() => {
    if (skipNextSearch.current) {
      skipNextSearch.current = false
      return
    }
    if (normalizedQuery.length < MINIMUM_QUERY_LENGTH) return

    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setSearch({ status: 'loading' })
      const request = kind === 'drugs' ? discoverDrugTerms : discoverReactionTerms
      void request(normalizedQuery, SUGGESTION_LIMIT, controller.signal)
        .then((response) => {
          setSearch({ status: 'ready', items: response.items })
          setActiveIndex(-1)
          setOpen(true)
        })
        .catch((error: unknown) => {
          if (error instanceof DOMException && error.name === 'AbortError') return
          setSearch({ status: 'error' })
          setOpen(true)
        })
    }, DEBOUNCE_MILLISECONDS)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [kind, normalizedQuery, retry])

  function updateValue(nextValue: string) {
    onChange(nextValue)
    setActiveIndex(-1)
    if (nextValue.trim().length < MINIMUM_QUERY_LENGTH) {
      setSearch({ status: 'idle' })
      setOpen(false)
    } else {
      setOpen(true)
    }
  }

  function selectTerm(term: string) {
    skipNextSearch.current = true
    onChange(term)
    setOpen(false)
    setActiveIndex(-1)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!open || search.status !== 'ready' || search.items.length === 0) {
      if (event.key === 'Escape') setOpen(false)
      return
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((current) => (current + 1) % search.items.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((current) => (current <= 0 ? search.items.length - 1 : current - 1))
    } else if (event.key === 'Enter' && activeIndex >= 0) {
      event.preventDefault()
      const selected = search.items[activeIndex]
      if (selected !== undefined) selectTerm(selected.term)
    } else if (event.key === 'Escape') {
      event.preventDefault()
      setOpen(false)
    }
  }

  const activeOptionId = activeIndex >= 0 ? `${listboxId}-${activeIndex}` : undefined

  return (
    <div className="source-term-combobox">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-activedescendant={activeOptionId}
        aria-describedby={statusId}
        autoComplete="off"
        required
        value={value}
        onChange={(event) => updateValue(event.target.value)}
        onFocus={() => {
          if (search.status === 'ready' || search.status === 'error') setOpen(true)
        }}
        onKeyDown={handleKeyDown}
      />
      <div className="source-term-combobox__status" id={statusId} aria-live="polite">
        {normalizedQuery.length < MINIMUM_QUERY_LENGTH
          ? `Enter at least ${MINIMUM_QUERY_LENGTH} characters to find source-derived terms.`
          : search.status === 'loading'
            ? 'Loading suggestions…'
            : 'Manual source-term entry is allowed.'}
      </div>
      {open && (
        <div className="source-term-combobox__popover">
          {search.status === 'ready' && search.items.length > 0 && (
            <ul id={listboxId} role="listbox" aria-label={`${label} suggestions`}>
              {search.items.map((item, index) => (
                <li
                  id={`${listboxId}-${index}`}
                  role="option"
                  aria-selected={activeIndex === index}
                  key={item.term}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => selectTerm(item.term)}
                >
                  {item.term}
                </li>
              ))}
            </ul>
          )}
          {search.status === 'ready' && search.items.length === 0 && (
            <p>No source-derived terms matched. You can keep your manual entry.</p>
          )}
          {search.status === 'error' && (
            <div role="alert">
              <p>Suggestions are unavailable. You can keep your manual entry.</p>
              <button type="button" className="text-button" onClick={() => setRetry((value) => value + 1)}>
                Retry suggestions
              </button>
            </div>
          )}
          {(search.status === 'ready' || search.status === 'error') && (
            <small>Source-derived FAERS terms are not clinical recommendations or synonym mappings.</small>
          )}
        </div>
      )}
    </div>
  )
}

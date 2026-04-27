/**
 * HTML sanitization utilities for any string that originates from a
 * source we don't control (book descriptions from external metadata
 * providers, article markdown from Instapaper, LLM-generated analysis
 * content, user-pasted notes).
 *
 * The Svelte `{@html ...}` directive renders strings as raw HTML, so
 * passing untrusted text through it is a stored-XSS vector. Without
 * sanitization, an attacker who controls metadata or article content
 * (a malicious enrichment provider, a Wikipedia edit, a smuggled
 * Instapaper article) can execute scripts in the user's browser and
 * steal the localStorage JWT.
 *
 * Use `sanitizeHtml(html)` for HTML inputs and `sanitizeMarkdown(md)`
 * for Markdown inputs. Both pass through DOMPurify with a strict
 * allowlist (no scripts, no event handlers, no javascript: URIs).
 */

import DOMPurify, { type Config } from 'dompurify';
import { marked } from 'marked';

// Tags we allow in rendered prose. Common formatting + headings + lists
// + blockquotes + tables + figures + code blocks + links + images.
// Conspicuously absent: <script>, <iframe>, <object>, <embed>, <form>,
// <input>, <button>, <link>, <meta>, <style>, <svg>, <math>, <audio>,
// <video>, anything that can execute code or load external resources.
const ALLOWED_TAGS = [
  'a', 'b', 'blockquote', 'br', 'code', 'div', 'em', 'figcaption',
  'figure', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'li',
  'ol', 'p', 'pre', 's', 'span', 'strong', 'sub', 'sup', 'table',
  'tbody', 'td', 'th', 'thead', 'tr', 'u', 'ul'
];

const ALLOWED_ATTR = ['href', 'title', 'alt', 'src', 'class'];

const PURIFY_CONFIG: Config = {
  ALLOWED_TAGS,
  ALLOWED_ATTR,
  // Block any URL whose protocol isn't in this list. Critically excludes
  // `javascript:` and `data:` (data: can carry text/html with scripts).
  ALLOWED_URI_REGEXP: /^(?:https?:|mailto:|tel:|#)/i,
  KEEP_CONTENT: true,
  // Strip event handlers even if a tag is in the allowlist. DOMPurify
  // does this by default; we set it explicitly to be loud about intent.
  ADD_ATTR: [],
  FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover', 'onmouseout',
                'onfocus', 'onblur', 'onkeydown', 'onkeyup', 'onkeypress',
                'onsubmit', 'onchange', 'onabort'],
};

export function sanitizeHtml(html: string | null | undefined): string {
  if (!html) return '';
  return DOMPurify.sanitize(html, PURIFY_CONFIG) as unknown as string;
}

export function sanitizeMarkdown(markdown: string | null | undefined): string {
  if (!markdown) return '';
  // marked.parse can return a Promise when async helpers are configured;
  // the default config is sync and we keep it that way for use in
  // reactive bindings.
  const rendered = marked.parse(markdown, { async: false }) as string;
  return sanitizeHtml(rendered);
}

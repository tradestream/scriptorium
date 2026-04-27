import type {
  User,
  Book,
  BookListResponse,
  Work,
  WorkListResponse,
  Edition,
  UserEdition,
  Loan,
  Library,
  LibraryAccess,
  Shelf,
  IngestLog,
  ReadProgress,
  AuthorDetail,
  TagDetail,
  SeriesDetail,
  SeriesPageData,
  LoginRequest,
  RegisterRequest,
  AuthResponse,
  Marginalium,
  MarginaliumKind,
  MarginaliumWithBook,
  ReadingLevel,
} from '$lib/types/index';

// ── Server URL (Capacitor native: absolute; web: relative) ────────────────────

let _serverUrl = '';

/** Read the stored server URL (set by ServerSetup on first native launch). */
export function getServerUrl(): string {
  if (!_serverUrl && typeof window !== 'undefined') {
    _serverUrl = localStorage.getItem('scriptorium_server_url') || '';
  }
  return _serverUrl;
}

/** Persist the server URL (strips trailing slash). */
export function setServerUrl(url: string) {
  _serverUrl = url.replace(/\/+$/, '');
  if (typeof window !== 'undefined') {
    if (_serverUrl) {
      localStorage.setItem('scriptorium_server_url', _serverUrl);
    } else {
      localStorage.removeItem('scriptorium_server_url');
    }
  }
}

export function getApiBase(): string {
  return `${getServerUrl()}/api/v1`;
}

// ─────────────────────────────────────────────────────────────────────────────

let authToken: string | null = null;

export function setAuthToken(token: string | null) {
  authToken = token;
  if (token) {
    localStorage.setItem('auth_token', token);
  } else {
    localStorage.removeItem('auth_token');
  }
}

export function getAuthToken(): string | null {
  if (!authToken && typeof window !== 'undefined') {
    authToken = localStorage.getItem('auth_token');
  }
  return authToken;
}

export function bookCoverUrl(book: Book): string | null {
  if (!book.cover_hash) return null;
  const token = getAuthToken();
  const base = `${getApiBase()}/books/${book.id}/cover`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

export function editionCoverUrl(edition: Edition): string | null {
  if (!edition.cover_hash) return null;
  const token = getAuthToken();
  const base = `${getApiBase()}/editions/${edition.id}/cover`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

async function fetchAPI<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${getApiBase()}${endpoint}`;
  const isFormData = options.body instanceof FormData;
  const headers = new Headers(options.headers || {});

  if (!isFormData) {
    headers.set('Content-Type', 'application/json');
  }

  const token = getAuthToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    const text = await response.text();
    let message: string;
    try {
      const json = JSON.parse(text);
      const detail = json.detail || json.message || '';
      message = typeof detail === 'string' ? detail : JSON.stringify(detail);
    } catch {
      // Non-JSON response (e.g. Cloudflare error page) — use a friendly message
      if (response.status === 502) {
        message = 'Server is unreachable. Please try again in a few minutes.';
      } else if (response.status === 503) {
        message = 'Server is temporarily unavailable. Please try again shortly.';
      } else if (response.status === 504) {
        message = 'Server timed out. Please try again.';
      } else {
        message = `Unexpected error (${response.status}). Please try again.`;
      }
    }
    // Keep error messages short for UI display
    if (message.length > 200) message = message.slice(0, 200) + '…';
    throw new Error(message);
  }

  if (response.status === 204) return undefined as T;
  return response.json();
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function login(credentials: LoginRequest): Promise<AuthResponse> {
  return fetchAPI('/auth/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
  });
}

export async function register(data: RegisterRequest): Promise<AuthResponse> {
  return fetchAPI('/auth/register', { method: 'POST', body: JSON.stringify(data) });
}

export function logout(): void {
  setAuthToken(null);
}

export async function getCurrentUser(): Promise<User> {
  return fetchAPI('/auth/me');
}

export async function updateProfile(data: { display_name?: string; email?: string }): Promise<User> {
  return fetchAPI('/auth/me', { method: 'PATCH', body: JSON.stringify(data) });
}

export async function getOidcConfig(): Promise<{ enabled: boolean }> {
  return fetchAPI('/auth/oidc/config');
}

// ── Libraries ─────────────────────────────────────────────────────────────────

export async function getLibraries(includeHidden = false): Promise<Library[]> {
  const q = includeHidden ? '?include_hidden=true' : '';
  return fetchAPI(`/libraries${q}`);
}

export async function getLibrary(id: number | string): Promise<Library> {
  return fetchAPI(`/libraries/${id}`);
}

export async function createLibrary(data: { name: string; description?: string; path: string }): Promise<Library> {
  return fetchAPI('/libraries', { method: 'POST', body: JSON.stringify(data) });
}

export async function updateLibrary(id: number | string, data: Partial<Library>): Promise<Library> {
  return fetchAPI(`/libraries/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function deleteLibrary(id: number | string): Promise<void> {
  return fetchAPI(`/libraries/${id}`, { method: 'DELETE' });
}

export async function reorderLibraries(libraryIds: number[]): Promise<void> {
  return fetchAPI('/libraries/reorder', { method: 'PATCH', body: JSON.stringify({ library_ids: libraryIds }) });
}

export async function scanLibrary(id: number | string): Promise<{ message: string }> {
  return fetchAPI(`/libraries/${id}/scan`, { method: 'POST' });
}

export async function uploadBookFile(file: File): Promise<{ filename: string; size: number; status: string }> {
  const form = new FormData();
  form.append('file', file);
  const url = `${getApiBase()}/ingest/upload`;
  const token = getAuthToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await fetch(url, { method: 'POST', headers, body: form });
  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Upload failed (${response.status}): ${err}`);
  }
  return response.json();
}

export async function getLibraryAccess(libraryId: number): Promise<LibraryAccess[]> {
  return fetchAPI(`/libraries/${libraryId}/access`);
}

export async function grantLibraryAccess(libraryId: number, userId: number, accessLevel = 'read'): Promise<LibraryAccess> {
  return fetchAPI(`/libraries/${libraryId}/access`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, access_level: accessLevel }),
  });
}

export async function revokeLibraryAccess(libraryId: number, userId: number): Promise<void> {
  return fetchAPI(`/libraries/${libraryId}/access/${userId}`, { method: 'DELETE' });
}

// ── Users ──────────────────────────────────────────────────────────────────────

export async function getUsers(): Promise<User[]> {
  return fetchAPI('/users');
}

// ── Books ─────────────────────────────────────────────────────────────────────

export interface BooksQuery {
  skip?: number;
  limit?: number;
  library_id?: number;
  include_hidden?: boolean;
  search?: string;
  author_id?: number;
  tag_id?: number;
  abs_linked?: boolean;
  format?: string;
  sort_by?: 'date_added' | 'title';
}

export async function getBooks(query: BooksQuery = {}): Promise<BookListResponse> {
  const params = new URLSearchParams();
  if (query.skip !== undefined) params.set('skip', String(query.skip));
  if (query.limit !== undefined) params.set('limit', String(query.limit));
  if (query.library_id !== undefined) params.set('library_id', String(query.library_id));
  if (query.include_hidden) params.set('include_hidden', 'true');
  if (query.search) params.set('search', query.search);
  if (query.author_id !== undefined) params.set('author_id', String(query.author_id));
  if (query.tag_id !== undefined) params.set('tag_id', String(query.tag_id));
  if (query.abs_linked) params.set('abs_linked', 'true');
  if (query.format) params.set('format', query.format);
  if (query.sort_by) params.set('sort_by', query.sort_by);
  const qs = params.toString();
  return fetchAPI(`/books${qs ? '?' + qs : ''}`);
}

export async function getBook(id: number | string): Promise<Book> {
  return fetchAPI(`/books/${id}`);
}

export interface BookCreateData {
  title: string;
  subtitle?: string | null;
  description?: string | null;
  isbn?: string | null;
  language?: string | null;
  published_date?: string | null;
  publisher?: string | null;
  library_id: number;
  physical_copy?: boolean;
  location?: string | null;
  location_id?: number | null;
  author_names?: string[];
  tag_names?: string[];
}

export async function createBook(data: BookCreateData): Promise<Book> {
  return fetchAPI('/books', { method: 'POST', body: JSON.stringify(data) });
}

export async function lookupBookMetadata(params: { title?: string; author?: string; isbn?: string }): Promise<Record<string, unknown>> {
  const qs = new URLSearchParams();
  if (params.title) qs.set('title', params.title);
  if (params.author) qs.set('author', params.author);
  if (params.isbn) qs.set('isbn', params.isbn);
  return fetchAPI(`/books/lookup?${qs.toString()}`);
}

export async function updateBook(id: number | string, data: Record<string, unknown>): Promise<Book> {
  return fetchAPI(`/books/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function deleteBook(id: number | string): Promise<void> {
  return fetchAPI(`/books/${id}`, { method: 'DELETE' });
}

export interface EnrichmentProvider {
  name: string;
  available: boolean;
  for_comics: boolean;
}

export async function getEnrichmentProviders(): Promise<EnrichmentProvider[]> {
  return fetchAPI('/books/enrichment/providers');
}

export async function enrichBook(bookId: number | string, provider?: string): Promise<Book> {
  const qs = provider ? `?provider=${encodeURIComponent(provider)}` : '';
  return fetchAPI(`/books/${bookId}/enrich${qs}`, { method: 'POST' });
}

export async function extractFromUrl(url: string): Promise<Record<string, unknown>> {
  return fetchAPI('/books/extract-from-url', { method: 'POST', body: JSON.stringify({ url }) });
}

export async function enrichBookFromUrl(bookId: number | string, url: string): Promise<Book> {
  return fetchAPI(`/books/${bookId}/enrich-from-url`, { method: 'POST', body: JSON.stringify({ url }) });
}

export interface EnrichStreamEvent {
  provider: string;
  status: 'ok' | 'error' | 'skipped';
  fields: string[];
  has_cover: boolean;
  has_description: boolean;
  title: string | null;
  event?: string;
}

export async function getEnrichmentProposals(bookId: number | string): Promise<Array<Record<string, any>>> {
  return fetchAPI(`/books/${bookId}/enrich/proposals`);
}

export function enrichBookStream(
  bookId: number | string,
  onEvent: (event: EnrichStreamEvent) => void,
  onDone: () => void,
): AbortController {
  const controller = new AbortController();
  const token = getAuthToken();
  const url = `${getApiBase()}/books/${bookId}/enrich/stream`;

  fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
    signal: controller.signal,
  }).then(async (resp) => {
    if (!resp.ok || !resp.body) { onDone(); return; }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            onEvent(data);
          } catch { /* skip */ }
        }
      }
    }
    onDone();
  }).catch(() => onDone());

  return controller;
}

export async function convertBookFile(bookId: number | string, fileId: number | string, outputFormat: string): Promise<Book> {
  return fetchAPI(`/books/${bookId}/files/${fileId}/convert?output_format=${encodeURIComponent(outputFormat)}`, { method: 'POST' });
}

export async function uploadBookCover(bookId: number | string, file: File): Promise<Book> {
  const form = new FormData();
  form.append('cover', file);
  return fetchAPI(`/books/${bookId}/cover`, { method: 'PUT', body: form });
}

export async function downloadBookFile(bookId: number | string, fileId: number | string): Promise<Blob> {
  const url = `${getApiBase()}/books/${bookId}/download/${fileId}`;
  const token = getAuthToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await fetch(url, { headers });
  if (!response.ok) throw new Error(`Download failed (${response.status})`);
  return response.blob();
}

// ── Works ─────────────────────────────────────────────────────────────────────

export interface WorksQuery {
  skip?: number;
  limit?: number;
  library_id?: number;
  search?: string;
  author_id?: number;
  tag_id?: number;
  sort_by?: 'date_added' | 'title';
}

export async function getWorks(query: WorksQuery = {}): Promise<WorkListResponse> {
  const params = new URLSearchParams();
  if (query.skip !== undefined) params.set('skip', String(query.skip));
  if (query.limit !== undefined) params.set('limit', String(query.limit));
  if (query.library_id !== undefined) params.set('library_id', String(query.library_id));
  if (query.search) params.set('search', query.search);
  if (query.author_id !== undefined) params.set('author_id', String(query.author_id));
  if (query.tag_id !== undefined) params.set('tag_id', String(query.tag_id));
  if (query.sort_by) params.set('sort_by', query.sort_by);
  const qs = params.toString();
  return fetchAPI(`/works${qs ? '?' + qs : ''}`);
}

export async function getWork(id: number | string): Promise<Work> {
  return fetchAPI(`/works/${id}`);
}

export async function createWork(data: {
  title: string;
  subtitle?: string | null;
  description?: string | null;
  language?: string | null;
  original_language?: string | null;
  original_publication_year?: number | null;
  characters?: string[];
  places?: string[];
  awards?: import('$lib/types/index').WorkAward[];
  author_names?: string[];
  tag_names?: string[];
}): Promise<Work> {
  return fetchAPI('/works', { method: 'POST', body: JSON.stringify(data) });
}

export async function updateWork(id: number | string, data: Record<string, unknown>): Promise<Work> {
  return fetchAPI(`/works/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function deleteWork(id: number | string): Promise<void> {
  return fetchAPI(`/works/${id}`, { method: 'DELETE' });
}

export async function getWorkEditions(workId: number | string): Promise<Edition[]> {
  return fetchAPI(`/works/${workId}/editions`);
}

// ── Editions ──────────────────────────────────────────────────────────────────

export async function getEdition(id: number | string): Promise<Edition> {
  return fetchAPI(`/editions/${id}`);
}

export async function createEdition(data: {
  work_id: number;
  library_id: number;
  isbn?: string | null;
  publisher?: string | null;
  published_date?: string | null;
  language?: string | null;
  format?: string | null;
  page_count?: number | null;
  physical_copy?: boolean;
  translator_names?: string[];
}): Promise<Edition> {
  return fetchAPI('/editions', { method: 'POST', body: JSON.stringify(data) });
}

export async function updateEdition(id: number | string, data: Record<string, unknown>): Promise<Edition> {
  return fetchAPI(`/editions/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function deleteEdition(id: number | string): Promise<void> {
  return fetchAPI(`/editions/${id}`, { method: 'DELETE' });
}

export function editionFileUrl(editionId: number | string, fileId: number | string): string {
  const token = getAuthToken();
  const base = `${getApiBase()}/editions/${editionId}/download/${fileId}`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

export async function getUserEdition(editionId: number | string): Promise<UserEdition | null> {
  return fetchAPI(`/editions/${editionId}/user-edition`);
}

export async function upsertUserEdition(editionId: number | string, data: Partial<UserEdition>): Promise<UserEdition> {
  return fetchAPI(`/editions/${editionId}/user-edition`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function getEditionLoans(editionId: number | string): Promise<Loan[]> {
  return fetchAPI(`/editions/${editionId}/loans`);
}

export async function createLoan(editionId: number | string, data: {
  loaned_to_user_id?: number | null;
  loaned_to_name?: string | null;
  due_back?: string | null;
  notes?: string | null;
}): Promise<Loan> {
  return fetchAPI(`/editions/${editionId}/loans`, { method: 'POST', body: JSON.stringify(data) });
}

export async function updateLoan(editionId: number | string, loanId: number, data: {
  due_back?: string | null;
  returned_at?: string | null;
  notes?: string | null;
}): Promise<Loan> {
  return fetchAPI(`/editions/${editionId}/loans/${loanId}`, { method: 'PATCH', body: JSON.stringify(data) });
}

// ── Search ────────────────────────────────────────────────────────────────────

export async function searchBooks(
  q: string,
  opts: { library_id?: number; skip?: number; limit?: number } = {}
): Promise<BookListResponse> {
  const params = new URLSearchParams({ q });
  if (opts.library_id !== undefined) params.set('library_id', String(opts.library_id));
  if (opts.skip !== undefined) params.set('skip', String(opts.skip));
  if (opts.limit !== undefined) params.set('limit', String(opts.limit));
  return fetchAPI(`/search?${params}`);
}

export interface UnifiedSearchResult {
  books: { id: number; type: 'book'; title: string; author?: string | null; cover_hash?: string | null; cover_format?: string | null; isbn?: string | null }[];
  articles: { id: number; type: 'article'; title: string; author?: string | null; domain?: string | null; url: string; progress: number }[];
  annotations: { id: number; type: 'annotation'; content: string; book_id: number; book_title: string; annotation_type: string }[];
  marginalia: { id: number; type: 'marginalium'; content: string; book_id: number; book_title: string; kind: string }[];
  total: number;
}

export async function unifiedSearch(q: string, limit: number = 10): Promise<UnifiedSearchResult> {
  return fetchAPI(`/search/all?q=${encodeURIComponent(q)}&limit=${limit}`);
}

// ── Browse ────────────────────────────────────────────────────────────────────

export async function getAuthors(skip = 0, limit = 100): Promise<AuthorDetail[]> {
  return fetchAPI(`/authors?skip=${skip}&limit=${limit}`);
}

export async function getAuthorBooks(
  authorId: number | string,
  opts: { skip?: number; limit?: number } = {}
): Promise<{ id: number; name: string; description: string | null; photo_url: string | null; book_count: number; books: Book[]; skip: number; limit: number }> {
  const params = new URLSearchParams();
  if (opts.skip !== undefined) params.set('skip', String(opts.skip));
  if (opts.limit !== undefined) params.set('limit', String(opts.limit));
  const qs = params.toString();
  return fetchAPI(`/authors/${authorId}${qs ? '?' + qs : ''}`);
}

export async function getTags(skip = 0, limit = 200): Promise<TagDetail[]> {
  return fetchAPI(`/tags?skip=${skip}&limit=${limit}`);
}

export async function getTagBooks(
  tagId: number | string,
  opts: { skip?: number; limit?: number } = {}
): Promise<{ id: number; name: string; book_count: number; books: Book[]; skip: number; limit: number }> {
  const params = new URLSearchParams();
  if (opts.skip !== undefined) params.set('skip', String(opts.skip));
  if (opts.limit !== undefined) params.set('limit', String(opts.limit));
  const qs = params.toString();
  return fetchAPI(`/tags/${tagId}${qs ? '?' + qs : ''}`);
}

export async function getAllSeries(skip = 0, limit = 100, opts?: { library_id?: number; format?: string }): Promise<SeriesDetail[]> {
  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  if (opts?.library_id) params.set('library_id', String(opts.library_id));
  if (opts?.format) params.set('format', opts.format);
  return fetchAPI(`/series?${params}`);
}

export async function getSeriesBooks(seriesId: number | string): Promise<SeriesPageData> {
  return fetchAPI(`/series/${seriesId}`);
}

export async function getBookSeriesEntries(bookId: number): Promise<import('$lib/types/index').BookSeriesEntry[]> {
  return fetchAPI(`/books/${bookId}/series-entries`);
}

export async function updateSeriesEntries(
  seriesId: number,
  entries: { book_id: number; position: number | null; volume: string | null; arc: string | null }[]
): Promise<void> {
  await fetchAPI(`/series/${seriesId}/entries`, { method: 'PATCH', body: JSON.stringify(entries) });
}

// ── Metadata management ───────────────────────────────────────────────────────

export async function renameAuthor(id: number, name: string): Promise<AuthorDetail> {
  return fetchAPI(`/metadata/authors/${id}`, { method: 'PATCH', body: JSON.stringify({ name }) });
}
export async function mergeAuthors(targetId: number, sourceIds: number[]): Promise<AuthorDetail> {
  return fetchAPI(`/metadata/authors/${targetId}/merge`, { method: 'POST', body: JSON.stringify({ source_ids: sourceIds }) });
}
export async function deleteAuthorEntity(id: number): Promise<void> {
  return fetchAPI(`/metadata/authors/${id}`, { method: 'DELETE' });
}

export async function renameTag(id: number, name: string): Promise<TagDetail> {
  return fetchAPI(`/metadata/tags/${id}`, { method: 'PATCH', body: JSON.stringify({ name }) });
}
export async function mergeTags(targetId: number, sourceIds: number[]): Promise<TagDetail> {
  return fetchAPI(`/metadata/tags/${targetId}/merge`, { method: 'POST', body: JSON.stringify({ source_ids: sourceIds }) });
}
export async function deleteTagEntity(id: number): Promise<void> {
  return fetchAPI(`/metadata/tags/${id}`, { method: 'DELETE' });
}

export async function renameSeriesEntity(id: number, name: string, description?: string | null): Promise<SeriesDetail> {
  return fetchAPI(`/metadata/series/${id}`, { method: 'PATCH', body: JSON.stringify({ name, description }) });
}
export async function mergeSeriesEntities(targetId: number, sourceIds: number[]): Promise<SeriesDetail> {
  return fetchAPI(`/metadata/series/${targetId}/merge`, { method: 'POST', body: JSON.stringify({ source_ids: sourceIds }) });
}
export async function deleteSeriesEntity(id: number): Promise<void> {
  return fetchAPI(`/metadata/series/${id}`, { method: 'DELETE' });
}

// ── Publishers & Languages ────────────────────────────────────────────────────

export interface FieldValueDetail {
  value: string;
  edition_count: number;
}

export async function getPublishers(): Promise<FieldValueDetail[]> {
  return fetchAPI('/metadata/publishers');
}
export async function renamePublisher(oldValue: string, newValue: string): Promise<FieldValueDetail> {
  return fetchAPI('/metadata/publishers/rename', { method: 'POST', body: JSON.stringify({ old_value: oldValue, new_value: newValue }) });
}
export async function mergePublishers(sourceValues: string[], targetValue: string): Promise<FieldValueDetail> {
  return fetchAPI('/metadata/publishers/merge', { method: 'POST', body: JSON.stringify({ source_values: sourceValues, target_value: targetValue }) });
}

export async function getLanguages(): Promise<FieldValueDetail[]> {
  return fetchAPI('/metadata/languages');
}
export async function renameLanguage(oldValue: string, newValue: string): Promise<FieldValueDetail> {
  return fetchAPI('/metadata/languages/rename', { method: 'POST', body: JSON.stringify({ old_value: oldValue, new_value: newValue }) });
}
export async function mergeLanguages(sourceValues: string[], targetValue: string): Promise<FieldValueDetail> {
  return fetchAPI('/metadata/languages/merge', { method: 'POST', body: JSON.stringify({ source_values: sourceValues, target_value: targetValue }) });
}

// ── Esoteric Analysis Export ─────────────────────────────────────────────────

export function esotericExportUrl(bookId: number | string): string {
  const token = getAuthToken();
  return `${getApiBase()}/books/${bookId}/esoteric/export.epub?token=${encodeURIComponent(token || '')}`;
}

export async function exportEsotericToLibrary(bookId: number | string): Promise<Record<string, unknown>> {
  return fetchAPI(`/books/${bookId}/esoteric/export-to-library`, { method: 'POST' });
}

// ── Bulk Esoteric Analysis ───────────────────────────────────────────────────

export async function startBulkEsotericAnalysis(opts: {
  library_id?: number;
  run_computational?: boolean;
  run_llm?: boolean;
  llm_template_ids?: number[];
} = {}): Promise<Record<string, unknown>> {
  return fetchAPI('/admin/esoteric/bulk', {
    method: 'POST',
    body: JSON.stringify({
      library_id: opts.library_id,
      run_computational: opts.run_computational ?? true,
      run_llm: opts.run_llm ?? false,
      llm_template_ids: opts.llm_template_ids ?? [],
    }),
  });
}
export async function getActiveBulkEsotericJob(): Promise<Record<string, unknown> | null> {
  return fetchAPI('/admin/esoteric/bulk/active');
}
export async function getBulkEsotericJob(jobId: string): Promise<Record<string, unknown>> {
  return fetchAPI(`/admin/esoteric/bulk/${jobId}`);
}

// ── LLM Metadata Extraction ──────────────────────────────────────────────────

export async function startBulkLlmMetadata(libraryId?: number): Promise<{ job_id: string; total: number }> {
  const qs = libraryId ? `?library_id=${libraryId}` : '';
  return fetchAPI(`/admin/llm-metadata/bulk${qs}`, { method: 'POST' });
}
export async function getActiveBulkLlmMetadataJob(): Promise<Record<string, unknown> | null> {
  return fetchAPI('/admin/llm-metadata/bulk/active');
}
export async function getBulkLlmMetadataJob(jobId: string): Promise<Record<string, unknown>> {
  return fetchAPI(`/admin/llm-metadata/bulk/${jobId}`);
}

// ── Embedded Metadata Extraction ─────────────────────────────────────────────

export async function startBulkEmbeddedMetadata(libraryId?: number): Promise<{ job_id: string; total: number }> {
  const qs = libraryId ? `?library_id=${libraryId}` : '';
  return fetchAPI(`/admin/embedded-metadata/bulk${qs}`, { method: 'POST' });
}
export async function getActiveBulkEmbeddedMetadataJob(): Promise<Record<string, unknown> | null> {
  return fetchAPI('/admin/embedded-metadata/bulk/active');
}
export async function getBulkEmbeddedMetadataJob(jobId: string): Promise<Record<string, unknown>> {
  return fetchAPI(`/admin/embedded-metadata/bulk/${jobId}`);
}

// ── Shelves ───────────────────────────────────────────────────────────────────

export async function getShelves(): Promise<Shelf[]> {
  return fetchAPI('/shelves');
}

export async function getShelf(id: number | string): Promise<Shelf> {
  return fetchAPI(`/shelves/${id}`);
}

export async function createShelf(data: { name: string; description?: string | null; is_smart?: boolean; smart_filter?: string | null }): Promise<Shelf> {
  return fetchAPI('/shelves', { method: 'POST', body: JSON.stringify(data) });
}

export async function updateShelf(id: number | string, data: { name?: string; description?: string | null; is_smart?: boolean; smart_filter?: string | null }): Promise<Shelf> {
  return fetchAPI(`/shelves/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function deleteShelf(id: number | string): Promise<void> {
  return fetchAPI(`/shelves/${id}`, { method: 'DELETE' });
}

export async function addBookToShelf(shelfId: number | string, bookId: number): Promise<void> {
  return fetchAPI(`/shelves/${shelfId}/books`, { method: 'POST', body: JSON.stringify({ book_id: bookId }) });
}

export async function removeBookFromShelf(shelfId: number | string, bookId: number | string): Promise<void> {
  return fetchAPI(`/shelves/${shelfId}/books/${bookId}`, { method: 'DELETE' });
}

// ── Read Progress ─────────────────────────────────────────────────────────────

export async function getReadProgress(bookId: number | string): Promise<ReadProgress> {
  return fetchAPI(`/books/${bookId}/progress`);
}

export async function updateReadProgress(bookId: number | string, data: Partial<ReadProgress>): Promise<ReadProgress> {
  return fetchAPI(`/books/${bookId}/progress`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function setBookStatus(
  bookId: number | string,
  status: string,
  rating?: number | null,
): Promise<void> {
  return fetchAPI(`/books/${bookId}/progress`, {
    method: 'PATCH',
    body: JSON.stringify({ status, rating }),
  });
}

// ── Analysis ──────────────────────────────────────────────────────────────────

export interface AnalysisTemplate {
  id: number;
  name: string;
  description: string | null;
  system_prompt: string;
  user_prompt_template: string;
  is_default: boolean;
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
}

export interface BookAnalysis {
  id: number;
  book_id: number;
  template_id: number | null;
  title: string;
  content: string;
  esoteric_reading: string | null;
  model_used: string | null;
  token_count: number | null;
  status: 'pending' | 'running' | 'completed' | 'failed';
  error_message: string | null;
  created_at: string;
  template?: AnalysisTemplate;
}

export interface BookAnalysisSummary {
  id: number;
  book_id: number;
  title: string;
  status: string;
  model_used: string | null;
  created_at: string;
}

export async function getAnalysisTemplates(): Promise<AnalysisTemplate[]> {
  return fetchAPI('/analysis-templates');
}

export async function getBookAnalyses(bookId: number | string): Promise<BookAnalysisSummary[]> {
  return fetchAPI(`/books/${bookId}/analyses`);
}

export async function getBookAnalysis(bookId: number | string, analysisId: number | string): Promise<BookAnalysis> {
  return fetchAPI(`/books/${bookId}/analyses/${analysisId}`);
}

export async function createBookAnalysis(
  bookId: number | string,
  data: { template_id?: number; custom_prompt?: string; title?: string }
): Promise<BookAnalysisSummary> {
  return fetchAPI(`/books/${bookId}/analyses`, { method: 'POST', body: JSON.stringify(data) });
}

export async function deleteBookAnalysis(bookId: number | string, analysisId: number | string): Promise<void> {
  return fetchAPI(`/books/${bookId}/analyses/${analysisId}`, { method: 'DELETE' });
}

export async function setEsotericReading(bookId: number | string, analysisId: number | string, esotericReading: string | null): Promise<BookAnalysis> {
  return fetchAPI(`/books/${bookId}/analyses/${analysisId}/esoteric-reading`, {
    method: 'PATCH',
    body: JSON.stringify({ esoteric_reading: esotericReading }),
  });
}

export async function exportAnnotations(bookId: number | string, fmt: 'yaml' | 'json' = 'yaml'): Promise<string> {
  return fetchAPI(`/annotations/export?book_id=${bookId}&fmt=${fmt}`);
}

export async function computeReadingLevel(bookId: number | string): Promise<{ status: string; flesch_kincaid_grade?: number }> {
  return fetchAPI(`/books/${bookId}/compute-reading-level`, { method: 'POST' });
}

export async function updateReadingLevel(bookId: number | string, data: { lexile?: number; lexile_code?: string; ar_level?: number; ar_points?: number; age_range?: string; interest_level?: string }): Promise<{ ok: boolean }> {
  return fetchAPI(`/books/${bookId}/reading-level`, { method: 'PATCH', body: JSON.stringify(data) });
}

export interface SeriesNeighbor {
  id: number;
  title: string;
  position: number | null;
}

export interface SeriesNav {
  series_id: number;
  series_name: string;
  current_position: number | null;
  total: number;
  previous: SeriesNeighbor | null;
  next: SeriesNeighbor | null;
}

export async function getSeriesNeighbors(bookId: number | string): Promise<{ series: SeriesNav[] }> {
  return fetchAPI(`/books/${bookId}/series-neighbors`);
}

export function citationUrl(bookId: number | string, format: 'bibtex' | 'mla' | 'apa' = 'bibtex'): string {
  const token = getAuthToken();
  return `${getApiBase()}/export/books/${bookId}/citation?format=${format}${token ? `&token=${encodeURIComponent(token)}` : ''}`;
}

// ── Computational Analysis ────────────────────────────────────────────────────

export interface ComputationalAnalysis {
  id: number;
  book_id: number;
  analysis_type: string;
  results: Record<string, unknown>;
  config: Record<string, unknown> | null;
  status: string;
  created_at: string;
}

export interface ComputationalAnalysisRequest {
  analysis_type:
    | 'full'
    | 'loud_silence'
    | 'contradiction'
    | 'center'
    | 'exoteric_esoteric'
    | 'repetition_variation'
    | 'audience_differentiation'
    | 'hedging_language'
    | 'engine_v2'
    | 'self_reference'
    | 'section_proportion'
    | 'epigraph'
    | 'conditional_language'
    | 'emphasis_quotation'
    | 'first_last_words'
    | 'parenthetical_footnote'
    | 'structural_obscurity'
    | 'disreputable_mouthpiece';
  keywords?: string[];
  entities?: string[];
  pious_words?: string[];
  subversive_words?: string[];
  delimiter_pattern?: string;
}

export async function getComputationalAnalyses(bookId: number | string): Promise<ComputationalAnalysis[]> {
  return fetchAPI(`/books/${bookId}/esoteric`);
}

export async function runComputationalAnalysis(
  bookId: number | string,
  data: ComputationalAnalysisRequest
): Promise<ComputationalAnalysis> {
  return fetchAPI(`/books/${bookId}/esoteric`, { method: 'POST', body: JSON.stringify(data) });
}

export async function deleteComputationalAnalysis(bookId: number | string, analysisId: number | string): Promise<void> {
  return fetchAPI(`/books/${bookId}/esoteric/${analysisId}`, { method: 'DELETE' });
}

// ── Literary / Poetic Analysis ───────────────────────────────────────────────

export interface LiteraryAnalysis {
  id: number;
  book_id: number;
  analysis_type: string;
  results: Record<string, unknown>;
  config: Record<string, unknown> | null;
  status: string;
  created_at: string;
}

export interface LiteraryAnalysisRequest {
  analysis_type: 'literary_full_poetry' | 'literary_full_prose' | string;
  mode?: 'poetry' | 'prose';
}

export async function getLiteraryAnalyses(bookId: number | string): Promise<LiteraryAnalysis[]> {
  return fetchAPI(`/books/${bookId}/literary`);
}

export async function runLiteraryAnalysis(
  bookId: number | string,
  data: LiteraryAnalysisRequest
): Promise<LiteraryAnalysis> {
  return fetchAPI(`/books/${bookId}/literary`, { method: 'POST', body: JSON.stringify(data) });
}

export async function deleteLiteraryAnalysis(bookId: number | string, analysisId: number | string): Promise<void> {
  return fetchAPI(`/books/${bookId}/literary/${analysisId}`, { method: 'DELETE' });
}

// ── Esoteric enablement + per-book prompt configs ─────────────────────────────

export async function setEsotericEnabled(bookId: number | string, enabled: boolean): Promise<{ book_id: number; esoteric_enabled: boolean }> {
  return fetchAPI(`/books/${bookId}/esoteric-enabled`, { method: 'PATCH', body: JSON.stringify({ enabled }) });
}

export async function enableEsotericForAuthor(authorId: number, enabled: boolean): Promise<{ author_id: number; books_updated: number; esoteric_enabled: boolean }> {
  return fetchAPI(`/authors/${authorId}/enable-esoteric`, { method: 'POST', body: JSON.stringify({ enabled }) });
}

export interface PromptConfig {
  id: number;
  book_id: number;
  template_id: number | null;
  custom_system_prompt: string | null;
  custom_user_prompt: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  template_name: string | null;
}

export async function getBookPromptConfigs(bookId: number | string): Promise<PromptConfig[]> {
  return fetchAPI(`/books/${bookId}/prompt-configs`);
}

export async function upsertBookPromptConfig(
  bookId: number | string,
  data: { template_id?: number | null; custom_system_prompt?: string | null; custom_user_prompt?: string | null; notes?: string | null }
): Promise<PromptConfig> {
  return fetchAPI(`/books/${bookId}/prompt-configs`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function deleteBookPromptConfig(bookId: number | string, configId: number): Promise<void> {
  return fetchAPI(`/books/${bookId}/prompt-configs/${configId}`, { method: 'DELETE' });
}

export interface TextPreview {
  book_id: number;
  char_count: number;
  word_count: number;
  preview: string;
  truncated: boolean;
}

export async function getTextPreview(bookId: number | string): Promise<TextPreview> {
  return fetchAPI(`/books/${bookId}/text-preview`);
}

// ── Marginalia ────────────────────────────────────────────────────────────────

export async function getMarginalia(bookId: number | string, kind?: MarginaliumKind): Promise<Marginalium[]> {
  const params = new URLSearchParams({ book_id: String(bookId) });
  if (kind) params.set('kind', kind);
  return fetchAPI(`/marginalia?${params}`);
}

export async function getMyMarginalia(opts?: { kind?: MarginaliumKind; q?: string }): Promise<MarginaliumWithBook[]> {
  const params = new URLSearchParams();
  if (opts?.kind) params.set('kind', opts.kind);
  if (opts?.q) params.set('q', opts.q);
  const qs = params.toString();
  return fetchAPI(`/marginalia/mine${qs ? `?${qs}` : ''}`);
}

export async function createMarginalium(data: {
  book_id: number | string;
  file_id?: number | null;
  kind?: MarginaliumKind;
  reading_level?: ReadingLevel | null;
  content: string;
  location?: string | null;
  chapter?: string | null;
  related_refs?: string[] | null;
  tags?: string[] | null;
  commentator?: string | null;
  source?: string | null;
}): Promise<Marginalium> {
  return fetchAPI('/marginalia', { method: 'POST', body: JSON.stringify(data) });
}

export async function updateMarginalium(id: number, data: {
  kind?: MarginaliumKind;
  reading_level?: ReadingLevel | null;
  content?: string;
  location?: string | null;
  chapter?: string | null;
  related_refs?: string[] | null;
  tags?: string[] | null;
  commentator?: string | null;
  source?: string | null;
}): Promise<Marginalium> {
  return fetchAPI(`/marginalia/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function deleteMarginalium(id: number): Promise<void> {
  return fetchAPI(`/marginalia/${id}`, { method: 'DELETE' });
}

export interface MarginaliaStats {
  total: number;
  by_kind: Record<string, number>;
  top_tags: { tag: string; count: number }[];
  top_books: { book_id: number; book_title: string; count: number }[];
  top_commentators: { commentator: string; count: number }[];
}

export async function getMarginaliaStats(): Promise<MarginaliaStats> {
  return fetchAPI('/marginalia/stats');
}

export interface FiveKeysNote {
  id: number;
  kind: string;
  content: string;
  chapter?: string | null;
  location?: string | null;
  reading_level?: string | null;
  related_refs: string[];
  tags: string[];
  commentator?: string | null;
  source?: string | null;
}

export interface FiveKeysAnalysis {
  book_id: number;
  total: number;
  center: FiveKeysNote | null;
  contradictions: FiveKeysNote[];
  silent_chapters: string[];
  repetitions: FiveKeysNote[];
  boring: FiveKeysNote[];
  chapter_counts: Record<string, number>;
}

export async function getFiveKeys(bookId: number | string): Promise<FiveKeysAnalysis> {
  return fetchAPI(`/marginalia/books/${bookId}/five-keys`);
}

// ── Shelf Books ───────────────────────────────────────────────────────────────

export async function getBookShelves(bookId: number | string): Promise<Shelf[]> {
  return fetchAPI(`/books/${bookId}/shelves`);
}

export async function getShelfBooks(shelfId: number | string): Promise<Book[]> {
  return fetchAPI(`/shelves/${shelfId}/books`);
}

// ── Ingest ────────────────────────────────────────────────────────────────────

export interface IngestStatus {
  watching: boolean;
  queue_size: number;
  ingest_path: string;
}

export interface IngestHistoryResponse {
  items: IngestLog[];
  total: number;
  skip: number;
  limit: number;
}

export async function getIngestStatus(): Promise<IngestStatus> {
  return fetchAPI('/ingest/status');
}

export async function triggerIngest(): Promise<{ status: string; message: string }> {
  return fetchAPI('/ingest/trigger', { method: 'POST' });
}

export async function getIngestHistory(skip = 0, limit = 50): Promise<IngestHistoryResponse> {
  return fetchAPI(`/ingest/history?skip=${skip}&limit=${limit}`);
}

// ── Kobo Sync ─────────────────────────────────────────────────────────────────

export interface KoboTokenShelf {
  id: number;
  name: string;
}

export interface KoboSyncToken {
  id: number;
  token: string;
  sync_url: string;
  is_active: boolean;
  created_at: string;
  last_used: string | null;
  shelves: KoboTokenShelf[];
}

export async function getKoboTokens(): Promise<KoboSyncToken[]> {
  return fetchAPI('/kobo/tokens');
}

export async function createKoboToken(deviceName?: string, shelfIds?: number[]): Promise<KoboSyncToken> {
  return fetchAPI('/kobo/tokens', {
    method: 'POST',
    body: JSON.stringify({ device_name: deviceName ?? 'Kobo eReader', shelf_ids: shelfIds ?? [] }),
  });
}

export async function setKoboTokenShelves(tokenId: number, shelfIds: number[]): Promise<void> {
  return fetchAPI(`/kobo/tokens/${tokenId}/shelves`, {
    method: 'PUT',
    body: JSON.stringify(shelfIds),
  });
}

export async function deleteKoboToken(id: number): Promise<void> {
  return fetchAPI(`/kobo/tokens/${id}`, { method: 'DELETE' });
}

// ── Reader ────────────────────────────────────────────────────────────────────

export function bookFileUrl(bookId: number | string, fileId: number | string): string {
  const token = getAuthToken();
  const base = `${getApiBase()}/books/${bookId}/download/${fileId}`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

export function comicPageUrl(bookId: number | string, fileId: number | string, page: number): string {
  return `${getApiBase()}/books/${bookId}/files/${fileId}/pages/${page}`;
}

export async function getComicPageCount(bookId: number | string, fileId: number | string): Promise<{ count: number }> {
  return fetchAPI(`/books/${bookId}/files/${fileId}/pages`);
}

export async function saveReadProgress(
  bookId: number | string,
  data: {
    current_page?: number;
    total_pages?: number;
    percentage: number;
    status?: string;
    file_id?: number;
    format?: string;
    cfi?: string;
    /** Seconds elapsed since the last save in this session. */
    time_spent_delta_seconds?: number;
  }
): Promise<ReadProgress> {
  return fetchAPI(`/books/${bookId}/progress`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function getBookProgress(bookId: number | string): Promise<ReadProgress | null> {
  return fetchAPI(`/books/${bookId}/progress`);
}

export async function resetFurthestPosition(
  bookId: number | string,
): Promise<{ ok: boolean; furthest_pct: number }> {
  return fetchAPI(`/books/${bookId}/progress/reset-furthest`, { method: 'POST' });
}

export async function sendBookToDevice(
  bookId: number | string,
  recipient: string,
  fileId?: number,
): Promise<{ ok: boolean; recipient: string; filename: string }> {
  return fetchAPI(`/books/${bookId}/send`, {
    method: 'POST',
    body: JSON.stringify({ recipient, file_id: fileId }),
  });
}

// ── Stats ─────────────────────────────────────────────────────────────────────

export interface ReadingStats {
  total_books: number;
  books_reading: number;
  books_completed: number;
  books_abandoned: number;
  pages_read: number;
  time_reading_seconds: number;
  sessions_this_year: number;
  currently_reading: Array<{ id: number; title: string; author: string | null; percentage: number; last_opened: string | null }>;
  recently_completed: Array<{ id: number; title: string; author: string | null; completed_at: string | null; rating: number | null }>;
  recent_sessions: Array<{ id: number; book_id: number; title: string; author: string | null; started_at: string; finished_at: string | null; rating: number | null; notes: string | null }>;
  // Booklore-style enrichments
  completions_by_month: Array<{ month: string; count: number }>;
  activity_by_day: Array<{ date: string; count: number }>;
  current_streak: number;
  longest_streak: number;
  avg_rating: number | null;
  rating_distribution: Record<string, number>;
  // BookLore-inspired analytics
  peak_hours: Array<{ hour: number; count: number }>;
  day_of_week: Array<{ day: string; count: number }>;
  reading_speed: { pages_per_hour: number; books_sampled: number } | null;
  time_by_month: Array<{ month: string; seconds: number }>;
  top_genres: Array<{ tag: string; count: number }>;
}

export async function getReadingStats(): Promise<ReadingStats> {
  return fetchAPI('/stats');
}

// ── Notebooks ─────────────────────────────────────────────────────────────────

export interface Notebook {
  id: number;
  user_id: number;
  name: string;
  description?: string | null;
  entry_count: number;
  created_at: string;
  updated_at: string;
}

export interface NotebookEntry {
  id: number;
  notebook_id: number;
  marginalium_id: number;
  note?: string | null;
  created_at: string;
  kind: string;
  content: string;
  chapter?: string | null;
  location?: string | null;
  reading_level?: string | null;
  book_id: number;
  book_title?: string | null;
}

export async function getNotebooks(): Promise<Notebook[]> {
  return fetchAPI('/notebooks');
}

export async function createNotebook(data: { name: string; description?: string | null }): Promise<Notebook> {
  return fetchAPI('/notebooks', { method: 'POST', body: JSON.stringify(data) });
}

export async function updateNotebook(id: number, data: { name?: string; description?: string | null }): Promise<Notebook> {
  return fetchAPI(`/notebooks/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function deleteNotebook(id: number): Promise<void> {
  return fetchAPI(`/notebooks/${id}`, { method: 'DELETE' });
}

export async function getNotebookEntries(notebookId: number): Promise<NotebookEntry[]> {
  return fetchAPI(`/notebooks/${notebookId}/entries`);
}

export async function addNotebookEntry(notebookId: number, data: { marginalium_id: number; note?: string | null }): Promise<NotebookEntry> {
  return fetchAPI(`/notebooks/${notebookId}/entries`, { method: 'POST', body: JSON.stringify(data) });
}

export async function removeNotebookEntry(notebookId: number, entryId: number): Promise<void> {
  return fetchAPI(`/notebooks/${notebookId}/entries/${entryId}`, { method: 'DELETE' });
}

// ── Recommendations ───────────────────────────────────────────────────────────

export interface BookRecommendation {
  id: number;
  title: string;
  author?: string | null;
  cover_hash?: string | null;
  cover_format?: string | null;
  score: number;
  reasons: string[];
}

export async function getBookRecommendations(bookId: number | string): Promise<BookRecommendation[]> {
  return fetchAPI(`/books/${bookId}/recommendations`);
}

// ── Admin ─────────────────────────────────────────────────────────────────────

export interface AdminConfig {
  oidc_enabled: boolean;
  oidc_configured: boolean;
  oidc_discovery_url: string | null;
  smtp_configured: boolean;
  smtp_host: string | null;
  smtp_port: number;
  smtp_user: string | null;
  smtp_from: string | null;
  smtp_tls: boolean;
  ingest_auto_convert: boolean;
  ingest_target_format: string;
  ingest_auto_enrich: boolean;
  ingest_default_provider: string;
  llm_provider: string;
  llm_configured: boolean;
  calibre_path: string;
  library_path: string;
  ingest_path: string;
  loose_leaves_path: string;
  hardcover_configured: boolean;
  comicvine_configured: boolean;
  google_books_configured: boolean;
  isbndb_configured: boolean;
  amazon_configured: boolean;
  librarything_configured: boolean;
  naming_enabled: boolean;
  naming_pattern: string;
  abs_configured: boolean;
  abs_url: string | null;
}

// ── Reading Goals ─────────────────────────────────────────────────────────────

export interface ReadingGoal {
  year: number;
  target_books: number;
  books_completed: number;
  pct: number;
}

export async function getReadingGoal(year: number): Promise<ReadingGoal> {
  return fetchAPI(`/goals/${year}`);
}

export async function setReadingGoal(year: number, target_books: number): Promise<ReadingGoal> {
  return fetchAPI(`/goals/${year}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_books }),
  });
}

export async function deleteReadingGoal(year: number): Promise<void> {
  await fetchAPI(`/goals/${year}`, { method: 'DELETE' });
}

// ── Loose Leaves ──────────────────────────────────────────────────────────────────

export interface DropItem {
  filename: string;
  size_bytes: number;
  format: string;
  guessed_title: string;
}

export interface DropPreview {
  filename: string;
  title?: string | null;
  authors: string[];
  description?: string | null;
  tags: string[];
  published_date?: string | null;
  language?: string | null;
  isbn?: string | null;
  cover_url?: string | null;
}

export async function getLooseLeavesPending(): Promise<DropItem[]> {
  return fetchAPI('/loose-leaves/pending');
}

export async function previewLooseLeaf(filename: string): Promise<DropPreview> {
  return fetchAPI(`/loose-leaves/preview?filename=${encodeURIComponent(filename)}`);
}

export async function importFromLooseLeaves(filename: string, libraryId: number): Promise<{ status: string; book_id?: number; message: string }> {
  return fetchAPI('/loose-leaves/import', { method: 'POST', body: JSON.stringify({ filename, library_id: libraryId }) });
}

export async function rejectFromLooseLeaves(filename: string): Promise<void> {
  return fetchAPI('/loose-leaves/reject', { method: 'DELETE', body: JSON.stringify({ filename }) });
}

export async function bulkImportFromLooseLeaves(
  files: Array<{ filename: string; library_id?: number | null }>,
  defaultLibraryId: number,
): Promise<{ total: number; imported: number; results: Array<{ filename: string; status: string; book_id?: number; library?: string }> }> {
  return fetchAPI('/loose-leaves/bulk-import', {
    method: 'POST',
    body: JSON.stringify({ files, default_library_id: defaultLibraryId }),
  });
}

export async function uploadToLooseLeaves(files: File[]): Promise<DropItem[]> {
  const form = new FormData();
  for (const f of files) form.append('files', f, f.name);
  const url = `${getApiBase()}/loose-leaves/upload`;
  const token = getAuthToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(url, { method: 'POST', headers, body: form });
  if (!res.ok) throw new Error(`Upload failed (${res.status}): ${await res.text()}`);
  return res.json();
}

export async function getAdminConfig(): Promise<AdminConfig> {
  return fetchAPI('/admin/config');
}

export async function updateNamingSettings(namingEnabled: boolean, namingPattern: string): Promise<{ naming_enabled: boolean; naming_pattern: string }> {
  return fetchAPI('/admin/naming', {
    method: 'PUT',
    body: JSON.stringify({ naming_enabled: namingEnabled, naming_pattern: namingPattern }),
  });
}

export interface EnrichmentKeysUpdate {
  hardcover_api_key?: string;
  comicvine_api_key?: string;
  google_books_api_key?: string;
  isbndb_api_key?: string;
  amazon_cookie?: string;
}

export async function updateEnrichmentKeys(keys: EnrichmentKeysUpdate): Promise<Record<string, boolean>> {
  return fetchAPI('/admin/enrichment', {
    method: 'PUT',
    body: JSON.stringify(keys),
  });
}

// ── Bulk Enrichment ────────────────────────────────────────────────────────────

export interface BulkEnrichOptions {
  library_id?: number | null;
  missing_cover?: boolean;
  missing_description?: boolean;
  missing_authors?: boolean;
  force?: boolean;
  provider?: string | null;
}

export interface BulkEnrichJob {
  job_id: string;
  status: 'queued' | 'running' | 'done' | 'cancelled' | 'error';
  total: number;
  done: number;
  failed: number;
  current: string;
  started_at: string;
  error: string | null;
}

export async function startBulkEnrich(opts: BulkEnrichOptions): Promise<{ job_id: string; total: number }> {
  return fetchAPI('/admin/enrich/bulk', { method: 'POST', body: JSON.stringify(opts) });
}

export async function getBulkEnrichJob(jobId: string): Promise<BulkEnrichJob> {
  return fetchAPI(`/admin/enrich/bulk/${jobId}`);
}

export async function getActiveBulkEnrichJob(): Promise<BulkEnrichJob | null> {
  return fetchAPI('/admin/enrich/bulk/active');
}

export async function cancelBulkEnrichJob(jobId: string): Promise<void> {
  await fetchAPI(`/admin/enrich/bulk/${jobId}`, { method: 'DELETE' });
}

// ── Bulk Markdown Generation ──────────────────────────────────────────────────

export async function startBulkMarkdown(libraryId?: number): Promise<{ job_id: string; total: number }> {
  const qs = libraryId ? `?library_id=${libraryId}` : '';
  return fetchAPI(`/admin/markdown/bulk${qs}`, { method: 'POST' });
}

export async function getBulkMarkdownJob(jobId: string): Promise<{ job_id: string; status: string; total: number; done: number; failed: number; skipped: number; current: string }> {
  return fetchAPI(`/admin/markdown/bulk/${jobId}`);
}

export async function getActiveBulkMarkdownJob(): Promise<{ job_id: string; status: string; total: number; done: number; failed: number; skipped: number; current: string } | null> {
  return fetchAPI('/admin/markdown/bulk/active');
}

export async function generateMarkdown(editionId: number, force = false): Promise<{ edition_id: number; status: string; length: number }> {
  const qs = force ? '?force=true' : '';
  return fetchAPI(`/admin/markdown/generate/${editionId}${qs}`, { method: 'POST' });
}

export async function startBatchMarkdown(editionIds: number[], force = false): Promise<{ job_id: string; total: number }> {
  return fetchAPI('/admin/markdown/batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ edition_ids: editionIds, force }),
  });
}

export async function replaceEditionFile(editionId: number, fileId: number, file: File): Promise<{ file_id: number; edition_id: number; file_hash: string; file_size: number; status: string }> {
  const form = new FormData();
  form.append('file', file);
  return fetchAPI(`/editions/${editionId}/files/${fileId}/replace`, {
    method: 'PUT',
    body: form,
  });
}

export async function rehashEditionFile(editionId: number, fileId: number, clearCaches = true): Promise<{ file_id: number; edition_id: number; old_hash: string; new_hash: string; file_size: number; changed: boolean }> {
  return fetchAPI(`/editions/${editionId}/files/${fileId}/rehash?clear_caches=${clearCaches}`, { method: 'POST' });
}

export async function updateLibraryNaming(libraryId: number, namingPattern: string | null): Promise<Library> {
  return fetchAPI(`/libraries/${libraryId}`, {
    method: 'PUT',
    body: JSON.stringify({ naming_pattern: namingPattern }),
  });
}

// ── Bulk Identifier Extraction ────────────────────────────────────────────────

export async function startBulkIdentifiers(libraryId?: number): Promise<{ job_id: string; total: number }> {
  const qs = libraryId ? `?library_id=${libraryId}` : '';
  return fetchAPI(`/admin/identifiers/bulk${qs}`, { method: 'POST' });
}

export async function getBulkIdentifiersJob(jobId: string): Promise<{ job_id: string; status: string; total: number; done: number; found_isbn: number; found_doi: number; failed: number }> {
  return fetchAPI(`/admin/identifiers/bulk/${jobId}`);
}

export async function getActiveBulkIdentifiersJob(): Promise<{ job_id: string; status: string; total: number; done: number; found_isbn: number; found_doi: number; failed: number } | null> {
  return fetchAPI('/admin/identifiers/bulk/active');
}

export async function extractBookIdentifiers(bookId: number | string): Promise<{ isbn_13: string | null; isbn_10: string | null; doi: string | null; isbn_source: string | null; doi_source: string | null }> {
  return fetchAPI(`/books/${bookId}/extract-identifiers`, { method: 'POST' });
}

export async function startBatchIdentifiers(editionIds: number[]): Promise<{ job_id: string; total: number }> {
  return fetchAPI('/admin/identifiers/batch', { method: 'POST', body: JSON.stringify({ edition_ids: editionIds }) });
}

// ── Cover Quality & Upgrade ──────────────────────────────────────────────────

export async function getLowQualityCovers(libraryId?: number): Promise<any[]> {
  const qs = libraryId ? `?library_id=${libraryId}` : '';
  return fetchAPI(`/admin/covers/low-quality${qs}`);
}

export async function startCoverUpgrade(libraryId?: number): Promise<{ job_id: string; total: number }> {
  const qs = libraryId ? `?library_id=${libraryId}` : '';
  return fetchAPI(`/admin/covers/upgrade${qs}`, { method: 'POST' });
}

export async function getCoverUpgradeJob(jobId: string): Promise<{ job_id: string; status: string; total: number; done: number; upgraded: number; no_match: number; failed: number; current: string }> {
  return fetchAPI(`/admin/covers/upgrade/${jobId}`);
}

// ── Bulk Cover Fetch (missing covers) ────────────────────────────────────────

export async function startCoverFetch(libraryId?: number): Promise<{ job_id: string; total: number }> {
  const qs = libraryId ? `?library_id=${libraryId}` : '';
  return fetchAPI(`/admin/covers/fetch${qs}`, { method: 'POST' });
}

export async function getCoverFetchJob(jobId: string): Promise<{ job_id: string; status: string; total: number; done: number; found: number; not_found: number; failed: number; current: string }> {
  return fetchAPI(`/admin/covers/fetch/${jobId}`);
}

// ── Filename Metadata Extraction ─────────────────────────────────────────────

export async function startFilenameExtract(libraryId?: number, minConfidence: string = 'medium'): Promise<{ job_id: string; total: number }> {
  const params = new URLSearchParams();
  if (libraryId) params.set('library_id', String(libraryId));
  params.set('min_confidence', minConfidence);
  return fetchAPI(`/admin/filename-extract/bulk?${params}`, { method: 'POST' });
}

export async function getFilenameExtractJob(jobId: string): Promise<{ job_id: string; status: string; total: number; done: number; applied: number; skipped: number; failed: number }> {
  return fetchAPI(`/admin/filename-extract/bulk/${jobId}`);
}

// ── Bulk Metadata Editing ────────────────────────────────────────────────────

export async function bulkEditBooks(editionIds: number[], updates: {
  author_names?: string[];
  tag_names?: string[];
  series_names?: string[];
  publisher?: string;
  language?: string;
  merge_authors?: boolean;
  merge_tags?: boolean;
  merge_series?: boolean;
}): Promise<{ updated: number; failed: number }> {
  return fetchAPI('/books/bulk-edit', {
    method: 'PUT',
    body: JSON.stringify({ edition_ids: editionIds, ...updates }),
  });
}

// ── Bulk Shelf Assignment ────────────────────────────────────────────────────

export async function bulkShelfAssignment(bookIds: number[], shelvesToAssign: number[], shelvesToUnassign: number[] = []): Promise<{ assigned: number; unassigned: number }> {
  return fetchAPI('/shelves/bulk', {
    method: 'POST',
    body: JSON.stringify({ book_ids: bookIds, shelves_to_assign: shelvesToAssign, shelves_to_unassign: shelvesToUnassign }),
  });
}

// ── Articles / Instapaper ─────────────────────────────────────────────────────

export interface ArticleItem {
  id: number;
  user_id: number;
  instapaper_id?: number | null;
  url: string;
  title: string;
  author?: string | null;
  description?: string | null;
  domain?: string | null;
  word_count?: number | null;
  progress: number;
  is_starred: boolean;
  is_archived: boolean;
  folder?: string | null;
  saved_at: string;
  highlight_count: number;
}

export interface ArticleDetail extends ArticleItem {
  markdown_content?: string | null;
  highlights: { id: number; text: string; note?: string | null; position?: number | null }[];
}

export async function getArticles(opts?: { archived?: boolean; starred?: boolean; skip?: number; limit?: number }): Promise<ArticleItem[]> {
  const params = new URLSearchParams();
  if (opts?.archived) params.set('archived', 'true');
  if (opts?.starred) params.set('starred', 'true');
  if (opts?.skip) params.set('skip', String(opts.skip));
  if (opts?.limit) params.set('limit', String(opts.limit));
  return fetchAPI(`/articles?${params}`);
}

export async function getArticle(id: number): Promise<ArticleDetail> {
  return fetchAPI(`/articles/${id}`);
}

export async function saveArticle(url: string, title?: string, description?: string): Promise<ArticleItem> {
  return fetchAPI('/articles', { method: 'POST', body: JSON.stringify({ url, title, description }) });
}

export async function deleteArticle(id: number): Promise<void> {
  return fetchAPI(`/articles/${id}`, { method: 'DELETE' });
}

export async function starArticle(id: number): Promise<{ starred: boolean }> {
  return fetchAPI(`/articles/${id}/star`, { method: 'POST' });
}

export async function archiveArticle(id: number): Promise<{ archived: boolean }> {
  return fetchAPI(`/articles/${id}/archive`, { method: 'POST' });
}

export async function syncInstapaper(): Promise<{ created: number; updated: number; highlights: number }> {
  return fetchAPI('/articles/sync', { method: 'POST' });
}

export async function getInstapaperStatus(): Promise<{ linked: boolean; instapaper_username?: string | null; has_full_api: boolean }> {
  return fetchAPI('/articles/instapaper/status');
}

export async function linkInstapaper(username: string, password: string): Promise<{ linked: boolean }> {
  return fetchAPI('/articles/instapaper/link', { method: 'POST', body: JSON.stringify({ username, password }) });
}

export async function unlinkInstapaper(): Promise<void> {
  return fetchAPI('/articles/instapaper/link', { method: 'DELETE' });
}

// ── Locations ─────────────────────────────────────────────────────────────────

export interface LocationItem {
  id: number;
  name: string;
  description?: string | null;
  parent_id?: number | null;
  tree_path: string;
}

export interface LocationTreeNode {
  id: number;
  name: string;
  description?: string | null;
  children: LocationTreeNode[];
}

export async function getLocations(): Promise<LocationItem[]> {
  return fetchAPI('/locations');
}

export async function getLocationTree(): Promise<LocationTreeNode[]> {
  return fetchAPI('/locations/tree');
}

export async function createLocation(data: { name: string; description?: string; parent_id?: number }): Promise<LocationItem> {
  return fetchAPI('/locations', { method: 'POST', body: JSON.stringify(data) });
}

export async function updateLocation(id: number, data: { name?: string; description?: string; parent_id?: number | null }): Promise<LocationItem> {
  return fetchAPI(`/locations/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function deleteLocation(id: number): Promise<void> {
  return fetchAPI(`/locations/${id}`, { method: 'DELETE' });
}

// ── AudiobookShelf ─────────────────────────────────────────────────────────────

export interface AbsStatus {
  configured: boolean;
  connected: boolean;
  server_url?: string;
  abs_user?: string;
  abs_user_type?: string;
  error?: string;
}

export interface AbsLibrary {
  id: string;
  name: string;
  media_type: string;
  icon: string | null;
}

export interface AbsSyncResult {
  items_from_abs: number;
  matched: number;
  updated: number;
  skipped_unlinked: number;
}

export interface AbsImportResult {
  total_abs_items: number;
  created: number;
  linked: number;
  skipped_already_linked: number;
}

export async function getAbsStatus(): Promise<AbsStatus> {
  return fetchAPI('/audiobookshelf/status');
}

export async function getAbsLibraries(): Promise<AbsLibrary[]> {
  return fetchAPI('/audiobookshelf/libraries');
}

export async function syncAbsProgress(): Promise<AbsSyncResult> {
  return fetchAPI('/audiobookshelf/sync-progress', { method: 'POST' });
}

export async function syncAbsCovers(overwrite = false): Promise<{ job_id: string; total: number }> {
  return fetchAPI(`/audiobookshelf/sync-covers?overwrite=${overwrite}`, { method: 'POST' });
}

export async function getAbsCoverSyncJob(jobId: string): Promise<{ job_id: string; status: string; total: number; done: number; failed: number }> {
  return fetchAPI(`/audiobookshelf/sync-covers/${jobId}`);
}

export async function importFromAbs(absLibraryId: string, scriptoriumLibraryId: number, limit = 0): Promise<AbsImportResult> {
  return fetchAPI('/audiobookshelf/import', {
    method: 'POST',
    body: JSON.stringify({ abs_library_id: absLibraryId, scriptorium_library_id: scriptoriumLibraryId, limit }),
  });
}

export async function linkBookToAbs(bookId: number, absItemId: string): Promise<{ book_id: number; abs_item_id: string }> {
  return fetchAPI('/audiobookshelf/link', {
    method: 'POST',
    body: JSON.stringify({ book_id: bookId, abs_item_id: absItemId }),
  });
}

export async function unlinkBookFromAbs(bookId: number): Promise<void> {
  return fetchAPI(`/audiobookshelf/link/${bookId}`, { method: 'DELETE' });
}

export async function rebuildSearchIndex(): Promise<{ indexed: number }> {
  return fetchAPI('/search/rebuild-index', { method: 'POST' });
}

export function adminBackupUrl(): string {
  const token = getAuthToken();
  const base = `${getApiBase()}/admin/backup`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

// ── API Keys ──────────────────────────────────────────────────────────────────

import type { ApiKey, ApiKeyCreated, Collection, CollectionDetail, Annotation, ReadSession } from '$lib/types/index';

export async function getApiKeys(): Promise<ApiKey[]> {
  return fetchAPI('/api-keys');
}

export async function createApiKey(name: string): Promise<ApiKeyCreated> {
  return fetchAPI('/api-keys', { method: 'POST', body: JSON.stringify({ name }) });
}

export async function revokeApiKey(id: number): Promise<void> {
  return fetchAPI(`/api-keys/${id}`, { method: 'DELETE' });
}

// ── Collections ───────────────────────────────────────────────────────────────

export async function getCollections(): Promise<Collection[]> {
  return fetchAPI('/collections');
}

export async function createCollection(data: { name: string; description?: string | null; cover_book_id?: number | null; is_smart?: boolean; smart_filter?: import('$lib/types/index').SmartFilter | null }): Promise<Collection> {
  return fetchAPI('/collections', { method: 'POST', body: JSON.stringify(data) });
}

export async function getCollection(id: number): Promise<CollectionDetail> {
  return fetchAPI(`/collections/${id}`);
}

export async function updateCollection(id: number, data: { name?: string; description?: string | null; cover_book_id?: number | null; is_smart?: boolean; smart_filter?: import('$lib/types/index').SmartFilter | null }): Promise<Collection> {
  return fetchAPI(`/collections/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function deleteCollection(id: number): Promise<void> {
  return fetchAPI(`/collections/${id}`, { method: 'DELETE' });
}

export async function addBookToCollection(collectionId: number, bookId: number): Promise<void> {
  return fetchAPI(`/collections/${collectionId}/books`, { method: 'POST', body: JSON.stringify({ book_id: bookId }) });
}

export async function removeBookFromCollection(collectionId: number, bookId: number): Promise<void> {
  return fetchAPI(`/collections/${collectionId}/books/${bookId}`, { method: 'DELETE' });
}

// ── Duplicates ────────────────────────────────────────────────────────────────

export async function findIsbnDuplicates(): Promise<import('$lib/types/index').Book[][]> {
  return fetchAPI('/duplicates/isbn');
}

export async function findTitleAuthorDuplicates(): Promise<import('$lib/types/index').Book[][]> {
  return fetchAPI('/duplicates/title-author');
}

export async function consolidateDuplicates(primaryId: number, sourceIds: number[]): Promise<import('$lib/types/index').Book> {
  return fetchAPI('/duplicates/consolidate', { method: 'POST', body: JSON.stringify({ primary_id: primaryId, source_ids: sourceIds }) });
}

// ── Devices ───────────────────────────────────────────────────────────────────

export interface Device {
  id: number;
  name: string;
  device_type: string;
  device_model: string | null;
  last_synced: string | null;
  created_at: string;
}

export async function getDevices(): Promise<Device[]> {
  return fetchAPI('/devices');
}

export async function deleteDevice(id: number): Promise<void> {
  return fetchAPI(`/devices/${id}`, { method: 'DELETE' });
}

// ── Cover from URL ────────────────────────────────────────────────────────────

export async function searchCovers(bookId: number | string): Promise<Array<{ provider: string; url: string }>> {
  return fetchAPI(`/books/${bookId}/cover/search`);
}

export async function setCoverFromUrl(bookId: number, url: string): Promise<import('$lib/types/index').Book> {
  return fetchAPI(`/books/${bookId}/cover/from-url`, { method: 'POST', body: JSON.stringify({ url }) });
}

// ── Locked Fields ─────────────────────────────────────────────────────────────

export async function setLockedFields(bookId: number, lockedFields: string[]): Promise<{ locked_fields: string[] }> {
  return fetchAPI(`/books/${bookId}/locked-fields`, { method: 'PATCH', body: JSON.stringify({ locked_fields: lockedFields }) });
}

// ── Annotations ───────────────────────────────────────────────────────────────

export async function getAnnotations(bookId: number, type?: string): Promise<Annotation[]> {
  const params = new URLSearchParams({ book_id: String(bookId) });
  if (type) params.set('type', type);
  return fetchAPI(`/annotations?${params}`);
}

export async function createAnnotation(data: {
  book_id: number; file_id?: number | null; type: string;
  content?: string | null; location?: string | null;
  chapter?: string | null; color?: string | null;
}): Promise<Annotation> {
  return fetchAPI('/annotations', { method: 'POST', body: JSON.stringify(data) });
}

export async function updateAnnotation(id: number, data: { content?: string | null; color?: string | null; chapter?: string | null }): Promise<Annotation> {
  return fetchAPI(`/annotations/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function deleteAnnotation(id: number): Promise<void> {
  return fetchAPI(`/annotations/${id}`, { method: 'DELETE' });
}

export interface AnnotationWithBook extends Annotation {
  book_title: string | null;
  book_author: string | null;
}

export async function getMyAnnotations(type?: string, q?: string): Promise<AnnotationWithBook[]> {
  const params = new URLSearchParams();
  if (type) params.set('type', type);
  if (q) params.set('q', q);
  const qs = params.toString();
  return fetchAPI(`/annotations/mine${qs ? `?${qs}` : ''}`);
}

// ── Read Sessions ─────────────────────────────────────────────────────────────

export async function getReadSessions(bookId?: number): Promise<ReadSession[]> {
  const params = bookId !== undefined ? `?book_id=${bookId}` : '';
  return fetchAPI(`/read-sessions${params}`);
}

export async function createReadSession(data: {
  book_id: number; started_at: string; finished_at?: string | null;
  rating?: number | null; notes?: string | null;
}): Promise<ReadSession> {
  return fetchAPI('/read-sessions', { method: 'POST', body: JSON.stringify(data) });
}

export async function updateReadSession(id: number, data: {
  started_at?: string; finished_at?: string | null;
  rating?: number | null; notes?: string | null;
}): Promise<ReadSession> {
  return fetchAPI(`/read-sessions/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function deleteReadSession(id: number): Promise<void> {
  return fetchAPI(`/read-sessions/${id}`, { method: 'DELETE' });
}

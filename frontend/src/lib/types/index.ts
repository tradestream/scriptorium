// ── Auth ──────────────────────────────────────────────────────────────────────

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

// ── Users ─────────────────────────────────────────────────────────────────────

export interface User {
  id: number;
  username: string;
  display_name?: string | null;
  email: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// ── Libraries ─────────────────────────────────────────────────────────────────

export interface LibraryAccess {
  id: number;
  library_id: number;
  user_id: number;
  access_level: 'read' | 'write';
  granted_at: string;
}

export interface Library {
  id: number;
  name: string;
  description?: string | null;
  path: string;
  is_active: boolean;
  is_hidden: boolean;
  sort_order?: number;
  last_scanned?: string | null;
  created_at: string;
  updated_at: string;
  book_count?: number;
  naming_pattern?: string | null;
}

// ── Works & Editions ──────────────────────────────────────────────────────────

export interface WorkAward {
  name: string;
  year?: number | null;
  category?: string | null;
}

export interface Work {
  id: number;
  uuid: string;
  title: string;
  subtitle?: string | null;
  description?: string | null;
  language?: string | null;
  original_language?: string | null;
  original_publication_year?: number | null;
  characters: string[];
  places: string[];
  awards: WorkAward[];
  esoteric_enabled: boolean;
  locked_fields?: string[];
  created_at: string;
  updated_at: string;
  authors: Author[];
  tags: Tag[];
  series: Series[];
  editors: string[];
  illustrators: string[];
  colorists: string[];
  edition_count: number;
}

export interface WorkListResponse {
  items: Work[];
  total: number;
  skip: number;
  limit: number;
}

export interface EditionFile {
  id: number;
  filename: string;
  format: string;
  file_size: number;
  created_at: string;
}

export interface Edition {
  id: number;
  uuid: string;
  work_id: number;
  library_id: number;
  isbn?: string | null;
  publisher?: string | null;
  published_date?: string | null;
  language?: string | null;
  format?: string | null;
  page_count?: number | null;
  cover_hash?: string | null;
  cover_format?: string | null;
  abs_item_id?: string | null;
  doi?: string | null;
  physical_copy: boolean;
  locked_fields?: string[];
  translators: string[];
  created_at: string;
  updated_at: string;
  files: EditionFile[];
  work?: Work | null;
}

export interface UserEdition {
  id: number;
  user_id: number;
  edition_id: number;
  status: 'want_to_read' | 'reading' | 'completed' | 'abandoned';
  current_page: number;
  total_pages?: number | null;
  percentage: number;
  rating?: number | null;
  review?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  last_opened?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Loan {
  id: number;
  edition_id: number;
  loaned_to_user_id?: number | null;
  loaned_to_name?: string | null;
  loaned_at: string;
  due_back?: string | null;
  returned_at?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

// ── Books (legacy — kept until migration 0034) ────────────────────────────────

export interface Author {
  id: number;
  name: string;
  description?: string | null;
  photo_url?: string | null;
}

export interface Tag {
  id: number;
  name: string;
}

export interface Series {
  id: number;
  name: string;
  description?: string | null;
}

export interface BookFile {
  id: number;
  filename: string;
  format: string;
  file_size: number;
  created_at: string;
}

export interface Book {
  id: number;
  uuid: string;
  title: string;
  subtitle?: string | null;
  description?: string | null;
  isbn?: string | null;
  isbn_10?: string | null;
  asin?: string | null;
  language?: string | null;
  published_date?: string | null;
  publisher?: string | null;
  cover_hash?: string | null;
  cover_format?: string | null;
  cover_color?: string | null;
  locked_fields?: string[];
  esoteric_enabled?: boolean;
  physical_copy?: boolean;
  binding?: string | null;
  condition?: string | null;
  purchase_price?: number | null;
  purchase_date?: string | null;
  purchase_from?: string | null;
  location?: string | null;
  location_id?: number | null;
  location_name?: string | null;
  abs_item_id?: string | null;
  doi?: string | null;
  lexile?: number | null;
  lexile_code?: string | null;
  ar_level?: number | null;
  ar_points?: number | null;
  flesch_kincaid_grade?: number | null;
  age_range?: string | null;
  interest_level?: string | null;
  library_id: number;
  created_at: string;
  updated_at: string;
  authors: Author[];
  tags: Tag[];
  series: Series[];
  files: BookFile[];
  translators: string[];
  editors: string[];
  illustrators: string[];
  colorists: string[];
  content_warnings?: { graphic: string[]; moderate: string[]; minor: string[] } | null;
}

export interface BookListResponse {
  items: Book[];
  total: number;
  skip: number;
  limit: number;
}

// ── Shelves ───────────────────────────────────────────────────────────────────

export interface SmartFilterRule {
  field: 'tag' | 'author' | 'series' | 'title' | 'language' | 'status' | 'rating' | 'min_rating';
  op: 'contains' | 'equals' | 'gte';
  value: string;
}

export interface Shelf {
  id: number;
  user_id: number;
  name: string;
  description?: string | null;
  is_smart: boolean;
  smart_filter?: string | null;
  sync_to_kobo: boolean;
  created_at: string;
  updated_at: string;
  book_count?: number;
}

// ── Ingest ────────────────────────────────────────────────────────────────────

export interface IngestLog {
  id: number;
  filename: string;
  status: 'imported' | 'duplicate' | 'error' | 'unsupported';
  book_id?: number | null;
  error_message?: string | null;
  created_at: string;
}

// ── Progress ──────────────────────────────────────────────────────────────────

export interface ReadProgress {
  id: number;
  user_id: number;
  book_id: number;
  device_id: number;
  current_page: number;
  total_pages?: number | null;
  percentage: number;
  status: 'want_to_read' | 'reading' | 'completed' | 'abandoned';
  rating?: number | null;  // 1-5
  started_at?: string | null;
  completed_at?: string | null;
  last_opened: string;
  created_at?: string;
  updated_at?: string;
}

// ── Browse ────────────────────────────────────────────────────────────────────

export interface AuthorDetail {
  id: number;
  name: string;
  description?: string | null;
  book_count: number;
}

export interface TagDetail {
  id: number;
  name: string;
  book_count: number;
}

export interface SeriesDetail {
  id: number;
  name: string;
  description?: string | null;
  book_count: number;
  cover_book_id?: number | null;
}

export interface SeriesEntry {
  book: Book;
  position: number | null;
  volume: string | null;
  arc: string | null;
  read_status: 'want_to_read' | 'reading' | 'completed' | 'abandoned' | null;
}

export interface BookSeriesEntry {
  series_id: number;
  name: string;
  position: number | null;
  volume: string | null;
  arc: string | null;
}

export interface SeriesPageData {
  id: number;
  name: string;
  description: string | null;
  book_count: number;
  entries: SeriesEntry[];
}

// ── API Keys ──────────────────────────────────────────────────────────────────

export interface ApiKey {
  id: number;
  name: string;
  prefix: string;
  last_used_at?: string | null;
  created_at: string;
  is_active: boolean;
}

export interface ApiKeyCreated extends ApiKey {
  key: string;
}

// ── Collections ───────────────────────────────────────────────────────────────

export interface SmartFilter {
  library_id?: number | null;
  author?: string | null;
  tag?: string | null;
  series?: string | null;
  format?: string | null;
  language?: string | null;
  status?: string | null;
  has_isbn?: boolean | null;
  physical_copy?: boolean | null;
  binding?: string | null;
  condition?: string | null;
  min_rating?: number | null;
}

export interface Collection {
  id: number;
  user_id: number;
  name: string;
  description?: string | null;
  cover_book_id?: number | null;
  cover_work_id?: number | null;
  is_smart: boolean;
  is_pinned: boolean;
  sync_to_kobo: boolean;
  source?: string | null;
  smart_filter?: SmartFilter | null;
  created_at: string;
  updated_at: string;
  book_count: number;
}

export interface CollectionDetail extends Collection {
  books: Book[];
}

// ── Annotations ───────────────────────────────────────────────────────────────

export interface Annotation {
  id: number;
  user_id: number;
  book_id: number;
  edition_id?: number | null;
  file_id?: number | null;
  type: 'highlight' | 'note' | 'bookmark';
  content?: string | null;
  location?: string | null;
  chapter?: string | null;
  color?: string | null;
  tags?: string[] | null;
  related_refs?: string[] | null;
  commentator?: string | null;
  source?: string | null;
  is_spoiler?: boolean;
  created_at: string;
  updated_at: string;
}

// ── Marginalia ────────────────────────────────────────────────────────────────

export type MarginaliumKind =
  | 'observation'
  | 'insight'
  | 'question'
  | 'theme'
  | 'symbol'
  | 'character'
  | 'parallel'
  | 'structure'
  | 'context'
  | 'esoteric'
  | 'boring';

export type ReadingLevel = 'surface' | 'exoteric' | 'esoteric' | 'meta';

export interface Marginalium {
  id: number;
  user_id: number;
  book_id: number;
  edition_id?: number | null;
  file_id?: number | null;
  kind: MarginaliumKind;
  reading_level?: ReadingLevel | null;
  content: string;
  location?: string | null;
  chapter?: string | null;
  related_refs?: string[] | null;
  tags?: string[] | null;
  commentator?: string | null;
  source?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MarginaliumWithBook extends Marginalium {
  book_title?: string | null;
  book_author?: string | null;
}

// ── Read Sessions ─────────────────────────────────────────────────────────────

export interface ReadSession {
  id: number;
  user_id: number;
  book_id: number;
  work_id?: number | null;
  started_at: string;
  finished_at?: string | null;
  rating?: number | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

// ── Generic ───────────────────────────────────────────────────────────────────

export interface ApiResponse<T> {
  data?: T;
  message?: string;
  error?: string;
  status: number;
}

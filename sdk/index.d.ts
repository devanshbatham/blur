export type Label =
  | "private_person" | "private_address" | "private_email" | "private_phone" | "private_date"
  | "private_url" | "account_number" | "personal_id" | "secret" | "online_identifier";

export interface Span {
  /** UTF-16 offset of the first character. */
  start: number;
  /** UTF-16 offset after the last character. */
  end: number;
  label: Label;
  /** The original text of the span. */
  text: string;
}

export interface DetectOptions {
  /** Report only these labels. */
  only?: Label[];
  /** Never report these labels. */
  keep?: Label[];
  /** Numbered placeholders such as [PERSON_1] (needs `createBlur({ pipeline: true })`). */
  numbered?: boolean;
  /** Set to false to run only the network on a pipeline-enabled masker. */
  pipeline?: boolean;
}

export interface MaskOptions extends DetectOptions {
  /** Replace each masked character with this character instead of writing a placeholder. */
  char?: string;
}

export interface Blur {
  mask(text: string, options?: MaskOptions): { text: string; spans: Span[] };
  detect(text: string, options?: DetectOptions): Span[];
  readonly labels: readonly Label[];
  readonly info: { neurons: number; connections: number; bytes: number; reachLeft: number; reachRight: number };
  readonly version: string;
}

export interface CreateOptions {
  /** Model file: URL, path URL or bytes. Default: the bundled `web/model-general.bin`. */
  model?: string | URL | ArrayBuffer | ArrayBufferView;
  /** Load the full pipeline (cross-document name linking, numbered placeholders). Default false. */
  pipeline?: boolean;
}

export const LABELS: readonly Label[];
export const VERSION: string;
export function createBlur(options?: CreateOptions): Promise<Blur>;

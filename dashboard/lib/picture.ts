// Profile pictures (David, 9 Nov 2026): what an upload may be, and where a saved one is fetched. Import-free, so the
// browser, the server action and the tests share it.

/** The kinds of picture an upload may be. SVG is not one: it can carry script. */
export const PICTURE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"] as const;
export type PictureType = (typeof PICTURE_TYPES)[number];

/** The size a picture is stored at, square. */
export const PICTURE_SIZE = 256;

/** The largest upload the server takes; the browser shrinks a picture well below this before sending it. */
export const MAX_PICTURE_BYTES = 900_000;

/** What a file is by its first bytes, never by its name or the type the browser claims; null for anything else. */
export function sniffImage(bytes: Uint8Array): PictureType | null {
  const starts = (offset: number, ...want: number[]) => bytes.length >= offset + want.length && want.every((b, i) => bytes[offset + i] === b);
  if (starts(0, 0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a)) return "image/png";
  if (starts(0, 0xff, 0xd8, 0xff)) return "image/jpeg";
  if (starts(0, 0x47, 0x49, 0x46, 0x38)) return "image/gif";
  if (starts(0, 0x52, 0x49, 0x46, 0x46) && starts(8, 0x57, 0x45, 0x42, 0x50)) return "image/webp";
  return null;
}

/** Where a person's picture is fetched. It carries when the picture was set, so a new one replaces the cached one. */
export function pictureUrl(name: string, updatedAt: string): string {
  return `/api/picture?name=${encodeURIComponent(name)}&v=${encodeURIComponent(updatedAt)}`;
}

/**
 * A person's picture, or their initials while they have none (David, 9 Nov 2026). It only decorates: the person's name
 * is always written beside it, so it carries no text of its own for a screen reader.
 */
export function Avatar({ initials, picture, size }: { initials: string; picture?: string | null; size?: "small" | "big" | "huge" }) {
  const className = `initials avatar${size ? ` ${size}` : ""}`;
  if (picture) {
    // A small picture the dashboard serves itself, already 256 pixels square; next/image would only add a copy.
    // eslint-disable-next-line @next/next/no-img-element
    return <img className={`${className} has-picture`} src={picture} alt="" aria-hidden="true" decoding="async" />;
  }
  return (
    <span className={className} aria-hidden="true">
      {initials}
    </span>
  );
}

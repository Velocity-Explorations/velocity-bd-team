"use client";

import { useRef, useState, useTransition } from "react";
import { removePictureAction, savePictureAction } from "@/app/actions";
import { Avatar } from "@/components/Avatar";
import { PICTURE_TYPES } from "@/lib/picture";

const SENT_SIZE = 512;   // the browser sends at most this square; the server makes the stored 256

/**
 * Profile settings' picture (David, 9 Nov 2026). Choosing a file saves it at once, apart from the profile's Save: the
 * browser crops it to a square and shrinks it, then the server checks it and re-encodes it. The file box has no name,
 * so the profile form never sends it.
 */
export function PictureField({ initials, picture }: { initials: string; picture: string | null }) {
  const input = useRef<HTMLInputElement>(null);
  const [pending, start] = useTransition();
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  async function choose(file: File | undefined) {
    if (!file) return;
    setMessage(null);
    let square: Blob;
    try {
      square = await squareOf(file);
    } catch {
      setMessage({ ok: false, text: "That file could not be read as a picture. Use a JPEG, PNG, WebP or GIF." });
      return;
    } finally {
      if (input.current) input.current.value = "";   // the same file can be chosen again
    }
    const data = new FormData();
    data.set("picture", square, "picture.jpg");
    start(async () => {
      const result = await savePictureAction(data);
      setMessage({ ok: result.ok, text: result.message });
    });
  }

  function remove() {
    setMessage(null);
    start(async () => {
      const result = await removePictureAction();
      setMessage({ ok: result.ok, text: result.message });
    });
  }

  return (
    <div className="picture-field">
      <Avatar initials={initials} picture={picture} size="huge" />
      <div className="picture-actions">
        <label className={pending ? "btn disabled" : "btn"}>
          {picture ? "Change picture" : "Upload picture"}
          <input
            ref={input}
            type="file"
            className="sr-only"
            accept={PICTURE_TYPES.join(",")}
            disabled={pending}
            onChange={(event) => void choose(event.target.files?.[0])}
          />
        </label>
        {picture ? (
          <button type="button" className="btn-text" onClick={remove} disabled={pending}>
            Remove
          </button>
        ) : null}
        <span className={message && !message.ok ? "picture-state error" : "picture-state"} role="status">
          {pending ? "Saving..." : (message?.text ?? "")}
        </span>
      </div>
    </div>
  );
}

/** The picture's middle square, at most SENT_SIZE across, as a JPEG on white (a transparent PNG would turn black). */
async function squareOf(file: File): Promise<Blob> {
  const bitmap = await createImageBitmap(file);
  try {
    const side = Math.min(bitmap.width, bitmap.height);
    if (!side) throw new Error("empty picture");
    const out = Math.min(SENT_SIZE, side);
    const canvas = document.createElement("canvas");
    canvas.width = out;
    canvas.height = out;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("no canvas");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, out, out);
    ctx.drawImage(bitmap, (bitmap.width - side) / 2, (bitmap.height - side) / 2, side, side, 0, 0, out, out);
    return await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("no picture"))), "image/jpeg", 0.9);
    });
  } finally {
    bitmap.close();
  }
}

"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useFormStatus } from "react-dom";
import { rowOutcome } from "@/lib/decide";
import { ratingAt, SLIDER, stopOf } from "@/lib/fitratings";

/**
 * One rating as a slider from Never to Core (David, 9 Nov 2026), inside its row's form on /fit. It saves when it is let
 * go, or with each arrow-key step: the form's hidden rating takes the new value and the form submits to
 * saveFitRatingAction, as the buttons did. A row nobody rated sits greyed at Neutral until it is moved; Clear sets it
 * back to not rated. Saving... shows while it saves, then Saved for a few seconds (Task 3, 18 Nov 2026; the note box
 * already said so, the slider did not), and a save that fails says why here, beside the slider, as well as at the top.
 */
export function FitSlider({ fitKey, name, rating }: { fitKey: string; name: string; rating: string | null }) {
  const slider = useRef<HTMLInputElement>(null);
  const chosen = useRef<HTMLInputElement>(null);
  const [stop, setStop] = useState(stopOf(rating));
  const [rated, setRated] = useState(Boolean(rating));
  const { pending } = useFormStatus();
  const mine = useRef(false);   // the form's save is this slider's, not the note box's
  const [saved, setSaved] = useState(false);
  const search = useSearchParams();
  const failed = rowOutcome({ row: search.get("row"), error: search.get("error") }, fitKey);

  useEffect(() => {   // Saved once a save this slider started has gone through
    if (pending || !mine.current) return undefined;
    mine.current = false;
    setSaved(true);
    const timer = window.setTimeout(() => setSaved(false), 4000);
    return () => window.clearTimeout(timer);
  }, [pending]);

  useEffect(() => {   // after a save the page sends the stored rating back
    setStop(stopOf(rating));
    setRated(Boolean(rating));
  }, [rating]);

  useEffect(() => {
    const el = slider.current;
    if (!el) return;
    const save = () => {   // the native change event: the slider let go, or an arrow key pressed
      if (!chosen.current) return;
      chosen.current.value = ratingAt(Number(el.value));
      mine.current = true;
      el.form?.requestSubmit();
    };
    el.addEventListener("change", save);
    return () => el.removeEventListener("change", save);
  }, []);

  const clear = () => {
    if (!chosen.current || !slider.current) return;
    chosen.current.value = "clear";
    mine.current = true;
    slider.current.form?.requestSubmit();
  };

  const at = SLIDER[stop];
  return (
    <div className={`fit-slider-wrap tone-${rated ? at.tone : "none"}${rated ? "" : " unrated"}`}>
      <input ref={chosen} type="hidden" name="rating" value={rated ? at.key : ""} readOnly />
      <div className="fit-slider-head">
        <span className="fit-slider-value">{rated ? at.label : "not rated"}</span>
        {rated ? <span className="muted"> {at.means}</span> : null}
        <span className={saved && !pending ? "fit-slider-state saved" : "fit-slider-state"} aria-live="polite">
          {pending ? "Saving..." : saved ? "Saved" : ""}
        </span>
        {rated ? (
          <button type="button" className="link-button fit-clear" onClick={clear} disabled={pending}>
            Clear
          </button>
        ) : null}
      </div>
      <input
        ref={slider}
        type="range"
        className="fit-slider"
        min={0}
        max={SLIDER.length - 1}
        step={1}
        value={stop}
        disabled={pending}
        aria-label={`Rating for ${name}`}
        aria-valuetext={rated ? at.label : "not rated"}
        onChange={(event) => {   // React's change is each move; the save waits for the native change
          setStop(Number(event.target.value));
          setRated(true);
        }}
      />
      {failed ? <p className="fit-slider-error tone-conflict">{failed.text}</p> : null}
      <ol className="fit-stops" aria-hidden="true">
        {SLIDER.map((s) => (
          <li key={s.key} className={rated && s.key === at.key ? "on" : undefined}>{s.label}</li>
        ))}
      </ol>
    </div>
  );
}

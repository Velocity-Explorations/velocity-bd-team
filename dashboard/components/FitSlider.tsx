"use client";

import { useEffect, useRef, useState } from "react";
import { useFormStatus } from "react-dom";
import { ratingAt, SLIDER, stopOf } from "@/lib/fitratings";

/**
 * One rating as a slider from Never to Core (David, 9 Nov 2026), inside its row's form on /fit. It saves when it is let
 * go, or with each arrow-key step: the form's hidden rating takes the new value and the form submits to
 * saveFitRatingAction, as the buttons did. A row nobody rated sits greyed at Neutral until it is moved; Clear sets it
 * back to not rated.
 */
export function FitSlider({ name, rating }: { name: string; rating: string | null }) {
  const slider = useRef<HTMLInputElement>(null);
  const chosen = useRef<HTMLInputElement>(null);
  const [stop, setStop] = useState(stopOf(rating));
  const [rated, setRated] = useState(Boolean(rating));
  const { pending } = useFormStatus();

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
      el.form?.requestSubmit();
    };
    el.addEventListener("change", save);
    return () => el.removeEventListener("change", save);
  }, []);

  const clear = () => {
    if (!chosen.current || !slider.current) return;
    chosen.current.value = "clear";
    slider.current.form?.requestSubmit();
  };

  const at = SLIDER[stop];
  return (
    <div className={`fit-slider-wrap tone-${rated ? at.tone : "none"}${rated ? "" : " unrated"}`}>
      <input ref={chosen} type="hidden" name="rating" value={rated ? at.key : ""} readOnly />
      <div className="fit-slider-head">
        <span className="fit-slider-value">{rated ? at.label : "not rated"}</span>
        {rated ? <span className="muted"> {at.means}</span> : null}
        <span className="fit-slider-state" aria-live="polite">{pending ? "Saving..." : ""}</span>
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
      <ol className="fit-stops" aria-hidden="true">
        {SLIDER.map((s) => (
          <li key={s.key} className={rated && s.key === at.key ? "on" : undefined}>{s.label}</li>
        ))}
      </ol>
    </div>
  );
}

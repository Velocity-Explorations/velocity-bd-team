import { ArrowRight } from "lucide-react";
import Link from "next/link";
import type { ViewCard } from "@/lib/views";

/**
 * A row of view cards (VC1, PRO-570): label band, number and one line, aligned across the row. The
 * open view's card is marked as the current page. The count that needs the viewer is in the accent
 * while it is above zero. Home's cards open other pages (VC3): each carries an arrow and says its
 * count and where it goes.
 */
export function ViewCards({ label, cards, opens = false }: { label: string; cards: ViewCard[]; opens?: boolean }) {
  return (
    <nav className="vt-card-row view-cards" aria-label={label}>
      {cards.map((card) => (
        <Link
          key={card.key}
          href={card.href}
          className="vt-card"
          aria-current={card.current ? "page" : undefined}
          aria-label={opens ? `${card.label}: ${card.count}, ${card.description}. Opens ${card.label}.` : undefined}
        >
          <span className="vt-card__label">
            {card.label}
            {opens ? <ArrowRight aria-hidden="true" /> : null}
          </span>
          <span className={card.needsYou && Number(card.count) > 0 ? "vt-card__number vt-card__number--needs-you" : "vt-card__number"}>{card.count}</span>
          <span className="vt-card__description">{card.description}</span>
        </Link>
      ))}
    </nav>
  );
}

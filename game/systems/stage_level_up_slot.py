from __future__ import annotations

import random

from game.systems.stage_cards import (
    CARDS_BY_TITLE,
    STAGE_CARD_CATALOG,
    card_offer_weight,
    card_rank_title,
    eligible_cards,
)


SAMPLE_CARD_LABELS = tuple(card.title for card in STAGE_CARD_CATALOG)
REEL_STOP_TIMES = (1.35, 1.68, 2.0)
REEL_CYCLE_INTERVAL = 0.075
CARD_REVEAL_RATE = 38.0


class StageLevelUpSlot:
    """Three-reel, ranked card offer flow used by Stage and Test Modes."""

    def __init__(self, rng=random) -> None:
        self.rng = rng
        self.active = False
        self.level_id: int | None = None
        self.elapsed = 0.0
        self.offers: list[str] = []
        self.offer_ranks: list[int] = []
        self.reel_labels: list[str] = []
        self.stopped: list[bool] = []
        self.reel_scroll_offsets: list[float] = []
        self.reel_scroll_speeds: list[float] = []
        self.reel_scroll_positions: list[float] = []
        self.reel_card_sequences: list[list[str]] = []
        self.reveal_orders: list[list[list[int]]] = []
        self.selected_index = 0
        self.last_selection: str | None = None
        self.visual_only = False

    @property
    def ready(self) -> bool:
        return self.active and bool(self.stopped) and all(self.stopped)

    def start(
        self,
        level_id: int,
        ranks: dict[str, int] | None = None,
        visual_only: bool = False,
    ) -> bool:
        cards = eligible_cards()
        if not cards:
            self.active = False
            self.visual_only = visual_only
            self.offers = []
            self.reel_labels = []
            self.stopped = []
            return False
        remaining_cards = list(cards)
        selected_cards = []
        current_ranks = {} if visual_only else (ranks or {})
        for _ in range(min(3, len(remaining_cards))):
            weights = [
                card_offer_weight(current_ranks.get(card.key, 0))
                for card in remaining_cards
            ]
            selected = self.rng.choices(
                remaining_cards,
                weights=weights,
                k=1,
            )[0]
            selected_cards.append(selected)
            remaining_cards.remove(selected)
        eligible_titles = [card.title for card in cards]
        self.level_id = level_id
        self.elapsed = 0.0
        self.offers = [card.title for card in selected_cards]
        self.offer_ranks = [
            1 if visual_only else (ranks or {}).get(card.key, 0) + 1
            for card in selected_cards
        ]
        self.reel_labels = [
            self.rng.choice(eligible_titles) for _ in selected_cards
        ]
        self.stopped = [False] * len(selected_cards)
        self.reel_scroll_offsets = [0.0] * len(selected_cards)
        self.reel_scroll_speeds = [0.0] * len(selected_cards)
        self.reel_scroll_positions = [0.0] * len(selected_cards)
        self.reel_card_sequences = []
        for title in self.offers:
            sequence = [
                self.rng.choice(eligible_titles) for _ in range(12)
            ]
            sequence[10] = title
            self.reel_card_sequences.append(sequence)
        self.reveal_orders = []
        for title, rank in zip(self.offers, self.offer_ranks):
            card = CARDS_BY_TITLE[title]
            strings = (card_rank_title(card, rank), card.description, card.perk)
            text_orders = []
            for text in strings:
                order = [index for index, char in enumerate(text) if not char.isspace()]
                self.rng.shuffle(order)
                text_orders.append(order)
            self.reveal_orders.append(text_orders)
        self.selected_index = 0
        self.visual_only = visual_only
        self.active = True
        return True

    def update(self, dt: float) -> None:
        if not self.active:
            return
        self.elapsed += max(0.0, dt)
        for index, stop_time in enumerate(REEL_STOP_TIMES[:len(self.offers)]):
            if self.stopped[index]:
                continue
            if self.elapsed >= stop_time:
                self.stopped[index] = True
                self.reel_labels[index] = self.offers[index]
                self.reel_scroll_offsets[index] = 0.0
                self.reel_scroll_speeds[index] = 0.0
                self.reel_scroll_positions[index] = 10.0
            else:
                progress = max(0.0, min(1.0, self.elapsed / stop_time))
                eased_travel = 10.0 * (1.0 - (1.0 - progress) ** 3)
                self.reel_scroll_positions[index] = eased_travel
                self.reel_scroll_offsets[index] = (eased_travel % 1.0) * 282.0
                self.reel_scroll_speeds[index] = (
                    30.0 * (1.0 - progress) ** 2 * 282.0 / stop_time
                )
                card_index = min(10, int(eased_travel))
                self.reel_labels[index] = self.reel_card_sequences[index][card_index]

    def revealed_text(self, index: int, field_index: int) -> str:
        """Return text with a stable, randomized subset of characters revealed."""
        title = self.offers[index]
        card = CARDS_BY_TITLE[title]
        text = (
            card_rank_title(card, self.offer_ranks[index]),
            card.description,
            card.perk,
        )[field_index]
        if not self.stopped[index]:
            return ""
        visible_count = min(
            len(self.reveal_orders[index][field_index]),
            int(max(0.0, self.elapsed - REEL_STOP_TIMES[index]) * CARD_REVEAL_RATE),
        )
        if visible_count == 0:
            return ""
        visible = set(self.reveal_orders[index][field_index][:visible_count])
        return "".join(
            char if char.isspace() or position in visible else " "
            for position, char in enumerate(text)
        )

    def move_selection(self, direction: int) -> None:
        if self.ready and direction:
            self.selected_index = (self.selected_index + direction) % len(self.offers)

    def confirm(self) -> str | None:
        if not self.ready:
            return None
        self.last_selection = self.offers[self.selected_index]
        self.active = False
        return self.last_selection

"""The Qobuz app's play queue, as the Connect cloud reports it.

Items carry only a queue item id and a track id; the receiver looks tracks up
itself. Order is play order. A shuffled queue is taken whole from a full queue
state, which lists the shuffled order, rather than reconstructed from a seed.

Protocol details adapted from Pibuz (https://github.com/PhilipVinc/pibuz,
crates/qconnect-core/src/reducer.rs and
crates/qconnect-app/src/queue_resolution.rs), MIT License:
Copyright (c) 2024 blitzkriegfc, Copyright (c) 2026 Filippo Vicentini.
"""

from dataclasses import dataclass
from typing import Iterable, Optional

from .proto import qconnect_pb2 as qc


@dataclass(frozen=True)
class QueueItem:
    queue_item_id: int
    track_id: int


def item_of(track) -> Optional[QueueItem]:
    """A QueueTrack or QueueTrackWithContext; None for the cloud's "none" (-1)."""
    if not track.HasField("track_id") or track.queue_item_id < 0:
        return None
    return QueueItem(track.queue_item_id, track.track_id)


class CloudQueue:
    def __init__(self):
        self.version: tuple[int, int] = (0, 0)
        self.items: list[QueueItem] = []
        # The position a freshly loaded queue starts at, until something else changes it.
        self.selected: Optional[int] = None

    def apply(self, message: qc.QConnectMessage) -> bool:
        """Fold one queue message in. True when the full state should be asked for."""
        kind = message.message_type
        self.selected = None
        if kind == qc.SRVR_CTRL_QUEUE_STATE:
            body = message.srvr_ctrl_queue_state
            items = _items(body.tracks)
            if body.shuffle_mode and len(body.shuffled_track_indexes) == len(items):
                items = [items[i] for i in body.shuffled_track_indexes if 0 <= i < len(items)]
            self.items = items
            self._version(body)
            return False
        if kind == qc.SRVR_CTRL_QUEUE_TRACKS_LOADED:
            body = message.srvr_ctrl_queue_tracks_loaded
            self.items = _items(body.tracks)
            self.selected = body.queue_position if body.HasField("queue_position") else None
            self._version(body)
            return body.shuffle_mode
        if kind == qc.SRVR_CTRL_QUEUE_TRACKS_INSERTED:
            body = message.srvr_ctrl_queue_tracks_inserted
            at = self._index_after(body.insert_after if body.HasField("insert_after") else None)
            self.items[at:at] = _items(body.tracks)
            self._version(body)
            return False
        if kind == qc.SRVR_CTRL_QUEUE_TRACKS_ADDED:
            body = message.srvr_ctrl_queue_tracks_added
            self.items.extend(_items(body.tracks))
            self._version(body)
            return False
        if kind == qc.SRVR_CTRL_QUEUE_TRACKS_REMOVED:
            body = message.srvr_ctrl_queue_tracks_removed
            removed = set(body.queue_item_ids)
            self.items = [item for item in self.items if item.queue_item_id not in removed]
            self._version(body)
            return False
        if kind == qc.SRVR_CTRL_QUEUE_CLEARED:
            self.items = []
            self._version(message.srvr_ctrl_queue_cleared)
            return False
        # Reordered and shuffled: the new order is simplest taken whole.
        return kind in (qc.SRVR_CTRL_QUEUE_TRACKS_REORDERED, qc.SRVR_CTRL_SHUFFLE_MODE_SET)

    def find(self, queue_item_id: int) -> Optional[QueueItem]:
        return next((i for i in self.items if i.queue_item_id == queue_item_id), None)

    def after(self, item: Optional[QueueItem]) -> Optional[QueueItem]:
        index = self._index_of(item)
        if index is None or index + 1 >= len(self.items):
            return None
        return self.items[index + 1]

    def before(self, item: Optional[QueueItem]) -> Optional[QueueItem]:
        index = self._index_of(item)
        if index is None or index == 0:
            return None
        return self.items[index - 1]

    def first(self) -> Optional[QueueItem]:
        return self.items[0] if self.items else None

    def selected_item(self) -> Optional[QueueItem]:
        if self.selected is None or not 0 <= self.selected < len(self.items):
            return None
        return self.items[self.selected]

    def reported_id(self, item: Optional[QueueItem]) -> int:
        """The id to report an item under; 0 is omitted from reports.

        The cloud gives the head of a freshly pushed queue the track's own id in
        place of a queue item id, and expects it reported as 0. The tell is the
        head's id equalling its track id, corroborated by a smaller id behind it.
        """
        if item is None:
            return 0
        index = self._index_of(item)
        if index == 0 and item.queue_item_id == item.track_id:
            later = self.items[1:]
            if not later or any(i.queue_item_id < item.queue_item_id for i in later):
                return 0
        return item.queue_item_id

    def _index_of(self, item: Optional[QueueItem]) -> Optional[int]:
        if item is None:
            return None
        for index, candidate in enumerate(self.items):
            if candidate.queue_item_id == item.queue_item_id:
                return index
        for index, candidate in enumerate(self.items):
            if candidate.track_id == item.track_id:
                return index
        return None

    def _index_after(self, queue_item_id: Optional[int]) -> int:
        if queue_item_id is not None:
            for index, item in enumerate(self.items):
                if item.queue_item_id == queue_item_id:
                    return index + 1
        return len(self.items)

    def _version(self, body) -> None:
        if body.HasField("queue_version"):
            self.version = (body.queue_version.major, body.queue_version.minor)


def _items(tracks: Iterable) -> list[QueueItem]:
    return [item for item in (item_of(t) for t in tracks) if item is not None]

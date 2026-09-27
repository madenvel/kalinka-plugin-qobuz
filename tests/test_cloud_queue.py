"""The Qobuz app's queue as the Connect cloud reports it."""

from kalinka_plugin_qobuz.connect.cloud_queue import CloudQueue, QueueItem
from kalinka_plugin_qobuz.connect.proto import qconnect_pb2 as qc


def _tracks(*pairs, kind=qc.QueueTrack):
    return [kind(queue_item_id=qid, track_id=tid) for qid, tid in pairs]


def _loaded(*pairs, position=None, shuffle=False):
    body = qc.QueueTracksLoadedMessage(
        queue_version=qc.QueueVersionRef(major=3, minor=1), tracks=_tracks(*pairs)
    )
    if position is not None:
        body.queue_position = position
    if shuffle:
        body.shuffle_mode = True
    return qc.QConnectMessage(
        message_type=qc.SRVR_CTRL_QUEUE_TRACKS_LOADED, srvr_ctrl_queue_tracks_loaded=body
    )


def _ids(queue):
    return [item.queue_item_id for item in queue.items]


def test_a_loaded_queue_replaces_everything_and_remembers_where_it_starts():
    queue = CloudQueue()

    assert queue.apply(_loaded((1, 100), (2, 200), (3, 300), position=1)) is False

    assert _ids(queue) == [1, 2, 3]
    assert queue.version == (3, 1)
    assert queue.selected_item() == QueueItem(2, 200)


def test_a_shuffled_load_asks_for_the_full_state():
    assert CloudQueue().apply(_loaded((1, 100), shuffle=True)) is True


def test_a_full_state_is_taken_in_its_shuffled_order():
    queue = CloudQueue()
    body = qc.QueueStateMessage(
        tracks=_tracks((1, 100), (2, 200), (3, 300), kind=qc.QueueTrackWithContext),
        shuffle_mode=True,
        shuffled_track_indexes=[2, 0, 1],
    )

    queue.apply(qc.QConnectMessage(message_type=qc.SRVR_CTRL_QUEUE_STATE, srvr_ctrl_queue_state=body))

    assert _ids(queue) == [3, 1, 2]


def test_tracks_are_inserted_after_the_named_item_or_at_the_end():
    queue = CloudQueue()
    queue.apply(_loaded((1, 100), (2, 200)))

    queue.apply(
        qc.QConnectMessage(
            message_type=qc.SRVR_CTRL_QUEUE_TRACKS_INSERTED,
            srvr_ctrl_queue_tracks_inserted=qc.QueueTracksInsertedMessage(
                tracks=_tracks((9, 900)), insert_after=1
            ),
        )
    )
    queue.apply(
        qc.QConnectMessage(
            message_type=qc.SRVR_CTRL_QUEUE_TRACKS_INSERTED,
            srvr_ctrl_queue_tracks_inserted=qc.QueueTracksInsertedMessage(
                tracks=_tracks((8, 800)), insert_after=77
            ),
        )
    )

    assert _ids(queue) == [1, 9, 2, 8]


def test_added_removed_and_cleared():
    queue = CloudQueue()
    queue.apply(_loaded((1, 100)))

    queue.apply(
        qc.QConnectMessage(
            message_type=qc.SRVR_CTRL_QUEUE_TRACKS_ADDED,
            srvr_ctrl_queue_tracks_added=qc.QueueTracksAddedMessage(tracks=_tracks((2, 200), (3, 300))),
        )
    )
    queue.apply(
        qc.QConnectMessage(
            message_type=qc.SRVR_CTRL_QUEUE_TRACKS_REMOVED,
            srvr_ctrl_queue_tracks_removed=qc.QueueTracksRemovedMessage(queue_item_ids=[2]),
        )
    )
    assert _ids(queue) == [1, 3]

    queue.apply(
        qc.QConnectMessage(
            message_type=qc.SRVR_CTRL_QUEUE_CLEARED,
            srvr_ctrl_queue_cleared=qc.QueueClearedMessage(),
        )
    )
    assert queue.items == []


def test_a_reorder_asks_for_the_full_state():
    queue = CloudQueue()

    assert queue.apply(
        qc.QConnectMessage(
            message_type=qc.SRVR_CTRL_QUEUE_TRACKS_REORDERED,
            srvr_ctrl_queue_tracks_reordered=qc.QueueTracksReorderedMessage(queue_item_ids=[1]),
        )
    )


def test_neighbours_are_found_by_queue_item_or_by_track():
    queue = CloudQueue()
    queue.apply(_loaded((1, 100), (2, 200), (3, 300)))

    assert queue.after(QueueItem(1, 100)) == QueueItem(2, 200)
    assert queue.before(QueueItem(1, 100)) is None
    assert queue.after(QueueItem(3, 300)) is None
    assert queue.after(QueueItem(99, 200)) == QueueItem(3, 300)
    assert queue.after(None) is None


def test_the_cloud_placeholder_head_is_reported_as_zero():
    """A fresh push names its head by the track id; later items corroborate it."""
    queue = CloudQueue()
    queue.apply(_loaded((126886853, 126886853), (10, 123452387), (1, 126886854)))

    assert queue.reported_id(QueueItem(126886853, 126886853)) == 0
    assert queue.reported_id(QueueItem(10, 123452387)) == 10


def test_a_single_track_head_rests_on_itself():
    queue = CloudQueue()
    queue.apply(_loaded((555, 555)))

    assert queue.reported_id(QueueItem(555, 555)) == 0


def test_a_none_track_is_no_item():
    queue = CloudQueue()
    queue.apply(_loaded((-1, 100), (2, 200)))

    assert _ids(queue) == [2]

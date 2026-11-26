# scenario: session_open_channel opens the one line to the primary
# inherits: hd=python/honest-persist/honest-persist.hd::session_open_channel -> feature=specs/features/honest-persist.feature::session_open_channel opens the one line to the primary

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import honest_persist as hp
import turso


def probe_session_open_channel_local_refusal():
    async def open_with_missing_ancestors(target):
        channel = await hp.session_open_channel(str(target), "not-a-valid-url", "")
        if hp.is_fault(channel):
            return [f"opening the channel should create its nested local parent: {channel!r}"]
        try:
            if not target.parent.is_dir():
                return ["the channel did not create its local parent"]
            pushed = await asyncio.wait_for(hp.channel_push(channel), 3)
            return [] if hp.is_fault(pushed) else ["the unreachable primary should be refused on the first push"]
        finally:
            try:
                await asyncio.wait_for(channel, 3)
            except turso.Error:
                # Consume the native driver's background open result before closing the channel.
                pass
            await asyncio.wait_for(hp.session_close_connection(channel), 3)

    with TemporaryDirectory() as directory:
        root = Path(directory)
        failures = asyncio.run(open_with_missing_ancestors(root / "new" / "nested" / "replica.db"))
        blocker = Path(directory) / "regular-file"
        blocker.write_text("not a directory", encoding="utf-8")
        target = str(blocker / "child" / "replica.db")
        outcome = asyncio.run(hp.session_open_channel(target, "http://127.0.0.1:1", ""))
        if not hp.is_fault(outcome) or outcome.get("code") != "channel_would_not_open":
            failures.append(f"an unmakeable channel parent should produce channel_would_not_open: {outcome!r}")
        elif target not in outcome["message"] or "open" not in outcome["message"].casefold():
            failures.append(f"the channel refusal did not identify the failure and its local path: {outcome!r}")
        return failures

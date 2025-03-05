import pytest
import pandas as pd
from scale_model.multiprocess_test_model import single_run

@pytest.mark.parametrize("duration", [2])
def test_single_send(duration):
    """
    'send_one' mode => always produce SEND events each cycle.
    No other event types should appear except SEND (and possibly no receiving side).
    """
    df = single_run(mode="send_one", duration=duration)
    sends = df[df["event_type"] == "SEND"]
    assert len(sends) > 0, "We expected some SEND events in send_one mode!"
    
    # Optionally check that internal events do not appear 
    internals = df[df["event_type"] == "INTERNAL"]
    assert len(internals) == 0, "We expected 0 INTERNAL events in send_one mode."

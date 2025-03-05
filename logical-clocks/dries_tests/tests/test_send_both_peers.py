import pytest
import pandas as pd
from scale_model.multiprocess_test_model import single_run

@pytest.mark.parametrize("duration", [2])
def test_send_both(duration):
    """
    'send_both' => each cycle we do 2 SEND events (to=0 and to=1).
    We'll see multiple SENDs. 
    """
    df = single_run(mode="send_both", duration=duration)
    sends = df[df["event_type"] == "SEND"]
    assert len(sends) >= 2, "We expected multiple SEND events in send_both mode!"
    
    # Probably no INTERNAL events
    internals = df[df["event_type"] == "INTERNAL"]
    assert len(internals) == 0, "We expected 0 INTERNAL events in send_both mode."

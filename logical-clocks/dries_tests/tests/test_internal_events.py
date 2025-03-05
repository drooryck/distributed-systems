import pytest
import pandas as pd
from dries_tests.scale_model.multiprocess_test_model import single_run

@pytest.mark.parametrize("duration", [2])
def test_internal_events(duration):
    """
    Run a single VM in 'internal' mode => only INTERNAL events. 
    The child's code never tries to SEND.
    """
    df = single_run(mode="internal", duration=duration)
    print(df)
    sends = df[df["event_type"] == "SEND"]
    assert len(sends) == 0, "We expected 0 SEND events in internal-only mode."
    internals = df[df["event_type"] == "INTERNAL"]
    assert len(internals) > 0, "We expected some INTERNAL events!"

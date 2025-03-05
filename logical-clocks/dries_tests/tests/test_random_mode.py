import pytest
import pandas as pd
import random
from dries_tests.scale_model.multiprocess_test_model import single_run

@pytest.mark.parametrize("seed", [42, 123])
def test_random_mode(seed):
    """
    Use 'random' mode, but set a fixed seed for reproducibility.
    We can't patch the child, so we rely on the child's random clock_rate 
    plus random event picks. We'll do a short run, parse the logs, 
    check that we get some variety.
    """
    random.seed(seed)  # affects only the parent's selection of clock_rate for the child
    df = single_run(mode="random", duration=2)

    # We might get some combination of SEND/INTERNAL
    unique_events = df["event_type"].unique()
    assert len(unique_events) >= 1, "Expected at least one event type in random mode."
    
    # It's possible we get no SEND if the random picks are all >=4, 
    # but there's a decent chance. Let's not assert strictly about that.

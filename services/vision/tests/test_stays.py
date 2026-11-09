from vision.stays import StayClock, StaySettings, stay_text


def test_a_seated_customer_keeps_counting_while_seen() -> None:
    clock = StayClock()
    assert clock.update([(1, 0.3, 0.6)], 0.0) == {1: 0.0}
    assert clock.update([(1, 0.3, 0.6)], 125.0) == {1: 125.0}


def test_an_id_switch_nearby_keeps_the_original_start_time() -> None:
    clock = StayClock()
    clock.update([(1, 0.3, 0.6)], 0.0)
    clock.update([(1, 0.3, 0.6)], 300.0)
    assert clock.update([], 301.0) == {}
    assert clock.update([(7, 0.31, 0.61)], 305.0) == {7: 305.0}


def test_the_same_track_returning_keeps_its_time() -> None:
    clock = StayClock()
    clock.update([(2, 0.5, 0.5)], 0.0)
    clock.update([], 10.0)
    assert clock.update([(2, 0.7, 0.7)], 20.0) == {2: 20.0}


def test_far_away_or_long_gone_customers_start_fresh() -> None:
    clock = StayClock(StaySettings(rejoin_s=60.0, rejoin_distance=0.05))
    clock.update([(1, 0.2, 0.2)], 0.0)
    clock.update([], 5.0)
    assert clock.update([(3, 0.8, 0.8)], 10.0) == {3: 0.0}
    clock.update([(4, 0.5, 0.5)], 20.0)
    clock.update([], 21.0)
    assert clock.update([(5, 0.5, 0.5)], 200.0) == {5: 0.0}


def test_two_customers_never_share_one_lost_stay() -> None:
    clock = StayClock()
    clock.update([(1, 0.3, 0.6)], 0.0)
    clock.update([(1, 0.3, 0.6)], 99.0)
    clock.update([], 100.0)
    times = clock.update([(8, 0.3, 0.6), (9, 0.31, 0.6)], 101.0)
    assert sorted(times.values()) == [0.0, 101.0]


def test_stay_text_reads_like_a_person_would_say_it() -> None:
    assert stay_text(30) == "<1 min"
    assert stay_text(25 * 60 + 40) == "25 min"
    assert stay_text(60 * 60) == "1 hour"
    assert stay_text(75 * 60) == "1 hour 15 min"
    assert stay_text(150 * 60) == "2 hours 30 min"

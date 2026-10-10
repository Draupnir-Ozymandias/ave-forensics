from analysis.declared_video_schedule import declared_samples


def test_frequency_ramp_uses_integrated_phase():
    region={'intervals':[{'kind':'pulse','start_us':0,'end_us':1_000_000,
        'frequency_hz':{'kind':'linear','start':2,'end':4},
        'duty_cycle':{'kind':'constant','value':.3},
        'phase_policy':'reset','phase_origin_cycles':0}]}
    gate,cycles=declared_samples(region,4,4)
    # At t=0.5, integral of 2+2t is 1.25 cycles, inside 0.3 duty.
    # Using instantaneous frequency times time would incorrectly turn it off.
    assert gate[2]
    assert cycles[2]==1

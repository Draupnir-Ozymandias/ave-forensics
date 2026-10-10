"""Post-observation reference samples from explicitly declared light curves."""
import math
from fractions import Fraction

import numpy as np

from compare_streaming_video import endpoints


def declared_samples(region, fps, count):
    gate=np.zeros(count,dtype=bool)
    cycle=np.zeros(count,dtype=np.int64)
    origin=Fraction(0)
    after_off=True
    rate=Fraction(str(fps))
    for interval in region['intervals']:
        start=Fraction(interval['start_us'],1_000_000)
        end=Fraction(interval['end_us'],1_000_000)
        duration=end-start
        if interval['kind']=='off':
            after_off=True
            continue
        if after_off or interval['phase_policy']=='reset':
            origin=Fraction(str(interval['phase_origin_cycles']))
        f0,f1=endpoints(interval['frequency_hz'])
        d0,d1=endpoints(interval['duty_cycle'])
        for frame in range(math.ceil(start*rate),min(count,math.ceil(end*rate))):
            t=Fraction(frame,rate)-start
            phase=origin+f0*t+(f1-f0)*t*t/(2*duration)
            gate[frame]=phase%1 < d0+(d1-d0)*t/duration
            cycle[frame]=math.floor(phase)
        origin+=(f0+f1)*duration/2
        after_off=False
    return gate,cycle

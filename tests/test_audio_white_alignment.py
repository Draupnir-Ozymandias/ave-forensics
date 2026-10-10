import numpy as np

from audio_white_alignment import spectrum_peaks


def test_spectrum_distinguishes_audio_carrier_and_slow_amplitude_rhythm():
    rate=4000
    time=np.arange(rate*20)/rate
    envelope=.7+.3*np.sin(2*np.pi*8*time)
    audio=envelope*np.sin(2*np.pi*440*time)
    audible=spectrum_peaks(audio,rate,40,1000,16)
    modulation=spectrum_peaks(envelope,rate,.5,40,20)
    assert audible['peaks'][0]['frequency_hz']==440
    assert modulation['peaks'][0]['frequency_hz']==8

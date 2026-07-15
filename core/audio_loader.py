import librosa


def load_audio(path):
    """
    Loads audio while preserving stereo if present.
    Returns audio array and sample rate.
    """
    y, sr = librosa.load(path, sr=None, mono=False)
    return y, sr

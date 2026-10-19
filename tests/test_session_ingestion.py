import json

from ingest_brainfm_sessions import ingest


def capture(path, records):
    path.write_text(json.dumps({'log':{'entries':[{'response':{'content':{
        'text':json.dumps({'tracks':records})}}}]}}))


def track(filename, title='Example', brightness=.5):
    return {'id':'track-id','name':title,'brightnessLevel':brightness,
            'variations':[{'id':'variation-id','url':filename}]}


def test_session_ingestion_uses_exact_names_and_preserves_existing(tmp_path):
    recordings=tmp_path/'recordings';recordings.mkdir()
    captures=tmp_path/'captures';captures.mkdir()
    (recordings/'exact.mp3').write_bytes(b'recording')
    (recordings/'alias.mp3').write_bytes(b'alias')
    (recordings/'existing.mp3').write_bytes(b'existing')
    existing=recordings/'existing.mp3.provider.json'
    existing.write_text('preserved original')
    capture(captures/'session_20261018.har',[track('exact.mp3','Older')])
    capture(captures/'session_20261019.har',[track('exact.mp3','Latest'),track('existing.mp3')])
    report=ingest(captures,recordings,write=True)
    sidecar=json.loads((recordings/'exact.mp3.provider.json').read_text())
    assert sidecar['provider_track']['title']=='Latest'
    assert sidecar['source_capture']['filename']=='session_20261019.har'
    assert existing.read_text()=='preserved original'
    assert report['unmatched']==[str(recordings/'alias.mp3')]
    assert len(report['written'])==1


def test_invalid_provider_values_do_not_block_valid_records(tmp_path):
    recordings=tmp_path/'recordings';recordings.mkdir()
    captures=tmp_path/'captures';captures.mkdir()
    for name in ('valid.mp3','invalid.mp3'):
        (recordings/name).write_bytes(b'recording')
    capture(captures/'session.har',[track('valid.mp3'),track('invalid.mp3',brightness=1.01)])
    report=ingest(captures,recordings,write=True)
    assert len(report['invalid_metadata'])==1
    assert not (recordings/'invalid.mp3.provider.json').exists()
    assert (recordings/'valid.mp3.provider.json').exists()

"""Ingest exact recording matches from multi-track HAR sessions, preserving sidecars."""
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from core.hashing import sha256_file
from core.media import AUDIO_EXTENSIONS
from provider.brainfm import (
    EXTRACTOR_VERSION, PROVIDER_SIDECAR_SCHEMA_VERSION, ProviderMetadataError,
    _walk, _canonical_track_projection, _projection_signature,
    parse_capture_responses, provider_sidecar_path_for, validate_provider_sidecar,
)


def ingest(captures_root, recordings_root, *, write=False):
    recordings=sorted(p for p in recordings_root.rglob('*')
                      if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS)
    missing=[p for p in recordings if not provider_sidecar_path_for(p).exists()]
    names={p.name for p in missing}
    candidates=defaultdict(list)
    rejected=[]
    for capture in sorted(captures_root.rglob('*.har')):
        try:
            responses,fmt=parse_capture_responses(capture)
        except (ProviderMetadataError,ValueError,UnicodeError) as error:
            rejected.append({'capture':str(capture),'reason':str(error)})
            continue
        found=defaultdict(dict)
        occurrences=Counter()
        for response in responses:
            for track in _walk(response.document):
                if not isinstance(track.get('variations'),list):
                    continue
                for variation in track['variations']:
                    if not isinstance(variation,dict) or variation.get('url') not in names:
                        continue
                    name=variation['url']
                    projection=_canonical_track_projection(track,variation)
                    found[name][_projection_signature(projection)]=projection
                    occurrences[name]+=1
        digest=sha256_file(capture) if found else None
        for name,projections in found.items():
            candidates[name].append({'capture':capture,'format':fmt,
                'document_count':len(responses),'sha256':digest,
                'projections':list(projections.values()),'occurrences':occurrences[name]})
        print(f"Scanned {capture.relative_to(captures_root)}: {len(found)} pending filenames",flush=True)
    report={'written':[],'ready':[],'preserved_existing_count':len(recordings)-len(missing),
            'unmatched':[],'ambiguous':[],'invalid_metadata':[],'unusable_captures':rejected,
            'selection_policy':'latest YYYYMMDD in filename, then same category directory, then lexical path; exact variation filename only'}
    for recording in missing:
        options=candidates.get(recording.name,[])
        if not options:
            report['unmatched'].append(str(recording));continue
        def rank(item):
            dates=re.findall(r'20\d{6}',item['capture'].name)
            relative_parent=item['capture'].parent.relative_to(captures_root)
            same=relative_parent==recording.parent.relative_to(recordings_root)
            return (max(dates,default='00000000'),same,str(item['capture']))
        selected=max(options,key=rank)
        if len(selected['projections'])!=1:
            report['ambiguous'].append(str(recording));continue
        sidecar={
            'provider_metadata_schema_version':PROVIDER_SIDECAR_SCHEMA_VERSION,'provider':'brain.fm',
            'recording':{'filename':recording.name,'hash_algorithm':'sha256',
                         'sha256':sha256_file(recording),'size_bytes':recording.stat().st_size},
            'source_capture':{'filename':selected['capture'].name,'hash_algorithm':'sha256',
                'sha256':selected['sha256'],'format':selected['format'],
                'json_document_count':selected['document_count']},
            'match':{'strategy':'exact_variation_filename',
                'matching_occurrence_count':selected['occurrences'],'unique_canonical_record_count':1},
            **selected['projections'][0],
            'extraction_provenance':{'generator':'provider.brainfm','generator_version':EXTRACTOR_VERSION,
                                     'sensitive_url_policy':'omit_all_provider_urls_and_tokens'},
        }
        try:
            validate_provider_sidecar(sidecar)
        except ProviderMetadataError as error:
            report['invalid_metadata'].append({'recording':str(recording),
                'source_capture':str(selected['capture']),'reason':str(error),
                'provider_measurements':sidecar['provider_measurements']})
            continue
        output=provider_sidecar_path_for(recording)
        report['ready'].append(str(output))
        if write:
            with output.open('x') as destination:
                destination.write(json.dumps(sidecar,indent=2,sort_keys=True)+'\n')
            report['written'].append(str(output))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--captures-root',type=Path,default=Path('captured/brainfm'))
    parser.add_argument('--recordings-root',type=Path,default=Path('samples/brainfm'))
    parser.add_argument('--write',action='store_true')
    parser.add_argument('--report',type=Path,default=Path('artifacts/ingestion/session-ingestion.json'))
    args=parser.parse_args()
    report=ingest(args.captures_root,args.recordings_root,write=args.write)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f"Existing preserved: {report['preserved_existing_count']}; ready: {len(report['ready'])}; "
          f"written: {len(report['written'])}; unmatched: {len(report['unmatched'])}; "
          f"ambiguous: {len(report['ambiguous'])}; invalid metadata: {len(report['invalid_metadata'])}",flush=True)


if __name__=='__main__':
    main()

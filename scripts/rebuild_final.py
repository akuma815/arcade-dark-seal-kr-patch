"""Reproduce this repository's final FBNeo IPS patch set from separate ROM ZIPs."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,zipfile,zlib
ROOT=Path(__file__).resolve().parents[1]
def digest(data):return hashlib.sha256(data).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clone-zip',type=Path,required=True)
    parser.add_argument('--parent-zip',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();output=args.output_dir.resolve()
    manifest=json.loads((ROOT/'docs/rebuild/INPUTS.json').read_text(encoding='utf-8'))
    game=manifest['set'];parent=manifest['parent']
    if output.exists():raise SystemExit('Use a new output folder; existing results are never overwritten.')
    if any(output.is_relative_to(ROOT/p) for p in [game,'common','inputs']):
        raise SystemExit('Output must be outside source input folders.')
    for row in manifest['files']:
        p=ROOT/row['path']
        if p.stat().st_size!=row['bytes'] or digest(p.read_bytes())!=row['sha256']:
            raise SystemExit('Frozen input differs: '+row['path'])
    originals={};payloads=[]
    for name,path,sub in [(game,args.clone_zip,''),(parent,args.parent_zip,'parent')]:
        with zipfile.ZipFile(path) as z:
            expected={r['name']:r for r in manifest['sets'][name]}
            if {i.filename for i in z.infolist() if not i.is_dir()}!=set(expected):
                raise SystemExit('ROM member names differ for '+name)
            for relative,row in expected.items():
                if Path(relative).name!=relative or '/' in relative or '\\' in relative:
                    raise SystemExit('Unsafe ROM member name')
                data=z.read(relative)
                if len(data)!=row['bytes'] or digest(data)!=row['sha256'] or f'{zlib.crc32(data)&0xffffffff:08x}'!=row['crc32']:
                    raise SystemExit('Wrong ROM revision: '+name+'/'+relative)
                originals[relative]=data
                payloads.append((sub,relative,data))
    output.mkdir(parents=True);project=output/'project'
    ignore=shutil.ignore_patterns('__pycache__','*.pyc')
    shutil.copytree(ROOT/game/'workspace',project/game/'workspace',ignore=ignore)
    shutil.copytree(ROOT/'common',project/'common',ignore=ignore)
    shutil.copytree(ROOT/'inputs',project/'inputs')
    for sub,relative,data in payloads:
        target=project/game/'extracted'/sub/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    with (output/'build_translation.log').open('w',encoding='utf-8') as log:
        run=subprocess.run([sys.executable,'-X','utf8','-B',str(project/game/'workspace/scripts/build_translation.py'),
                            '--name','Korean','--no-install','--min-status','approved','--desc',manifest['description']],
                            cwd=project,stdout=log,stderr=subprocess.STDOUT)
    if run.returncode:raise SystemExit('Build failed; see build_translation.log')
    build=project/game/'build/Korean'
    expected={r['name']:r for r in manifest['expectedPatches']}
    if {p.name for p in build.glob('*.ips')}!=set(expected):raise SystemExit('Generated IPS population differs from the release.')
    for name,row in expected.items():
        data=(build/name).read_bytes()
        if len(data)!=row['bytes'] or digest(data)!=row['sha256']:
            raise SystemExit('Generated IPS differs from the published release: '+name)
    sys.path.insert(0,str(project/'common/scripts'))
    from patchutil import ips_apply
    report=json.loads((build/'report.json').read_text(encoding='utf-8'))
    applied=[]
    for name,row in report['roms'].items():
        patched=ips_apply(originals[name],(build/row['ips']).read_bytes())
        if patched!=(build/name).read_bytes():raise SystemExit('IPS application differs from the rebuilt ROM: '+name)
        applied.append({'rom':name,'patch':row['ips'],'targetSHA256':digest(patched)})
    result={'status':'PASS','set':game,'parent':parent,'publicInputsVerified':len(manifest['files']),
            'originalMembersVerified':len(payloads),'publishedIPSMatch':len(expected),'ipsApplyMatchesBuild':applied,
            'installedToEmulator':False,'runtimeVerification':'not performed'}
    (output/'REBUILD_RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('FINAL PASS',game,len(expected),'published IPS files match; apply checks passed',flush=True)

if __name__=='__main__':main()

"""Attach a supported FileUploadControl; saves no account credentials."""
import copy
import json
import sys
import uuid
from pathlib import Path
import requests
from pandaai.config import load_config
from pandaai.factor_core import api_url, make_headers, get_factor, update_factor

root=Path(__file__).resolve().parent
label=sys.argv[1]
state=json.loads((root/f'budget14-{label}-candidates.txt.state.json').read_text())
entry=next(iter(state.values()));fid=entry['factor_id']
c=load_config();headers=make_headers(token=c['token'],uid=c['uid'])
headers.pop('Content-Type',None)
manifests=[]
for filename in json.loads((root/f'budget14-{label}-parts.json').read_text()):
    file=root/filename
    with file.open('rb') as stream:
        response=requests.post(api_url(c,'/quantflow/api/workspace-files/upload'),headers=headers,
            data={'workflow_id':fid,'user_id':c['uid']},
            files={'file':(file.name,stream,'application/vnd.apache.parquet')},timeout=120)
    response.raise_for_status();payload=response.json()
    if not (payload.get('code') in (0,200) or payload.get('success') is True):
        print({'response_keys':list(payload), 'code':payload.get('code'),'message':payload.get('message'), 'detail':payload.get('detail')})
        raise RuntimeError('Upload response requires inspection')
    manifests.append({'name':file.name,'relpath':file.name,'size':file.stat().st_size,'type':'application/vnd.apache.parquet'})
wf=get_factor(c,c['token'],c['uid'],fid)
assert wf and not any(n['type']=='FileUploadControl' for n in wf['nodes']), 'Unexpected existing upload; inspect before resuming'
template=json.loads((root/'budget14-upload-workflow.json').read_text())
code=next(n for n in wf['nodes'] if n['type']=='CodeControl')
lite=wf['litegraph'];lcode=next(n for n in lite['nodes'] if n['type']=='CodeControl')
code['static_input_data']['code']=(root/f'upload_{label}.py').read_text()
lcode['properties']['策略代码']=code['static_input_data']['code']
node=copy.deepcopy(next(n for n in template['nodes'] if n['type']=='FileUploadControl'))
lnode=copy.deepcopy(next(n for n in template['litegraph']['nodes'] if n['type']=='FileUploadControl'))
nid=max(n['id'] for n in lite['nodes'])+1
lid=max([l[0] for l in lite['links']]+[0])+1
uid=str(uuid.uuid4());node.update(uuid=uid,litegraph_id=nid)
node['static_input_data']['uploaded_files']=manifests
lnode['id']=nid;lnode['flags']['uuid']=uid
lnode['properties']['已选文件']=manifests;lnode['outputs'][0]['links']=[lid]
target=next((i for i,a in enumerate(lcode['inputs']) if a.get('fieldName')=='uploaded_files'),None)
if target is None:
    target=len(lcode['inputs']);lcode['inputs'].append({'name':'上传文件','type':'array','link':lid,'fieldName':'uploaded_files','hide':False})
else:lcode['inputs'][target]['link']=lid
wf['nodes'].append(node);lite['nodes'].append(lnode)
wf['links'].append({'uuid':str(uuid.uuid4()),'litegraph_id':lid,'status':1,
    'previous_node_uuid':uid,'next_node_uuid':code['uuid'],'input_field_name':'uploaded_files','output_field_name':'uploaded_files'})
lite['links'].append([lid,nid,0,lcode['id'],target,'array'])
lite.update(last_node_id=nid,last_link_id=lid)
assert update_factor(c,c['token'],c['uid'],fid,wf)==fid
readback=get_factor(c,c['token'],c['uid'],fid)
assert next(n for n in readback['nodes'] if n['type']=='FileUploadControl')['static_input_data']['uploaded_files']==manifests
assert next(n for n in readback['nodes'] if n['type']=='CodeControl')['static_input_data']['code']==(root/f'upload_{label}.py').read_text()
summary={'factor_id':fid,'label':label,'manifest':manifests,'connected':True,'readback_verified':True}
(root/f'budget14-{label}-upload-verified.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))

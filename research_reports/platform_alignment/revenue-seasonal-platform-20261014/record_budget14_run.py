"""Read-only settlement for one run in the explicitly authorized 14-credit round."""
import json
import subprocess
import sys
from pathlib import Path

from pandaai.config import load_config
from pandaai.factor_core import poll_factor_run

root = Path(__file__).resolve().parent
label = sys.argv[1]
entry = next(iter(json.loads((root / f'budget14-{label}-candidates.txt.state.json').read_text()).values()))
info = json.loads(subprocess.check_output(['pandaai-cli', '--json', 'factor_info', entry['factor_id']]))
run_id = info['last_run_id']
config = load_config()
status = poll_factor_run(config, config['token'], config['uid'], run_id, timeout=20)

def redact(value):
    if isinstance(value, dict):
        return {k: '[redacted]' if k.lower() in {
            'uid', 'user_id', 'userid', 'token', 'authorization', 'password', 'phone'
        } else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        for secret in (config['token'], str(config['uid'])):
            value = value.replace(secret, '[redacted]')
    return value

status = redact(status)
(root / f'budget14-{label}-status.json').write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n')
details = []

def scan(value):
    if isinstance(value, dict):
        if value.get('error_detail'):
            details.append(value['error_detail'])
        for child in value.values():
            scan(child)
    elif isinstance(value, list):
        for child in value:
            scan(child)

scan(status)
balance = json.loads(subprocess.check_output(['pandaai-cli', '--json', 'balance']))['balance']['computingPower']
path = root / 'budget14-plan.json'
plan = json.loads(path.read_text())
spent = plan['starting_balance'] - balance
deducted = spent - plan['spent']
record = {'label': label, 'run_id': run_id, 'factor_id': entry['factor_id'],
          'status': status['status'], 'deducted': deducted, 'errors': details}
if entry.get('metrics'):
    record['metrics'] = entry['metrics']
if not any(r['run_id'] == run_id for r in plan['runs']):
    plan['runs'].append(record)
    if not plan['stage2_started']:
        plan['stage1_spent'] += deducted
plan.update(spent=spent, remaining=plan['additional_credit_cap'] - spent, balance_after=balance)
path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'run_id': run_id, 'status': status['status'], 'errors': details,
                  'deducted': deducted, 'spent': spent, 'stage1_spent': plan['stage1_spent'],
                  'remaining': plan['remaining']}, ensure_ascii=False, indent=2))

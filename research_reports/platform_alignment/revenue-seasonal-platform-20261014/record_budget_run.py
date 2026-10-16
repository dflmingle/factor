"""Read-only accounting and diagnostics for an already started budgeted run."""
import json
import subprocess
import sys
from pathlib import Path

from pandaai.config import load_config
from pandaai.factor_core import poll_factor_run

ROOT = Path(__file__).resolve().parent
label = sys.argv[1]
state = json.loads((ROOT / f'budget10-{label}-candidates.txt.state.json').read_text())
name, entry = next(iter(state.items()))
info = json.loads(subprocess.check_output([
    'pandaai-cli', '--json', 'factor_info', entry['factor_id']
]))
(ROOT / f'budget10-{label}-info-after.json').write_text(
    json.dumps(info, ensure_ascii=False, indent=2) + '\n')
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
(ROOT / f'budget10-{label}-status.json').write_text(
    json.dumps(status, ensure_ascii=False, indent=2) + '\n')
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
balance = json.loads(subprocess.check_output(['pandaai-cli', '--json', 'balance']))
safe_balance = {k: balance['balance'][k] for k in (
    'computingPower', 'giftBalance', 'rechargeBalance')}
(ROOT / f'budget10-{label}-balance-after.json').write_text(
    json.dumps(safe_balance, indent=2) + '\n')
plan_path = ROOT / 'budget10-plan.json'
plan = json.loads(plan_path.read_text())
spent = plan['starting_balance'] - safe_balance['computingPower']
deducted = spent - plan['spent']
record = {'step': label, 'name': name, 'factor_id': entry['factor_id'],
          'run_id': run_id, 'status': status['status'], 'error_details': details,
          'balance_after': safe_balance['computingPower'], 'deducted': deducted}
if entry.get('metrics'):
    record['metrics'] = entry['metrics']
if not any(r['run_id'] == run_id for r in plan['runs']):
    plan['runs'].append(record)
plan.update(spent=spent, remaining=plan['additional_credit_cap'] - spent)
plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'run_id': run_id, 'status': status['status'], 'errors': details,
                  'deducted': deducted, 'spent': spent, 'remaining': plan['remaining']},
                 ensure_ascii=False, indent=2))

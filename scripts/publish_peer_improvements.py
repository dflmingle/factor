"""Publish immutable, verified local reconstruction improvements to Git.

No platform calls. The live search directories remain untracked; this exporter
owns only its publication directory. Never pulls, rebases, force-pushes or stages
the user's other work. A matched verification is required, not an updated log.
"""
import argparse
from datetime import datetime
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess


DEFAULT_OUTPUT = 'research_reports/peer_reconstruction/published-improvements-20261016'
SEARCH = 'research_reports/peer_reconstruction/top50-20261013/search_v1'
GROUPS = ('peers_v5_Broster', 'seven_methods_v1')
ENGINE_FILES = ('algorithms.py', 'board_reference.py', 'differentiable.py',
                'engine.py', 'evidence.py', 'financial.py', 'grammar.py',
                'hypotheses.py', 'mcts.py', 'neural.py', 'objective.py',
                'run.py', 'seven_suite.py', 'verify.py')


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def load(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def candidate(path):
    """Reject torn writes, invalid numbers and verification of another candidate."""
    try:
        blob = path.read_bytes()
        row = json.loads(blob)
        best = json.loads(path.with_name('best.json').read_bytes())
        if row.get('valid') is not True or best.get('valid') is not True:
            return None
        fields = ('pool', 'formulas', 'directions', 'cycle', 'search_objective_version')
        if any(row.get(k) != best.get(k) for k in fields):
            return None
        if row.get('target', {}).get('pool_id') != best.get('target', {}).get('pool_id'):
            return None
        if not all(finite(row.get(k)) for k in ('score', 'ic_mae', 'rankic_mae')) or not finite(best.get('score')):
            return None
        if abs(row['score'] - best.get('score', float('inf'))) > 1e-8:
            return None
        actual = row.get('acceptance', {}).get('actual', {})
        if not finite(actual.get('mean_holdings_overlap')) or not row.get('pool'):
            return None
        if not isinstance(row.get('acceptance', {}).get('passed'), bool):
            return None
        if path.read_bytes() != blob:
            return None
        return row
    except (OSError, ValueError, TypeError):
        return None


def metrics(row):
    return dict(score=row['score'], ic_mae=row['ic_mae'], rankic_mae=row['rankic_mae'],
                overlap=row['acceptance']['actual']['mean_holdings_overlap'],
                passed=row['acceptance']['passed'])


def improvement(before, after):
    if after['passed'] and not before['passed']:
        return 'new_reference_threshold_pass'
    # A weighted objective can improve by sacrificing holdings or either IC.
    # Publish only >=1% loss reduction with bounded diagnostic regressions.
    gain = after['score'] - before['score']
    enough = gain >= max(.01 * abs(before['score']), 1e-4)
    stable = (after['overlap'] >= before['overlap'] - .005 and
              after['ic_mae'] <= before['ic_mae'] * 1.02 + 1e-8 and
              after['rankic_mae'] <= before['rankic_mae'] * 1.02 + 1e-8)
    return 'verified_fit_improvement' if enough and stable else None


class Publisher:
    def __init__(self, root, output=DEFAULT_OUTPUT, remote='origin', branch='main'):
        self.root = Path(root).resolve()
        self.output = Path(output)
        if self.output.is_absolute() or '..' in self.output.parts:
            raise ValueError('Publication output must be relative to the repository')
        self.out = self.root / self.output
        self.local = self.out / '.local'
        self.local.mkdir(parents=True, exist_ok=True)
        # A manifest committed with the snapshots is the durable baseline even
        # after a crash, reboot, push failure or migration to another computer.
        self.manifest = load(self.out / 'manifest.json', dict(targets={}))
        self.remote, self.branch = remote, branch

    def git(self, *args, timeout=120, check=True):
        env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
        result = subprocess.run(['git', *args], cwd=self.root, env=env,
                                capture_output=True, text=True, timeout=timeout)
        if check and result.returncode:
            # Do not persist credential-bearing URLs or credential helper output.
            raise RuntimeError('git ' + args[0] + ' failed (exit ' + str(result.returncode) + ')')
        return result.stdout.strip() if check else result

    def engine(self):
        blobs = {name: (self.root / SEARCH / name).read_bytes() for name in ENGINE_FILES}
        hashes = {name: digest(blob) for name, blob in blobs.items()}
        version = digest(json.dumps(hashes, sort_keys=True).encode())
        for name, blob in blobs.items():
            path = self.out / 'engines' / version / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_bytes(blob)
        return version, hashes

    def collect(self):
        events = []
        rows = []
        for group in GROUPS:
            for path in sorted((self.root / SEARCH / group).glob('*/verified_best.json')):
                row = candidate(path)
                if row:
                    rows.append((group, path, row))
        if not rows:
            return []
        # Source changes establish a separate context rather than comparing
        # scores across evaluator versions. Input evidence is hashed as well.
        version, engine_hashes = self.engine()
        market_path = self.root / SEARCH / 'panels_v3_raw_labels/context.json'
        if not market_path.exists():
            raise ValueError('Frozen market context is missing')
        market_blob = market_path.read_bytes()
        for group, path, row in rows:
            peer = row['target']['pool_id']
            evidence = self.root / SEARCH / 'evidence' / (peer + '.json')
            if not evidence.exists():
                continue
            evidence_blob = evidence.read_bytes()
            context = digest(json.dumps(dict(engine=version, evidence=digest(evidence_blob),
                market_context=digest(market_blob),
                objective=row['search_objective_version'], cycle=row['cycle']), sort_keys=True).encode())
            key = group + '/' + peer + '/' + context
            previous = self.manifest['targets'].get(key)
            now = metrics(row)
            reason = improvement(previous['metrics'], now) if previous else 'initial_verified_baseline'
            if not reason:
                continue
            stamp = datetime.now().astimezone().strftime('%Y%m%dT%H%M%S%f%z')
            row_blob = json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
            ident = stamp + '-' + group + '-' + peer + '-' + context[:8] + '-' + digest(row_blob)[:12]
            dest = self.out / 'snapshots' / ident
            dest.mkdir(parents=True, exist_ok=True)
            save(dest / 'verified_candidate.json', row)
            save(dest / 'evidence.json', json.loads(evidence_blob))
            save(dest / 'market_context.json', json.loads(market_blob))
            event = dict(name=row['target']['display_name'], original_rank=row['target']['rank'],
                reason=reason, before=previous['metrics'] if previous else None, after=now,
                context=context, engine_version=version, engine_hashes=engine_hashes,
                source=str(path.relative_to(self.root)), evidence_sha256=digest(evidence_blob),
                candidate_sha256=digest((dest / 'verified_candidate.json').read_bytes()),
                engine_capture='Files on disk at export; existing workers may retain earlier imported modules; no byte-level runtime attestation',
                market_context_sha256=digest(market_blob),
                strict_oos=False, scope='Retrospective inverse-fit proxy; not new alpha or exact private formula identity',
                platform_compute=0, timestamp=stamp)
            save(dest / 'change.json', event)
            self.manifest['targets'][key] = dict(metrics=now, snapshot=str(dest.relative_to(self.out)))
            events.append(event)
        if events:
            save(self.out / 'manifest.json', self.manifest)
            lines = ['# 复刻改善自动归档', '',
                '每5分钟检查；只归档与当前候选一致的验证结果。首次归档是基线，不是新增突破。', '',
                '改进门槛：同源码和证据版本下，损失较上次归档下降至少1%，全持仓重合率下降不超过0.5个百分点，'
                'IC和RankIC MAE分别恶化不超过2%；或由未通过变为通过既定参照验收。', '',
                '每个快照保留公式/AST、独立A与各榜验证、逐期指标、未通过项、源证据、评估源码及SHA256。'
                '这些仍是全部公开日期参与的回顾性拟合代理，没有严格样本外验证。', '',
                '下表为本批归档。完整各路线基线见manifest.json，历史改进见snapshots/*/change.json。', '',
                '|对手|类型|损失|平均持仓重合|参照验收|', '|---|---|---:|---:|---|']
            for event in events:
                m = event['after']
                lines.append(f"|{event['name']}|{event['reason']}|{-m['score']:.6f}|{m['overlap']:.2%}|{m['passed']}|")
            (self.out / 'README.md').write_text('\n'.join(lines) + '\n')
        return events

    def publish(self):
        if self.git('branch', '--show-current') != self.branch:
            raise RuntimeError('Not on configured publication branch')
        self.git('fetch', '--quiet', self.remote, 'refs/heads/' + self.branch)
        remote_tip = self.git('rev-parse', 'FETCH_HEAD')
        relation = self.git('merge-base', '--is-ancestor', remote_tip, 'HEAD', check=False)
        if relation.returncode:
            raise RuntimeError('Remote has commits absent locally; manual integration required')
        staged = self.git('diff', '--cached', '--name-only', '-z').split('\0')
        prefix = str(self.output) + '/'
        if any(p and not p.startswith(prefix) for p in staged):
            raise RuntimeError('Unrelated staged changes present; publication deferred')
        self.git('add', '--', str(self.output))
        dirty = self.git('diff', '--cached', '--quiet', '--', str(self.output), check=False)
        if dirty.returncode == 1:
            self.git('commit', '--only', '-m', 'research: publish verified reconstruction checkpoints',
                     '--', str(self.output))
        elif dirty.returncode:
            raise RuntimeError('Cannot inspect publication diff')
        head = self.git('rev-parse', 'HEAD')
        if head != remote_tip:
            self.git('push', '--quiet', self.remote, 'HEAD:refs/heads/' + self.branch)
        # Remote acknowledgement, rather than a successful local commit, is the
        # receipt. An interrupted push is retried even with no new improvements.
        receipt = self.git('ls-remote', self.remote, 'refs/heads/' + self.branch).split()[0]
        if receipt != head:
            raise RuntimeError('Remote acknowledgement differs from local commit')
        return head

    def tick(self):
        status = dict(updated_at=datetime.now().astimezone().isoformat(), platform_compute=0)
        try:
            events = self.collect()
            head = self.publish()
            status.update(state='synced', commit=head, archived=len(events),
                          improvements=sum(e['reason'] != 'initial_verified_baseline' for e in events))
        except Exception as exc:
            status.update(state='retry_pending', error=type(exc).__name__ + ': ' + str(exc))
        save(self.local / 'status.json', status)
        return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--output', default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    exporter = Publisher(args.root, args.output)
    with (exporter.local / 'publisher.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        status = exporter.tick()
        print(json.dumps(status, ensure_ascii=False))
        if status['state'] != 'synced':
            raise SystemExit(1)


if __name__ == '__main__':
    main()

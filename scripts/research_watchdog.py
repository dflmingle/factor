"""Local research supervision. Never calls a platform or fabricates LLM replies.

Adopts exact command/cwd/executable matches, persists metric high-water marks,
and resumes exited workers. Lack of improvement changes scheduling priority;
it does not kill an otherwise live computation.
"""
import argparse
from datetime import datetime
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import shutil
import socket
import subprocess
import sys
import time


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    tmp.replace(path)


def proc_info(pid):
    try:
        root = Path('/proc')/str(pid)
        stat = (root/'stat').read_text().rsplit(')', 1)[1].split()
        if stat[0] in ('Z', 'X') or root.stat().st_uid != os.getuid():
            return None
        return dict(pid=int(pid), start_ticks=int(stat[19]),
            cpu_ticks=int(stat[11])+int(stat[12]),
            argv=[s.decode() for s in (root/'cmdline').read_bytes().split(b'\0') if s],
            cwd=os.readlink(root/'cwd'), exe=os.readlink(root/'exe'),
            nice=os.getpriority(os.PRIO_PROCESS, int(pid)))
    except (OSError, ValueError, IndexError, UnicodeError):
        return None


def matches(info, job):
    return bool(info and info['cwd']==job['cwd'] and
        info['exe']==str(Path(job['argv'][0]).resolve()) and info['argv'][1:]==job['argv'][1:])


def retry_delay(failures, base=60, maximum=3600):
    return min(maximum, base*2**min(max(failures-1, 0), 10))


def tier(job, state, now):
    if job.get('closed_case'):
        return 'closed_case_background', 19
    age = max(0, now-state.get('last_improvement', now))
    if age >= job.get('deep_stall_seconds', 21600):
        return 'deep_stall', 18
    if age >= job.get('stall_seconds', 7200):
        return 'stalled', 12
    return 'productive', job.get('base_nice', 5)


def observe_metrics(job, state, now):
    previous = state.setdefault('metric_best', {})
    improvements, dates = [], []
    for spec in job.get('metrics', []):
        path = Path(spec['path'])
        obj = read(path)
        if not isinstance(obj, dict):
            continue
        value = obj.get(spec.get('key', 'score'))
        if not isinstance(value, (float, int)) or not math.isfinite(value):
            continue
        if obj.get('valid') is False:
            continue
        key = str(path)+'|'+spec.get('key', 'score')
        dates.append(min(now, path.stat().st_mtime))
        if key not in previous:
            previous[key] = value
            # A newly appearing target is evidence coverage, not a measured
            # improvement over a previously observed value.
        elif value > previous[key] + max(1e-8, abs(previous[key])*1e-9):
            previous[key] = value
            improvements.append(key)
    if 'last_improvement' not in state:
        state['last_improvement'] = max(dates) if dates else now
    if improvements:
        state['last_improvement'] = now
    return improvements


def notify(message):
    address = os.environ.get('NOTIFY_SOCKET')
    if not address:
        return
    if address.startswith('@'):
        address = '\0'+address[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.settimeout(1)
            sock.sendto(message.encode(), address)
    except OSError:
        pass


class Supervisor:
    def __init__(self, config_path):
        self.config_path = Path(config_path).resolve()
        self.out = self.config_path.parent
        self.state_path = self.out/'state.json'
        self.state = read(self.state_path, dict(jobs={}))
        self.boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        self.children = {}

    def event(self, job, action, **details):
        record = dict(time=datetime.now().astimezone().isoformat(), job=job, action=action, **details)
        with (self.out/'events.jsonl').open('a') as stream:
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False)+'\n')

    def set_nice(self, info, desired):
        # Verify start time again immediately before any PID operation.
        current = proc_info(info['pid'])
        if not current or current['start_ticks']!=info['start_ticks']:
            return None
        if current['nice']==desired:
            return desired
        try:
            os.setpriority(os.PRIO_PROCESS, info['pid'], desired)
        except PermissionError:
            # Returning from nice=18 to nice=5 needs CAP_SYS_NICE. On this
            # host passwordless sudo is available; never request a password.
            try:
                result = subprocess.run(['/usr/bin/sudo','-n','/usr/bin/renice','-n',str(desired),'-p',str(info['pid'])],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                if result.returncode:
                    return current['nice']
            except (OSError, subprocess.TimeoutExpired):
                return current['nice']
        except ProcessLookupError:
            return None
        current = proc_info(info['pid'])
        return current['nice'] if current else None

    def tick(self):
        now = time.time()
        config = read(self.config_path)
        if not config or not isinstance(config.get('jobs'), list):
            raise ValueError('Invalid watchdog configuration')
        processes = [p for p in (proc_info(s.name) for s in Path('/proc').iterdir() if s.name.isdigit()) if p]
        free_kb = next(int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
        disk_free_gib = shutil.disk_usage(self.out).free/(1024**3)
        started = 0
        statuses = []
        for job in config['jobs']:
            ident = job['id']
            state = self.state['jobs'].setdefault(ident, {})
            for pid, child in list(self.children.items()):
                if child.poll() is not None:
                    del self.children[pid]
            improvements = observe_metrics(job, state, now)
            if improvements:
                self.event(ident, 'metric_improved', count=len(improvements))
            priority, desired = tier(job, state, now)
            candidates = [p for p in processes if matches(p, job)]
            info = next((p for p in candidates if p['pid']==state.get('pid') and p['start_ticks']==state.get('start_ticks') and state.get('boot_id')==self.boot), None)
            if not info and candidates:
                info = min(candidates, key=lambda p:p['start_ticks'])
                self.event(ident, 'adopted_existing_process', pid=info['pid'])
            status = dict(id=ident, priority=priority, desired_nice=desired,
                no_improvement_seconds=round(max(0,now-state['last_improvement'])),
                data_version=job.get('data_version'), platform_compute=0,
                matching_processes=len(candidates))
            if info:
                previous = (state.get('pid'),state.get('start_ticks'),state.get('boot_id'))
                identity = (info['pid'], info['start_ticks'], self.boot)
                if previous!=identity:
                    state['adopted_at'] = now
                    state['cpu_ticks'] = info['cpu_ticks']
                    state['last_cpu_activity'] = now
                if info['cpu_ticks']!=state.get('cpu_ticks'):
                    state['last_cpu_activity'] = now
                state.update(pid=info['pid'], start_ticks=info['start_ticks'], boot_id=self.boot, cpu_ticks=info['cpu_ticks'])
                pause_identity = [self.boot, info['pid'], info['start_ticks']]
                paused = state.get('disk_paused_identity') == pause_identity
                if disk_free_gib < config.get('pause_below_free_disk_gib',50) and not paused:
                    current = proc_info(info['pid'])
                    if current and current['start_ticks']==info['start_ticks']:
                        state['disk_paused_identity'] = pause_identity
                        # Persist ownership before pausing: a watchdog crash
                        # between the signal and its next tick must not leave
                        # a worker stopped with no durable resume record.
                        atomic(self.state_path,self.state)
                        os.kill(info['pid'], signal.SIGSTOP)
                        paused = True
                        self.event(ident,'paused_low_disk',free_gib=round(disk_free_gib,2))
                elif paused and disk_free_gib >= config.get('resume_above_free_disk_gib',100):
                    os.kill(info['pid'],signal.SIGCONT)
                    state.pop('disk_paused_identity',None)
                    paused = False
                    self.event(ident,'resumed_after_disk_recovery',free_gib=round(disk_free_gib,2))
                if now-state.get('adopted_at',now)>3600:
                    state['failures'] = 0
                actual = self.set_nice(info, desired)
                if state.get('priority')!=priority:
                    self.event(ident, 'priority_changed', tier=priority, desired_nice=desired, actual_nice=actual)
                state['priority'] = priority
                heartbeats = [Path(p).stat().st_mtime for p in job.get('heartbeat_files',[]) if Path(p).exists()]
                heartbeat = max(heartbeats) if heartbeats else None
                status.update(state='running', pid=info['pid'], actual_nice=actual,
                    cpu_idle_seconds=round(max(0,now-state.get('last_cpu_activity',now))),
                    checkpoint_age_seconds=round(max(0,now-heartbeat)) if heartbeat else None)
                if status['cpu_idle_seconds']>3600 and (heartbeat is None or now-heartbeat>14400):
                    status['state'] = 'live_but_no_activity_check_required'
                if paused:status['state'] = 'paused_low_disk'
                statuses.append(status)
                continue
            done = any(read(p,{}).get('done') is True for p in job.get('done_files',[]))
            stopped = any(Path(p).exists() for p in job.get('stop_files',[])) or (self.out/f'STOP.{ident}').exists()
            if done or stopped or not job.get('restart',True):
                status['state'] = 'completed' if done else 'stopped_by_marker' if stopped else 'not_running_restart_disabled'
                statuses.append(status); continue
            if state.get('pid') is not None:
                state['failures'] = state.get('failures',0)+1
                delay = retry_delay(state['failures'])
                state['next_retry'] = now+delay
                self.event(ident, 'worker_exited', old_pid=state['pid'], retry_in_seconds=delay)
                state['pid'] = None
            if now<state.get('next_retry',0):
                status.update(state='retry_backoff', retry_at=state['next_retry'])
            elif free_kb<config.get('min_available_memory_gib',16)*1024*1024 or disk_free_gib<config.get('pause_below_free_disk_gib',50) or started>=config.get('max_starts_per_tick',1):
                status['state'] = 'waiting_for_capacity'
            else:
                env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONUNBUFFERED='1')
                log = self.out/(ident+'.worker.log')
                # Absolute executable, argv list, no shell. A worker restarts
                # from its existing checkpoints and must enforce its own gates.
                with log.open('ab') as stream:
                    child = subprocess.Popen(['/usr/bin/nice','-n',str(desired)]+job['argv'],
                        cwd=job['cwd'], env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                self.children[child.pid] = child
                state.update(pid=child.pid, boot_id=self.boot, adopted_at=now, start_ticks=None,
                             next_retry=0, last_cpu_activity=now)
                started += 1
                status.update(state='starting', pid=child.pid)
                self.event(ident, 'worker_started', pid=child.pid, nice=desired, log=str(log))
            statuses.append(status)
        self.state.update(updated_at=datetime.now().astimezone().isoformat(), watchdog_pid=os.getpid(), boot_id=self.boot)
        atomic(self.state_path,self.state)
        atomic(self.out/'status.json',dict(updated_at=self.state['updated_at'], watchdog_pid=os.getpid(),
            memory_available_gib=round(free_kb/(1024*1024),2),jobs=statuses,
            disk_free_gib=round(disk_free_gib,2),blocked_research=config.get('blocked_research',[]),
            platform_compute=0, scope='process supervision; not a claim of all research jobs being ready'))
        notify('WATCHDOG=1\nSTATUS=Supervising '+str(len(statuses))+' local jobs')
        return statuses


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path)
    parser.add_argument('--once',action='store_true')
    parser.add_argument('--awake-until',help='Sleep inhibitor child: exit normally at this aware ISO timestamp')
    args=parser.parse_args()
    if args.awake_until:
        remaining=max(0,datetime.fromisoformat(args.awake_until).timestamp()-time.time())
        while remaining>0:
            time.sleep(min(remaining,60))
            remaining=max(0,datetime.fromisoformat(args.awake_until).timestamp()-time.time())
        return
    if args.config is None:parser.error('--config is required')
    lock=args.config.resolve().parent/'watchdog.lock'
    lock.parent.mkdir(parents=True,exist_ok=True)
    stream=lock.open('a')
    fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
    supervisor=Supervisor(args.config)
    halted=False
    def stop(*unused):
        nonlocal halted
        halted=True
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    supervisor.tick()
    notify('READY=1\nWATCHDOG=1')
    while not args.once and not halted:
        for unused in range(60):
            if halted:break
            time.sleep(1)
        if not halted:supervisor.tick()
    # Live workers intentionally survive a supervisor restart. Exact identities
    # will be adopted by the next instance, avoiding duplicate computations.


if __name__=='__main__':main()

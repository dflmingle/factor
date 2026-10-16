"""Scheduling semantics, PID matching and local process restart integration."""
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from research_watchdog import Supervisor, matches, observe_metrics, proc_info, retry_delay, tier


class SchedulingTests(unittest.TestCase):
    def test_disk_pressure_pauses_and_recovers_same_worker(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as folder:
            path=Path(folder).resolve();worker=path/'worker.py'
            worker.write_text('import time\ntime.sleep(120)\n')
            argv=[str(Path(sys.executable).resolve()),str(worker)]
            config=path/'config.json';config.write_text(json.dumps(dict(jobs=[dict(id='fixture',argv=argv,cwd=str(path),metrics=[])])))
            child=subprocess.Popen(argv,cwd=path,start_new_session=True)
            supervisor=Supervisor(config)
            try:
                time.sleep(.1)
                with patch('research_watchdog.shutil.disk_usage',return_value=SimpleNamespace(free=40*1024**3)):
                    self.assertEqual(supervisor.tick()[0]['state'],'paused_low_disk')
                self.assertEqual(supervisor.state['jobs']['fixture']['pid'],child.pid)
                supervisor=Supervisor(config)  # Pause ownership survives watchdog restart.
                with patch('research_watchdog.shutil.disk_usage',return_value=SimpleNamespace(free=120*1024**3)):
                    self.assertEqual(supervisor.tick()[0]['state'],'running')
                self.assertEqual(supervisor.state['jobs']['fixture']['pid'],child.pid)
                self.assertNotIn('disk_paused_identity',supervisor.state['jobs']['fixture'])
            finally:
                if child.poll() is None:
                    os.kill(child.pid,signal.SIGCONT)
                    child.terminate();child.wait(timeout=5)

    def test_legacy_search_context_still_constructs_after_new_bundle_support(self):
        search=Path(__file__).resolve().parents[1]/'research_reports/peer_reconstruction/top50-20261013/search_v1'
        sys.path.insert(0,str(search))
        import seven_suite
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as folder:
            root=Path(folder).resolve();public=root/'public';public.mkdir()
            (public/'targets.json').write_text(json.dumps([{'rank':6,'pool_id':'fixture'}]))
            prior=root/'residual_refinement_v1/fixture';prior.mkdir(parents=True)
            (prior/'best.json').write_text(json.dumps({'pool':[{'op':'field','value':'cap'}]}))
            market=SimpleNamespace(panel=lambda expr:None,context={'rule_reference':'fixture'})
            enabled=[]
            objective=SimpleNamespace(enable_A=lambda:enabled.append(True))
            with patch.object(seven_suite,'HERE',root),patch.object(seven_suite,'ROOT',root/'seven'), \
                 patch.object(seven_suite,'PUBLIC',public),patch.object(seven_suite,'Market',return_value=market), \
                 patch.object(seven_suite,'extract',return_value={}), \
                 patch.object(seven_suite.objective,'Objective',return_value=objective), \
                 patch.object(seven_suite.objective,'HERE',root),patch.object(seven_suite.verification,'HERE',root):
                result,workspace=seven_suite.context(6)
                self.assertIs(result,objective)
                self.assertEqual(enabled,[True])
                self.assertFalse(json.loads((workspace/'manifest.json').read_text())['diagnostic_only'])

    def test_stall_tiers(self):
        state={'last_improvement':100}
        self.assertEqual(tier({},state,101),('productive',5))
        self.assertEqual(tier({},state,7300),('stalled',12))
        self.assertEqual(tier({},state,21700),('deep_stall',18))
        self.assertEqual(tier({'closed_case':True},state,101),('closed_case_background',19))

    def test_retry_is_bounded(self):
        self.assertEqual([retry_delay(n) for n in range(1,5)],[60,120,240,480])
        self.assertEqual(retry_delay(99),3600)

    def test_pid_match_requires_executable_arguments_and_cwd(self):
        info=proc_info(os.getpid())
        job={'argv':[str(Path(sys.executable).resolve())]+info['argv'][1:],'cwd':os.getcwd()}
        self.assertTrue(matches(info,job))
        self.assertFalse(matches(info,dict(job,cwd='/')))
        self.assertFalse(matches(info,dict(job,argv=job['argv']+['--different-job'])))

    def test_log_rewrite_does_not_count_as_improvement(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as folder:
            path=Path(folder)/'best.json'
            path.write_text(json.dumps({'score':-20}))
            state={};job={'metrics':[{'path':str(path)}]}
            observe_metrics(job,state,100)
            before=state['last_improvement']
            path.write_text(json.dumps({'score':-20}))
            self.assertEqual(observe_metrics(job,state,10000),[])
            self.assertEqual(state['last_improvement'],before)
            path.write_text(json.dumps({'score':-19}))
            self.assertEqual(len(observe_metrics(job,state,11000)),1)
            self.assertEqual(state['last_improvement'],11000)
            path.write_text(json.dumps({'score':-21}))
            self.assertEqual(observe_metrics(job,state,12000),[])
            self.assertEqual(state['last_improvement'],11000)

    def test_missing_and_invalid_metrics_do_not_fabricate_progress(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as folder:
            path=Path(folder)/'best.json';path.write_text('{broken')
            state={'last_improvement':1}
            job={'metrics':[{'path':str(path)}]}
            self.assertEqual(observe_metrics(job,state,100),[])
            path.write_text(json.dumps({'score':10,'valid':False}))
            self.assertEqual(observe_metrics(job,state,100),[])
            self.assertEqual(state['last_improvement'],1)

    def test_adopts_without_duplicate_and_restarts_after_exit(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as folder:
            path=Path(folder).resolve()
            worker=path/'worker.py';worker.write_text('import time\ntime.sleep(120)\n')
            argv=[str(Path(sys.executable).resolve()),str(worker)]
            job=dict(id='fixture',argv=argv,cwd=str(path),restart=True,metrics=[])
            config=path/'config.json'
            config.write_text(json.dumps(dict(jobs=[job],min_available_memory_gib=0)))
            child=subprocess.Popen(argv,cwd=path,start_new_session=True)
            supervisor=Supervisor(config)
            try:
                time.sleep(.1)
                row=supervisor.tick()[0]
                self.assertEqual(row['state'],'running')
                self.assertEqual(row['pid'],child.pid)
                self.assertFalse(supervisor.children)
                # A new supervisor instance, including stale PID data, adopts
                # the same live process rather than spawning a second one.
                supervisor=Supervisor(config)
                self.assertEqual(supervisor.tick()[0]['pid'],child.pid)
                child.terminate();child.wait(timeout=5)
                self.assertEqual(supervisor.tick()[0]['state'],'retry_backoff')
                self.assertGreater(supervisor.state['jobs']['fixture']['next_retry'],time.time())
                supervisor.state['jobs']['fixture']['next_retry']=0
                self.assertEqual(supervisor.tick()[0]['state'],'starting')
                self.assertEqual(len(supervisor.children),1)
            finally:
                if child.poll() is None:child.terminate();child.wait(timeout=5)
                for fresh in supervisor.children.values():
                    if fresh.poll() is None:fresh.terminate();fresh.wait(timeout=5)

    def test_stop_marker_blocks_restart(self):
        with tempfile.TemporaryDirectory(dir=TEST_ROOT) as folder:
            path=Path(folder).resolve();(path/'STOP.fixture').touch()
            config=path/'config.json';config.write_text(json.dumps(dict(jobs=[dict(id='fixture',
                argv=[str(Path(sys.executable).resolve()),str(path/'absent.py')],cwd=str(path),metrics=[])])))
            supervisor=Supervisor(config)
            self.assertEqual(supervisor.tick()[0]['state'],'stopped_by_marker')
            self.assertFalse(supervisor.children)


TEST_ROOT=Path(__file__).resolve().parents[1]/'research_reports/operations/weekend-watchdog-20261016/test_artifacts'
TEST_ROOT.mkdir(parents=True,exist_ok=True)

if __name__=='__main__':unittest.main()

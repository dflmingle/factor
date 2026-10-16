"""Publication gates and Git retry/isolation tests; all remotes are local fixtures."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from publish_peer_improvements import (Publisher, ENGINE_FILES, SEARCH,
                                       candidate, improvement, metrics, save)


def fixture():
    return dict(valid=True, score=-100., ic_mae=.01, rankic_mae=.005,
        pool=[dict(op='field', value='cap')], formulas=['CAP'], directions=[1],
        cycle=5, search_objective_version='fixture-v1',
        target=dict(pool_id='fixture', display_name='Fixture', rank=6),
        acceptance=dict(passed=False, actual=dict(mean_holdings_overlap=.8), failures=['fixture']))


class Gates(unittest.TestCase):
    def test_tiny_improvement_is_not_published(self):
        before=metrics(fixture());after=dict(before,score=-99.5)
        self.assertIsNone(improvement(before,after))
        after['score']=-98.
        self.assertEqual(improvement(before,after),'verified_fit_improvement')

    def test_ic_or_holdings_sacrifice_rejected(self):
        before=metrics(fixture())
        for change in (dict(overlap=.79),dict(ic_mae=.011),dict(rankic_mae=.006)):
            self.assertIsNone(improvement(before,dict(before,score=-90.,**change)))

    def test_pass_transition_published_separately(self):
        before=metrics(fixture())
        self.assertEqual(improvement(before,dict(before,passed=True)), 'new_reference_threshold_pass')

    def test_rejects_stale_verification_and_nonfinite(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'verified_best.json';row=fixture()
            save(path,row);save(path.with_name('best.json'),row)
            self.assertIsNotNone(candidate(path))
            best=copy.deepcopy(row);best['pool'][0]['value']='close'
            save(path.with_name('best.json'),best)
            self.assertIsNone(candidate(path))
            save(path.with_name('best.json'),row)
            path.write_text('{broken')
            self.assertIsNone(candidate(path))
            bad=copy.deepcopy(row);bad['score']=float('nan')
            path.write_text(json.dumps(bad));self.assertIsNone(candidate(path))


class GitPublication(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.root=self.base/'work';self.root.mkdir();self.remote=self.base/'remote.git'
        self.git('init','-q','-b','main')
        self.git('config','user.email','fixture@example.invalid')
        self.git('config','user.name','Fixture')
        (self.root/'.gitignore').write_text('published/.local/\nresearch_reports/\n')
        (self.root/'user.txt').write_text('original\n')
        self.git('add','.gitignore','user.txt');self.git('commit','-qm','initial')
        subprocess.run(['git','init','--bare','-q',str(self.remote)],check=True)
        self.git('remote','add','origin',str(self.remote));self.git('push','-q','origin','main')
        search=self.root/SEARCH
        for name in ENGINE_FILES:
            p=search/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('# fixture\n')
        self.row=fixture()
        self.path=search/'peers_v5_Broster/fixture/verified_best.json'
        self.write()
        save(search/'evidence/fixture.json',dict(public='fixture'))
        save(search/'panels_v3_raw_labels/context.json',dict(cutoff='20261012',proxy=True))

    def tearDown(self):
        self.temp.cleanup()

    def git(self,*args):
        return subprocess.run(['git',*args],cwd=self.root,capture_output=True,text=True,check=True).stdout.strip()

    def write(self):
        save(self.path,self.row);save(self.path.with_name('best.json'),self.row)

    def publisher(self):
        return Publisher(self.root,'published')

    def test_end_to_end_push_and_unchanged_tick(self):
        (self.root/'user.txt').write_text('user edit remains\n')
        status=self.publisher().tick();self.assertEqual(status['state'],'synced',status)
        self.assertEqual(status['improvements'],0)
        first=status['commit'];self.assertEqual(self.git('ls-remote','origin','refs/heads/main').split()[0],first)
        self.assertEqual((self.root/'user.txt').read_text(),'user edit remains\n')
        self.assertEqual(self.git('show','HEAD:user.txt'),'original')
        status=self.publisher().tick();self.assertEqual(status['commit'],first)
        self.row['score']=-98.;self.write()
        status=self.publisher().tick();self.assertEqual(status['improvements'],1)
        self.assertNotEqual(status['commit'],first)
        self.assertEqual(len(list((self.root/'published/snapshots').iterdir())),2)

    def test_unrelated_staged_work_defers_without_committing_it(self):
        (self.root/'user.txt').write_text('staged edit\n');self.git('add','user.txt')
        first=self.git('rev-parse','HEAD')
        status=self.publisher().tick();self.assertEqual(status['state'],'retry_pending')
        self.assertEqual(self.git('rev-parse','HEAD'),first)
        self.assertIn('user.txt',self.git('diff','--cached','--name-only'))

    def test_failed_push_retries_saved_commit_even_without_new_improvement(self):
        # Fetch remains valid while push fails; next tick must retry that commit.
        self.git('remote','set-url','--push','origin',str(self.base/'missing.git'))
        status=self.publisher().tick();self.assertEqual(status['state'],'retry_pending')
        saved=self.git('rev-parse','HEAD')
        self.git('remote','set-url','--push','origin',str(self.remote))
        status=self.publisher().tick();self.assertEqual(status['state'],'synced',status)
        self.assertEqual(status['commit'],saved)
        self.assertEqual(status['archived'],0)

    def test_changed_context_establishes_baseline_instead_of_improvement(self):
        self.assertEqual(self.publisher().tick()['state'],'synced')
        save(self.root/SEARCH/'evidence/fixture.json',dict(public='different dates'))
        self.row['score']=-50.;self.write()
        status=self.publisher().tick();self.assertEqual(status['state'],'synced')
        self.assertEqual(status['archived'],1);self.assertEqual(status['improvements'],0)

    def test_remote_advance_is_not_overwritten(self):
        clone=self.base/'other'
        subprocess.run(['git','clone','-q','-b','main',str(self.remote),str(clone)],check=True)
        def other(*args):
            return subprocess.run(['git',*args],cwd=clone,capture_output=True,check=True)
        other('config','user.email','fixture@example.invalid');other('config','user.name','Other')
        (clone/'other.txt').write_text('remote work\n');other('add','other.txt');other('commit','-qm','remote work');other('push','-q')
        status=self.publisher().tick();self.assertEqual(status['state'],'retry_pending')
        self.assertIn('manual integration',status['error'])
        self.assertEqual(self.git('log','-1','--format=%s'),'initial')


if __name__=='__main__':
    unittest.main()

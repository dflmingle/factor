"""Read-only source/result inventory; no inference that artifact counts are alpha."""
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
CAT=ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OLD=CAT/'exhaustive_sweep_20261013'
OUT=ROOT/'research_reports/platform_alignment/quant-corpus-coverage-audit-20261015'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    recipes=pd.read_csv(OLD/'all_saved_recipes.csv')
    baseline=pd.read_csv(OLD/'all_saved_results.csv')
    existing=set(zip(baseline.batch,baseline.key,baseline.form.fillna('raw'),baseline.window))
    frames=[];files=[];added=[]
    for output,g in recipes.groupby('output',sort=True):
        directory=ROOT/output
        for filename in ['results.csv','incremental_information.csv']:
            path=directory/filename
            if not path.exists():continue
            frame=pd.read_csv(path);frame['artifact_file']=str(path.relative_to(ROOT));frame['batch']=directory.name
            if 'form' not in frame:frame['form']='raw'
            frame['form']=frame.form.fillna('raw')
            meta=g.drop_duplicates('key').set_index('key')
            for key in ['superseded_unsafe','superseded_semantic','effective_gated','fidelity']:
                frame[key]=frame.key.map(meta[key])
            frame['in_previous_result_index']=[(directory.name,k,f,w) in existing for k,f,w in zip(frame.key,frame.form,frame.window)]
            # Keep original artifact locators; do not turn different proxy versions
            # into one comparable performance ranking or count them as new hypotheses.
            frame['comparison_scope']='artifact index only; inspect source config before cross-batch ranking'
            frames.append(frame)
            files.append(dict(file=str(path.relative_to(ROOT)),rows=len(frame),missing_from_old_index=int((~frame.in_previous_result_index).sum())))
            if filename=='incremental_information.csv':added.extend(frame.loc[~frame.in_previous_result_index,['batch','key','form','window','artifact_file']].to_dict('records'))
    allrows=pd.concat(frames,ignore_index=True)
    allrows.to_csv(OUT/'all_result_artifact_index.csv',index=False)
    pd.DataFrame(files).to_csv(OUT/'artifact_coverage.csv',index=False)
    pd.DataFrame(added).to_csv(OUT/'previously_unindexed_incremental_results.csv',index=False)
    queue=pd.read_csv(OLD/'remaining_source_review_queue.csv')
    # Preserve every unresolved row; priorities identify follow-up checks rather
    # than asserting that any blocked data is now available.
    def priority(row):
        text=' '.join(str(row.get(k,'')) for k in ['semantic_status','semantic_data_requirements','finding'])
        if any(x in text.lower() for x in ['dividend','分红','股息','行业','industry','shareholder','股东']):return 'first_review_financial_industry_or_event_data'
        if any(x in text.lower() for x in ['minute','intraday','tick','分钟','竞价','逐笔']):return 'requires_verified_intraday_data'
        return 'requires_source_or_applicability_review'
    queue['followup_priority']=queue.apply(priority,axis=1)
    queue.to_csv(OUT/'unresolved_source_followup_queue.csv',index=False)
    counts=json.loads((OLD/'progress.json').read_text())
    summary=dict(audit_date='2026-10-15',source_snapshot='2026-10-13 saved registry; not a new reading or rerun',
        corpus_files=counts['corpus_files'],readable_strategy_texts=755,opaque_unread=57,
        saved_spec_rows=len(recipes),unique_nonsuperseded_keys=counts['unique_complete_nonsuperseded_keys'],
        sources_with_direct_tested_atoms=315,unresolved_sources=len(queue),
        old_result_index_rows=len(baseline),result_artifact_rows=len(allrows),incremental_rows_missing_old_index=len(added),
        followup_groups=queue.followup_priority.value_counts().to_dict(),
        latest_accounting_cohort_specs_separately=14,
        no_full_strategy_or_new_cluster_completion_claim=True,new_backtests_this_audit=0,platform_compute_spent=0,
        result_index_is_not_a_cross_version_performance_ranking=True)
    (OUT/'audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()

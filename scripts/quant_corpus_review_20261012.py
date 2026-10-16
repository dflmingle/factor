#!/usr/bin/env python3
"""Per-file evidence ledger with explicit limits on source review and fidelity."""
import csv
import hashlib
import json
import re
from collections import Counter,defaultdict
from pathlib import Path
import pandas as pd
from quant_strategy_factor_catalog_20261012 import read_text, scan
from quant_corpus_local_20261012 import OUT,ROOT,dump

DEST=ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'

PRIMITIVES={
 'market_cap':'small_size','circulating_market_cap':'small_size (total_mv adaptation)',
 'pb_ratio':'book_market','pe_ratio':'earnings_yield','ps_ratio':'sales_yield','pcf_ratio':'cf_yield',
 'roe':'roe','roa':'roa','roic':'roic','roic_ttm':'roic (latest-report proxy)',
 'gross_profit_margin':'gross_margin','gross_income_ratio':'gross_margin','total_asset_turnover_rate':'asset_turnover','asset_turnover':'asset_turnover',
 'net_profit_margin':'net_margin','net_profit_to_total_revenue':'net_margin','net_profit_to_total_operate_revenue_ttm':'net_margin (proxy)',
 'inc_net_profit_year_on_year':'growth_profit','net_profit_growth_rate':'growth_profit','inc_revenue_year_on_year':'growth_sales','operating_revenue_growth_rate':'growth_sales',
 'inc_total_revenue_year_on_year':'growth_sales','inc_operation_profit_year_on_year':'growth_operating_profit',
 'turnover_volatility':'low_turn_std20','net_operate_cash_flow_ttm':'cf_yield','net_operate_cash_flow':'cf_yield (TTM adaptation)',
 'EBIT':'ebit_ev (EBIT/EV proxy; EBIT standalone differs)','ARBR':'arbr26 (AR-BR atom; source learned bounds differ)',
 'gross_profitability':'profitability_ytd_assets','grossprofit_assets':'profitability_ttm_assets',
 'MACD':'macd_scaled (cross-stock adaptation)','VMACD':'volume_macd_scaled (cross-stock adaptation)',
 'cash_to_current_liability':'cash_current_liability (PIT input proxy)',
 'sharpe_ratio_20':'sharpe20_atom (rf0 vendor-input proxy)',
 'sharpe_ratio_120':'sharpe120_atom (rf0 vendor-input proxy)',
}

SPECIAL={
 '球队硬币':'daily behavioural reversal; narrative reconstruction and equal-CS-zscore synthesis',
 '凸显度':'salience/fear; external calc_weight absent, reconstruct paper within-window weights',
 '价格形态':'HighOpen/CloseLow/VwapClose; narrative and final code direction conflict, test labelled variants',
 'CGO':'turnover-survival cost basis, actual raw VWAP converted to qfq; original risk neutralization removed',
 'FScore':'source sign-score structure; cumulative/single-quarter and share-field proxy; scalar denominator bug preserved',
 'FFScore':'financial components partly covered; original thirteen-component model not claimed exactly replicated',
 '黄金律':'intraday momentum + overnight reversal, industry-to-stock adaptation',
 '势的度量':'three source ultimate-score modes, example30/MA5, unsigned strength',
 '趋与势':'normalized path relative to MA; companion source three30-day strength modes tested, index timing not reproduced',
 '再论动量':'raw daily momentum/MA/max atoms tested; full-window time-series OLS in source rejected as lookahead; minute reconstructed bars unavailable',
 '传统反转因子的改进':'10:30-to-15:00 minute return22; unavailable, not substituted with open-to-close',
 '拿的住':'minute volume-weighted volatility stability, cannot replace with daily volatility',
 '股价日内模式':'APM requires120-minute returns; source narrative residual and code regression reversed; unavailable',
 '高频价量':'external cpv.csv and intraday data missing, no claimed daily replication',
 '银行翻倍':'causal250-day PIT mean(PB/ROE); fixed-bank universe transferred to fullA',
}

UNMAPPED={
 'sales_growth':'five-year vendor sales-growth definition not byte-equivalent; source-specific estimate pending',
 'earnings_growth':'vendor growth style / forecast definition unknown',
 'long_term_predicted_earnings_growth':'analyst forecasts unavailable',
 'a_share_holders':'shareholder-count PIT data unavailable',
 'roa_ttm_8y':'eight-year warmup unavailable at first five-year signal',
 'roe_ttm_8y':'eight-year warmup unavailable at first five-year signal',
 'financing_cash_growth_rate':'financing cashflow source-specific growth recipe outside tested core',
 'net_interest_expense':'interest expense mapping not verified in this experiment',
 'non_recurring_gain_loss':'non-recurring earnings mapping not verified',
 'non_operating_net_profit_ttm':'non-operating earnings mapping not verified',
}

def main():
    rows=scan(ROOT/'quant');manifest=json.loads((OUT/'recipe_manifest.json').read_text());by_source=defaultdict(list);by_sha=defaultdict(list)
    for m in manifest:
        for p,h in zip(m['source_paths'],m['source_sha256']):by_source[p].append(m['key']);by_sha[h].append(m['key'])
    canonical={};ledger=[];unmapped=[];dossiers=defaultdict(list)
    for row in rows:
        path=ROOT/row['path'];canonical.setdefault(row['sha256'],row['path'])
        suffix=path.suffix.lower();record={k:row[k] for k in ['path','bytes','title','sha256']}
        record['canonical_identical_file']=canonical[row['sha256']]
        record['tested_source_recipes']=';'.join(sorted(set(by_source[row['path']]+by_sha[row['sha256']])))
        if suffix not in ['.txt','.py','.ipynb']:
            record.update({'review_level':'opaque_binary' if suffix=='.rzrk' else 'supporting_asset_inspected','source_kind':'proprietary_strategy' if suffix=='.rzrk' else 'directory_or_instruction_asset','finding':'rzrk binary has no readable source; not decoded or executed' if suffix=='.rzrk' else 'directory workbook / instructions / notice, no factor formula','primitive_links':'','missing_or_unverified':''})
        else:
            text=read_text(path);lines=text.splitlines()
            attrs=sorted(set(re.findall(r'(?:valuation|indicator|balance|income|cash_flow)\.([A-Za-z][A-Za-z_0-9]*)',text)))
            literals=sorted(set(re.findall(r'[\'"]([A-Za-z][A-Za-z_0-9]{2,80})[\'"]',text)))
            names=set(attrs+literals)
            links=[f'{x} -> {PRIMITIVES[x]}' for x in sorted(names.intersection(PRIMITIVES))]
            missing=[f'{x}: {UNMAPPED[x]}' for x in sorted(names.intersection(UNMAPPED))]
            for m in missing:unmapped.append({'path':row['path'],'issue':m})
            notes=[note for token,note in SPECIAL.items() if token in path.name]
            if re.search(r"['\"](?:[125]m|1min|120m|30m|5min)['\"]|(?:frequency|unit)\s*=\s*['\"](?:minute|min)",text):notes.append('minute/auction execution or features present; daily atoms do not reproduce this full strategy')
            if re.search(r'XGBoost|LightGBM|LSTM|SVM|RandomForest|强化学习|神经网络|机器学习',text,re.I):notes.append('trained model and calibration not replicated; only mapped input atoms tested')
            if any(x in text for x in ['FUND_PORTFOLIO','北向','龙虎榜','STK_ML_QUOTA','STK_SHAREHOLDER','STK_AH_PRICE','融资融券']):notes.append('external PIT/event/holdings dataset dependency; not recreated from OHLCV')
            if re.search(r'ETF|期权|期货|FOF|FoF|基金',path.name,re.I):notes.append('original non-stock universe/timing strategy; only explicitly labelled stock adaptations eligible')
            if not notes:
                notes.append('mapped stock selection atoms and execution/timing constraints identified; full strategy backtest not reproduced' if links else 'timing, pattern, execution or helper code; no separately confirmed new cross-sectional recipe')
            record.update({'review_level':'formula_and_code_checked' if record['tested_source_recipes'] else 'per_file_evidence_and_dependencies_reviewed','source_kind':'strategy_text','finding':' | '.join(notes),'primitive_links':' | '.join(links),'missing_or_unverified':' | '.join(missing)})
            # Retain indexed formula/access/select excerpts with original line
            # numbers for every source; boilerplate is not treated as a factor.
            selected=[]
            for i,line in enumerate(lines,1):
                if re.search(r'valuation\.|indicator\.|balance\.|dependencies\s*=|get_factor_values|factor_list\s*=|g\.factors\s*=|\b(?:rank|rolling|corr|cov|polyfit|linregress)\s*\(|sort_values|order_by|因子构建|计算公式',line,re.I):selected.append((i,line.strip()))
            dossier=[row['path'],record['finding'],'Related atoms: '+record['primitive_links'],'Recipes: '+record['tested_source_recipes']]
            dossier += [f'{i}: {line}' for i,line in selected[:24]]
            dossiers[path.relative_to(ROOT/'quant').parts[0]].extend(dossier+[''])
        ledger.append(record)
    pd.DataFrame(ledger).to_csv(DEST/'source_review.csv',index=False,encoding='utf-8-sig')
    dump(DEST/'source_review.json',ledger);pd.DataFrame(unmapped).to_csv(DEST/'unreproduced_field_recipes.csv',index=False)
    for name,lines in dossiers.items():(DEST/f'{name}_dossier.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    for p in (ROOT/'quant').rglob('*.xlsx'):
        for sheet,df in pd.read_excel(p,sheet_name=None).items():df.to_csv(DEST/f'{p.stem}_{sheet}.csv',index=False,encoding='utf-8-sig')
    dump(DEST/'review_coverage.json',{'files':len(rows),'decoded_strategy_texts':sum(Path(r['path']).suffix.lower() in ['.txt','.py','.ipynb'] for r in rows),'opaque_rzrk':sum(Path(r['path']).suffix.lower()=='.rzrk' for r in rows),'identical_content_groups':len(canonical),'review_levels':dict(Counter(r['review_level'] for r in ledger)),'tested_recipe_count':len(manifest),'unreproduced_field_references':len(unmapped),'all_sources_present_in_ledger':True,'no_claim_all_lines_human_semantically_verified':True,'no_claim_full_strategies_reproduced':True})
    print('source review',len(rows),len(manifest),Counter(r['review_level'] for r in ledger))
    if (DEST/'semantic_reviews.json').exists():
        from quant_corpus_semantic_review_20261012 import refresh
        refresh()

if __name__=='__main__':main()

"""Report both useful falsification and rejected apparent improvements."""
from pathlib import Path
import json
import math
import numpy as np

OUT=Path(__file__).resolve().parent


def read(name):return json.loads((OUT/name).read_text())


def main():
    raw=read('result.json');r=read('accepted_result.json');bank=read('candidate_bank.json')
    verification=read('verification.json');grids=read('grid_audit.json')['rows']
    previous=json.loads((OUT.parent/'star-coin-fidelity-focus-20261016-v6/result.json').read_text())
    baseline=r['baselines'][0];focus=[0,2,7,8]
    # Strict Pareto acceptance is evaluated on ALL single-seat hypotheses,
    # not just the twenty pool finalists exported by the exploratory search.
    diagnostics=[]
    for j in focus:
        c=bank[j]
        def ae(x):return abs(math.log(x['A']['2026-10']['local']['s_i_a']/x['A']['2026-10']['public']['s_i_a']))
        accepted=[b['id'] for b in bank if b['seat']==j and b['rankic_mae']<=c['rankic_mae']+1e-12
            and b['ic_mae']<=c['ic_mae']+1e-12 and ae(b)<=ae(c)+1e-12]
        assert accepted==[j]
        diagnostics.append(dict(seat=j+1,eligible_ids=accepted,tested=len([b for b in bank if b['seat']==j])))
    # Verify that the recomputed control truly is the previous v6 candidate.
    for key in ['rankic_mae','ic_mae','mean_full_overlap','loss']:
        assert abs(baseline[key]-previous['selected'][key])<1e-10
    assert verification['independent_daily_ledger_equal']
    assert [p['top20'] for p in verification['path']]==[p['top20'] for p in r['selected']['path']]
    decision=dict(promoted=False,retained='star-coin-fidelity-focus-20261016-v6',
        baseline_state=baseline['state'],diagnostic_state=r['selected']['state'],
        strict_per_seat_gate='no worsening of A absolute log error, recent RankIC MAE or Pearson MAE',
        all_tested_legs_checked=True,seat_acceptance=diagnostics,
        reason='No new focus-seat hypothesis dominates its control. Better A or recent IC alone is insufficient.',
        platform_compute=0,all_dates_fitted=True,strict_oos=False)
    (OUT/'decision.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2)+'\n')
    m=read('candidate_manifest.json');m.update(status='verified_diagnostic_rejected_for_promotion',
        promoted=False,decision='decision.json',verification='verification.json')
    (OUT/'candidate_manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    table=['|席位|当前A/对手|信号日解释下A/对手|本轮处理结论|','|---:|---:|---:|---|']
    conclusions={0:'现金流代理、排名、符号与结构变体未同时改善A和近期IC',
        2:'活动量/相对量与非加法组合能接近A，但近期IC明显变差',
        7:'A对日期解释高度敏感；先核实公共窗口日期角色，不据此换公式',
        8:'纯市值与金融归一化未同时改善A和近期IC；有效股票范围也有影响'}
    for j in focus:
        g=next(x for x in grids if x['seat']==j+1 and x['offset']==6)
        a=bank[j]['A']['2026-10'];ratio=a['local']['s_i_a']/a['public']['s_i_a']
        table.append(f"|{j+1}|{ratio:.3f}|{g['A_ratio']:.3f}|{conclusions[j]}|")
    gridtable=['|全局信号网格偏移|六个对照席A对数绝对误差均值|','|---:|---:|']
    for offset in [-5,-1,0,1,5,6]:
        e=np.mean([abs(np.log(x['A_ratio'])) for x in grids if x['offset']==offset and x['seat'] not in [1,3,8,9]])
        gridtable.append(f'|{offset:+d}|{e:.6f}|')
    examples=[]
    for ident,label in [(71,'第8席 LOW 均线'),(84,'第9席40日纯市值')]:
        row=bank[ident];old=bank[row['seat']]
        examples.append(f"- {label}：A/对手 {1+old['A']['2026-10']['relative_error']:.3f}→{1+row['A']['2026-10']['relative_error']:.3f}，RankIC MAE {old['rankic_mae']:.5f}→{row['rankic_mae']:.5f}，Pearson MAE {old['ic_mae']:.5f}→{row['ic_mae']:.5f}。公式 `{row['formula']}`。")
    text=f'''# star_coin 大差异专项 v7

本轮完成了逐席五年A筛查、日期角色敏感性、近期IC与池级账本交叉检查。结论是保留v6，没有新组合获得替换资格。新进展是第8席的A对日期解释高度敏感，第9席金融子树的缺失值会改变有效股票范围；不能把所有偏差都归为公式参数。

## 范围与方法

- 规则沿用 `{r['protocol']['rule_reference']}`；未改共享算子、字段配置或旧结果。沪深全A/qfq/total_mv/label1及2018暖机保持。池级账本仍是赛事代理，不冒充正式近五年净超额回测。
- 针对第1、3、8、9席提出{raw['proposed']}个结构假设，含去重后的{raw['unique_legs']-10}条非对照腿，连同10条对照共{raw['unique_legs']}条。每个结构假设都计算完整五年A，不再以少量近期IC先筛掉候选。
- A分别比较方向调整后的IC均值绝对值、ICIR绝对值、胜率，再与逐期近期RankIC/Pearson比较。十席等权，方向和生效日期固定，没有股票代码条件、池权拟合或收益最大化。
- 评估{raw['evaluated_states']}个组合状态。探索性评分、A不恶化门槛和最终严格不恶化门槛分别披露。最后一项是搜索后的保守验收，不是事前独立检验；所有公开快照及五年汇总已用于拟合，没有样本外证据。

## 四个重点席位

{chr(10).join(table)}

“信号日解释”仅为全局日期敏感性：把所有席位公共窗口日期统一当作信号日，仍采用close(t+1)→close(t+cycle+1)，不是给每席挑一个最有利日期。当前正式比较仍沿用v6的收益结束日解释。两列不得混合选优，也不把变化当成公式改善。

## 日期角色诊断

六个对照席位为2、4、5、6、7、10，不以四个困难席位决定日期方案。

{chr(10).join(gridtable)}

偏移+6对应5日周期从“收益结束日”解释切到“信号日”解释。第8席的A比从1.694降至1.017，且六个对照席误差总体下降；这是应进一步核查日期语义的证据，尚不是平台内部日期角色的证明。第1、3席仍约0.286和1.947，不能仅靠日期平移解决。原始逐席IC均值、ICIR、胜率和样本数见grid_audit.json。

## 没有采用的表面改善

{chr(10).join(examples)}

探索性评分选中了第8席LOW方案，但它把原本过高的A进一步推高，因此未采用。A门槛筛出的第9席纯市值方案虽降低A偏差，却增加两种近期IC误差；分榜也从v6的超额-0.76%/稳健+0.66%变成-1.47%/-2.85%，最终同样不替换。accepted_result.json仅记录A门槛后的诊断候选，最终决策以decision.json为准。

最终验收检查全部{raw['unique_legs']}条腿：每个重点席位的A对数绝对误差、近期RankIC误差和Pearson误差均不恶化时，只剩该席原对照。没有以一席改善抵消另一席退化，也不靠综合评分下降宣称复刻成功。

## 第9席缺失值敏感性

同样使用20日均线时，原“市值减金融排名”与纯市值之间，在45个近期面板日平均相差约133.5只有效股票。去掉金融子树会使它们重新进入有效截面；RankIC MAE由0.03131变为0.04155，A只从0.003867变到0.003782。这既有数值变化也有覆盖变化，不能归因于单独一项；更不能因为金融项量纲小就认为可以删除。明细见seat9_missingness.json。

## 复核与保留决定

原v6对照的IC、A和账本在新目录重算，汇总指标与旧值一致。A门槛后第9席诊断候选又从全历史独立计算，与缓存逐值相同；变动公式两次截断重算通过。逐席A、组合持仓、日收益、换手和月度C独立重算一致，见verification.json。该候选仍因拟合退化而不提升为基线。selected_signal_grid_sensitivity.json是它的日期敏感性，不代表已验证平台日期语义。

保留v6及其原始基线，平台算力0，没有创建因子或发起平台回测。下一项应解决的是公共A窗口日期角色和第9席字段缺失覆盖的校准；第1、3席仍需要不同结构或更准确字段的证据，继续在当前子树附近微调没有得到同时吻合的结果。

主要产物：protocol.json、proposals.json、grid_audit.json、candidate_bank.json、seat_frontiers.json、result.json、accepted_result.json、verification.json、seat9_missingness.json、decision.json。
'''
    (OUT/'report.md').write_text(text)
    print(json.dumps(dict(report=str(OUT/'report.md'),promoted=False,seat_acceptance=diagnostics),ensure_ascii=False))


if __name__=='__main__':main()

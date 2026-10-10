from pathlib import Path
import pandas as pd
root=Path('research_reports/platform_alignment'); out=root/'factor-cluster-master-20261010';out.mkdir(exist_ok=True)
rows=[]
old=pd.read_csv(root/'all-factor-cluster-expansion-20260919.clusters.csv',encoding='utf-8-sig')
for _,r in old.iterrows():
 c=r.cluster; status='old/base'
 if c=='N34': status='old correction / independent candidate'
 rows.append(dict(family='B/N',cluster=c,representative=r.representative,members=int(r.record_count),feature='',net_excess_pct=r.representative_platform_net_excess_pct,turnover='',rank_ic=r.representative_platform_rank_ic,max_old_corr='',status=status,source='all-factor-cluster-expansion-20260919.clusters.csv'))
k=pd.read_csv(root/'candidate-new-clusters-20260925/new_clusters_profile.csv')
for _,r in k.iterrows():
 s='K candidate / local screen'
 if r.cluster in ['K008','K021','K015','K020']: s='platform validated; pool edge negative or structural caveat'
 elif r.cluster=='K024': s='platform validated weak; IC p=0.81'
 rows.append(dict(family='K',cluster=r.cluster,representative=r.best_member,members=int(r['size']),feature=r.feature,net_excess_pct=r.best_net*100,turnover=r.turnover_range,rank_ic=r.rank_ic_range,max_old_corr=r.max_known_abs_rho,status=s,source='candidate-new-clusters-20260925/new_clusters_profile.csv'))
# S from Sept30 table
srows=[('S01','VV6-500/VV6-756',3,'volstab long-window ratio',3.09,'local/platform mixed; weak'),('S02','LAMD10/20/0-K5V2',4,'LEGMIX-NEXT composite',12.66,'composite; not standalone new alpha'),('S03','a046 turnoverstd × Alpha191',3,'turnover stability × A191',-0.78,'proxy/local; weak'),('S04','amihud × volstab',2,'illiquidity × vol stability',None,'local/engine; no strong platform proof'),('S05','V4R01/V7-V01',2,'volatility level / volume trend',None,'local/engine; no strong platform proof')]
for c,rep,n,feat,net,status in srows: rows.append(dict(family='S',cluster=c,representative=rep,members=n,feature=feat,net_excess_pct=net,turnover='',rank_ic='',max_old_corr='',status=status,source='new-factor-cluster-20260930/summary.md'))
u=pd.read_csv(root/'recent-factor-clusters-20261010-average-rank-v2/new_unanchored_cluster_summary.csv')
for _,r in u.iterrows(): rows.append(dict(family='U',cluster=r.new_cluster,representative=r.names,members=int(r.members),feature='',net_excess_pct='',turnover='',rank_ic='',max_old_corr='',status='unanchored; platform evidence only for U01/U02 representatives',source='recent-factor-clusters-20261010-average-rank-v2/new_unanchored_cluster_summary.csv'))
rows += [dict(family='correction',cluster='N34',representative='F-GFN-N02-20260916',members=1,feature='book-to-market / operating profit',net_excess_pct=12.274464,turnover=5.64,rank_ic=.0363,max_old_corr=.7249,status='platform aligned; size correlation high; pool edge not evaluated',source='f-gfn-n02-cluster-assignment-20260920.md')]
for c,rep,net,turn,status in [('board', 'F-BI1010-01',-2.42,71.5,'local diagnostic; hold'),('board','F-BI1010-02',.04,68.86,'local diagnostic; hold'),('board','F-BI1010-03',-4.78,80.86,'local diagnostic; hold')]: rows.append(dict(family='board',cluster='BI1010',representative=rep,members=1,feature='board-inspired hypothesis',net_excess_pct=net,turnover=turn,rank_ic='',max_old_corr='',status=status,source='board-inspired-local-reproduction-20261010/summary.md'))
df=pd.DataFrame(rows)
df=df.rename(columns={"net_excess_pct":"saved_representative_net_pct"})
df["platform_net_pct"]=None;df["local_net_pct"]=None
df["nearest_other_cluster"]="";df["nearest_other_rho"]=None;df["correlation_source"]=""
for i,r in df.iterrows():
    if r.family in ["B/N","correction"]: df.loc[i,"platform_net_pct"]=r.saved_representative_net_pct
    elif r.family in ["K","board"]: df.loc[i,"local_net_pct"]=r.saved_representative_net_pct
platform={"K008":(13.71,44.39),"K021":(11.27,36.15),"K015":(10.36,45.72),"K020":(13.28,40.51),"K024":(6.51,55.0),"U01":(6.49,4.82),"U02":(3.96,10.02)}
for c,(net,turn) in platform.items():
    df.loc[df.cluster.eq(c),"platform_net_pct"]=net
    df.loc[df.cluster.eq(c),"platform_turnover_pct"]=turn
    if c.startswith("U"): df.loc[df.cluster.eq(c),"status"]="platform representative validated; not whole-cluster proof"
for _,r in k.iterrows():
    mask=df.cluster.eq(r.cluster)
    df.loc[mask,"nearest_other_cluster"]=r.nearest_known_cluster
    df.loc[mask,"nearest_other_rho"]=r.max_known_abs_rho
    df.loc[mask,"correlation_source"]="K historical max abs against known members; sign unavailable in profile"
n=pd.read_csv(root/"recent-factor-clusters-20261010-average-rank-v2/cluster_nearest_other.csv")
for _,r in n.iterrows():
    mask=df.cluster.eq(r.cluster)
    df.loc[mask,"nearest_other_cluster"]=r.other_cluster
    df.loc[mask,"nearest_other_rho"]=r.rho
    df.loc[mask,"correlation_source"]="Oct saved member max abs daily-mean Spearman; incomplete historical anchors"
df.loc[df.cluster.eq("N34"),"nearest_other_cluster"]="B01"
df.loc[df.cluster.eq("N34"),"nearest_other_rho"]=-.7249016
df.loc[df.cluster.eq("N34"),"correlation_source"]="N34 historical base representatives, 1211 daily dates"
df.to_csv(out/"factor_cluster_master.csv",index=False,encoding="utf-8-sig")
# Keep every historical member and October census record, including excluded
# and duplicate candidates, without claiming that aliases are unique factors.
member_tables=[]
for path in ["all-factor-cluster-expansion-20260919.assignments.csv","candidate-new-clusters-20260925/candidate_new_cluster_assignment.csv","new-factor-cluster-20260930/new_factor_cluster_assignment.csv","recent-factor-clusters-20261010-average-rank-v2/ledger.csv","recent-factor-clusters-20261010-average-rank-v2/inventory.csv"]:
    part=pd.read_csv(root/path);part["inventory_source"]=path;member_tables.append(part)
pd.concat(member_tables,ignore_index=True,sort=False).to_csv(out/"factor_member_inventory.csv",index=False,encoding="utf-8-sig")
# markdown
lines=['# 因子簇统一台账（截至 2026-10-10）','', '这份台账把第一次分簇以来的旧 B/N 簇、9 月 GP K 簇、9 月底 S 簇、10 月 U 簇、N34 修正和榜单启发候选放在同一张表。簇编号来自不同批次，不能直接按编号大小比较。','', '|层级|数量|说明|','|---|---:|---|',f'|旧 B/N 体系|{len(old)}|首次基础簇与后续旧扩展，含历史负收益簇|',f'|K 新簇|{len(k)}|205 条 GP 候选切出的 106 个簇，绝大多数只有本地筛选证据|',f'|S 结构簇|{len(srows)}|9 月 28–30 新挖的 5 个结构簇；多为复合或弱证据|',f'|U 无旧锚点簇|{len(u)}|10 月整理出的 14 个 U 簇；不等于独立 alpha|', '|N34 修正|1|旧记录遗漏后的独立候选，另列防止被 B/N 表覆盖|','|榜单启发|1|3 条候选的统一机制记录，不计作已验证簇|','', '## 当前有平台单因子证据的新增候选','', '|簇|代表|净超额|换手|旧簇最高相关|状态|','|---|---|---:|---:|---:|---|', '|K008|cand0000|13.71%|44.39%|0.333|平台验证；池级边际未通过|','|K021|cand0013-ASIFIX-S18|11.27%|36.15%|0.287|平台验证；优先保留素材|','|K015|cand0003 ×10²⁴|10.36%|45.72%|0.501|平台验证；结构敏感|','|K020|cand0110 ×10²⁷，direction=0|13.28%|40.51%|0.583|平台验证；高危方向翻转|','|N34|F-GFN-N02|12.27%|5.64%|0.725|平台对齐；规模相关偏高|','|K024|cand0026|6.51%|55.0%|—|平台可复现；IC p=0.81|','|U01|1/LOW|6.49%|4.82%|—|平台代表验证；低价储备|','|U02|1/bs_total_cur_assets|3.96%|10.02%|—|平台代表验证；弱证据/规模代理|','', '## 使用状态','', '- **可作为研究素材**：K008、K021、N34、U01；仍需池级边际、近期稳定性和样本外检查。','- **有单因子收益但不宜直接上池**：K015、K020；K020 的平台方向翻转和相关分母结构尤其敏感。','- **弱验证/结构簇**：K024、S01–S05、U02–U14；不能把簇编号当作 alpha 结论。','- **已证伪或仅历史对照**：旧 N 簇中的负收益成员及 BI1010 当前诊断留作历史对照；未做平台验证的 K 候选标记待验证，不能等同证伪。','', '完整逐簇字段见 [factor_cluster_master.csv](factor_cluster_master.csv)，全量成员、重复别名及排除条目见 [factor_member_inventory.csv](factor_member_inventory.csv)。平台与本地收益分别存列，不混排；S 行的收益只代表指定成员证据，不代表全簇。原始证据入口：[旧基础簇](../factor-base-clusters-20260919.md)、[K 簇](../candidate-new-clusters-20260925/summary.md)、[S 簇](../new-factor-cluster-20260930/summary.md)、[U 簇](../recent-factor-clusters-20261010-average-rank-v2/summary.md)、[平台复核](../gp-platform-tests-20260925/verified-candidates-review.md)。']
(out/'summary.md').write_text('\n'.join(lines)+'\n')
print(out/'summary.md',len(df))

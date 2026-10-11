"""Bounded public literature/repository/blog retrieval; never executes remote code."""
from __future__ import annotations
import concurrent.futures
import datetime
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research_reports/literature/fengmao-next-search-20261011'


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.skip += 1
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.skip=max(0,self.skip-1)
    def handle_data(self, data):
        if not self.skip and data.strip(): self.parts.append(data.strip())


def fetch(item):
    name,url,kind = item
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'LocalFactorResearch/1.0','Accept':'application/json,text/html,text/plain'})
        with urllib.request.urlopen(request,timeout=35) as response:
            final_url=response.geturl()
            raw=response.read(2_000_001)
            if len(raw)>2_000_000: raise ValueError('response exceeds 2 MB bound')
        txt=raw.decode('utf8',errors='replace')
        if kind=='openalex':
            data=json.loads(txt)
            result=[]
            for r in data.get('results',[]):
                inv=r.get('abstract_inverted_index') or {}; words={}
                for word,positions in inv.items():
                    for pos in positions: words[pos]=word
                result.append(dict(title=r['title'],year=r.get('publication_year'),doi=r.get('doi'),
                                   url=(r.get('primary_location') or {}).get('landing_page_url'),
                                   abstract=' '.join(words[i] for i in sorted(words))))
            return dict(name=name,url=url,kind=kind,status='ok',works=result)
        if kind=='html':
            parser=TextParser(); parser.feed(txt); txt='\n'.join(parser.parts)
        return dict(name=name,url=url,final_url=final_url,kind=kind,status='ok',text=txt[:120000])
    except Exception as e:
        return dict(name=name,url=url,kind=kind,status='failed',error=str(e))


def main():
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument('--followup',action='store_true'); parser.add_argument('--alpha101',action='store_true')
    args=parser.parse_args(); followup=args.followup
    OUT.mkdir(parents=True,exist_ok=True)
    items=[]
    for q in ('abnormal trading volume stock reversal China',
              'overnight intraday returns momentum reversal',
              'peer firm momentum industry return predictability',
              'volume synchronized probability informed trading stock returns',
              'conditional short term reversal stock liquidity China'):
        url='https://api.openalex.org/works?search='+urllib.parse.quote(q)+'&per-page=6'
        items.append((q,url,'openalex'))
    for repo in ('HanYang544/AlphaCFG','damilab/FaVOR','RL-MLDM/alphagen','microsoft/qlib'):
        items.append((repo,'https://api.github.com/repos/'+repo,'json'))
        items.append((repo+' readme','https://api.github.com/repos/'+repo+'/readme','github_readme'))
    items += [('Quantpedia industry momentum','https://quantpedia.com/strategies/industry-momentum','html'),
              ('Quantpedia high volume','https://quantpedia.com/strategies/volume-return-predictability','html'),
              ('Quantpedia overnight intraday','https://quantpedia.com/overnight-drift-and-intraday-reversal-in-u-s-equity-markets/','html'),
              ('Alphalens documentation','https://quantopian.github.io/alphalens/alphalens.html','html')]
    if followup:
        items=[('Quantpedia overnight blog search','https://quantpedia.com/wp-json/wp/v2/posts?search=overnight&per_page=4','json'),
               ('Quantpedia volume blog search','https://quantpedia.com/wp-json/wp/v2/posts?search=volume&per_page=4','json'),
               ('QuantStart mean reversion blog','https://www.quantstart.com/articles/Basics-of-Statistical-Mean-Reversion-Testing/','html'),
               ('QuantConnect overnight momentum blog','https://www.quantconnect.com/learning/articles/investment-strategy-library/overnight-anomaly','html'),
               ('AlphaCFG semantic grammar','https://api.github.com/repos/HanYang544/AlphaCFG/contents/alphacfg/mcts_core.py','github_readme')]
    if args.alpha101:
        items=[('Alpha101 reference implementation','https://raw.githubusercontent.com/yli188/WorldQuant_alpha101_code/master/101Alpha_code_1.py','text'),
               ('101 Formulaic Alphas bibliography','https://api.openalex.org/works?search=101%20Formulaic%20Alphas&per-page=3','openalex')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        records=list(ex.map(fetch,items))
    import base64
    for r in records:
        if r['status']=='ok' and r['kind']=='github_readme':
            data=json.loads(r.pop('text'))
            r['text']=base64.b64decode(data['content']).decode('utf8',errors='replace')
            r['sha']=data.get('sha'); r['html_url']=data.get('html_url')
    document=dict(retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  remote_code_executed=False,records=records)
    filename='alpha101_sources.json' if args.alpha101 else ('followup_sources.json' if followup else 'sources.json')
    (OUT/filename).write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for r in records:
        print(r['status'],r['name'])
        for w in r.get('works',[]): print(' ',w['year'],w['title'],w.get('doi'))


if __name__=='__main__': main()

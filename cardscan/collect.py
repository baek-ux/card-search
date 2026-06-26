# -*- coding: utf-8 -*-
"""
통신/렌탈 제휴카드 실적별 할인 수집기 (패밀리 A + B)
- 패밀리 A: partner.*/user/sub5014 (다온홈시스, card_Wrap 표) — 8개
- 패밀리 B: /shop/card.php 등 (bilrigo, tbl_CardInfo 문장형) — 5개
출력: card_long_<date>.csv, card_grid_<date>.csv (+ env 있으면 Supabase 적재)
실행: python3 collect.py
"""
import os, re, csv, datetime, json
import requests
from bs4 import BeautifulSoup

WATCHLIST_A = {
    "코웨이":"http://partner.woongjin-shop.co.kr/user/sub5014",
    "SK매직":"http://partner.skmagicmall.kr/user/sub5014",
    "쿠쿠":"http://partner.cuckoo-rental.kr/user/sub5014",
    "LG전자":"http://partner.lg-rentalmall.co.kr/user/sub5014",
    "청호나이스":"http://partner.chunghonais-mall.co.kr/user/sub5014",
    "교원웰스":"http://partner.kyowon-wells.co.kr/user/sub5014",
    "현대큐밍":"http://partner.hyundai-rentalcare.co.kr/user/sub5014",
    "루헨스":"http://partner.ruhens-mall.com/user/sub5014",
}
WATCHLIST_B = {
    "세스코":"https://m.xn--vj4b2zo2z.net/shop/card.php",   # 미검증(같은 CMS 추정)
    "BS렌탈":"https://bs-rental.com/shop/card.php",
    "이니렌탈":"https://direct-rental.net/shop/card.php",
    "렌타나":"https://rh-rental.com/model/card.php",
    "캐리어":"https://xn--sm2bt3a96vf1iixc.com/shop/card.php",
}
GRID = [30,40,50,60,70,80,100,120,150,200]

def parse_lghello(html):
    soup=BeautifulSoup(html,"lxml"); out=[]
    for info in soup.select("div.item-info"):
        st=info.find("strong"); name=clean(st.get_text()) if st else ""
        if not name: continue
        tiers=[]
        for li in info.select("ul.benefit li"):
            m=re.search(r"(\d+)\s*만원\s*사용\s*시\s*([\d,]+)\s*원", clean(li.get_text()))
            if m: tiers.append({"spend":int(m.group(1)),"type":"기본","discount":int(m.group(2).replace(",",""))})
        if tiers: out.append({"card_name":name,"tel":"","apply_url":"","fee":"","tiers":tiers})
    return out

def parse_rentalpay(html):
    soup=BeautifulSoup(html,"lxml"); out=[]
    for h1 in soup.find_all("h1"):
        name=clean(h1.get_text())
        if "카드" not in name: continue
        block=h1.find_parent("li") or h1.parent
        fee=""; detail=""
        for ul in block.select("ul"):
            lis=ul.find_all("li")
            if len(lis)>=2:
                lab=clean(lis[0].get_text())
                if "할인상세" in lab:
                    for br in lis[1].find_all("br"): br.replace_with("\n")
                    detail=lis[1].get_text("\n")
                elif "연회비" in lab:
                    fee=re.sub(r"^연회비\s*","",clean(lis[1].get_text(" ")))[:100]
        tiers=[]
        for ln in [clean(x) for x in detail.split("\n") if clean(x)]:
            m=re.search(r"(\d+)\s*만원\s*이상\s*시?\s*([\d,]+)\s*원", ln)
            if m: tiers.append({"spend":int(m.group(1)),"type":"기본","discount":int(m.group(2).replace(",",""))})
        if tiers: out.append({"card_name":name,"tel":"","apply_url":"","fee":fee,"tiers":tiers})
    return out

def parse_smartrental(html):
    soup=BeautifulSoup(html,"lxml"); out=[]
    for box in soup.select("div.card_cont"):
        cn=box.select_one("[class*='card_name'],[class*='tit'],h2,h3,h4,strong")
        name=clean(cn.get_text())[:40] if cn else ""
        if not name: continue
        tiers=[]; seen=set()
        for p in box.find_all("p"):
            for br in p.find_all("br"): br.replace_with("\n")
            for ln in p.get_text("\n").split("\n"):
                m=re.search(r"(\d+)\s*만원\s*이상\s*사용\s*시[,\s]*매월\s*([\d,]+)\s*원", clean(ln))
                if m:
                    k=(int(m.group(1)),int(m.group(2).replace(",","")))
                    if k in seen: continue
                    seen.add(k); tiers.append({"spend":k[0],"type":"기본","discount":k[1]})
        if tiers: out.append({"card_name":name,"tel":"","apply_url":"","fee":"","tiers":tiers})
    return out

# 단발(C): 사이트별 파서. (이미지형: 유버스/세라젬/바디프랜드 → 수기, 자동수집 불가)
ONEOFFS = [
    ("LG헬로비전","https://rental.lghellovision.net/card/list.do", parse_lghello),
    ("렌탈페이","https://rental-pay.co.kr/kor/mall/card.asp?rentalsacode=livon", parse_rentalpay),
    ("스마트렌탈","https://www.smartrental.co.kr/Event/card.aspx", parse_smartrental),
]

UA = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
def clean(s): return re.sub(r"\s+"," ",(s or "")).strip()

# ── 패밀리 A 파서 (card_Wrap) ─────────────────────────────────
def parse_a(html):
    soup=BeautifulSoup(html,"lxml"); out=[]
    for ul in soup.select("ul.card_Wrap"):
        ct=ul.select_one("li.card_table")
        if not ct: continue
        tel=""; tm=re.search(r"(1[5-9]\d{2}-\d{3,4}|0\d{1,2}-\d{3,4}-\d{4})", ct.get_text(" "))
        if tm: tel=tm.group(1)
        a=ct.select_one("div[style*='float:right'] a[href], p a[href]")
        url=a["href"] if a else ""
        name=""; nd=ct.select_one("div[style*='float:left']")
        if nd: name=clean(nd.get_text())
        if not name:
            p=ct.find("p")
            if p:
                for sp in p.find_all("span"): sp.extract()
                name=clean(p.get_text())
        if not name: continue
        tiers=[]
        for tr in ct.select("table tr"):
            tds=tr.find_all("td",recursive=False)
            if len(tds)==2:
                k,v=clean(tds[0].get_text()),clean(tds[1].get_text())
                if "만원" in k and "원" in v:
                    sm=re.search(r"(\d+)\s*만원",k); dm=re.search(r"([\d,]+)\s*원",v)
                    tiers.append({"spend":int(sm.group(1)) if sm else None,
                                  "type":"프로모션" if "프로모션" in k else "기본",
                                  "discount":int(dm.group(1).replace(",","")) if dm else None})
        det=ct.select_one("td[colspan]"); fee=""
        if det:
            m=re.search(r"연회비\s*[:：]\s*(.+)",det.get_text())
            if m: fee=clean(m.group(1))[:100]
        if tiers: out.append({"card_name":name,"tel":tel,"apply_url":url,"fee":fee,"tiers":tiers})
    return out

# ── 패밀리 B 파서 (tbl_CardInfo) ──────────────────────────────
def parse_b(html):
    soup=BeautifulSoup(html,"lxml"); out=[]
    for li in soup.select("div.tbl_CardInfo li"):
        h=li.find(["h3","h4"]); name=clean(h.get_text()) if h else ""
        if not name: continue
        fee=""; url=""; det=None
        for dl in li.select("dl"):
            dt=dl.find("dt"); dd=dl.find("dd")
            if not dt or not dd: continue
            key=clean(dt.get_text())
            if "할인상세" in key: det=dd
            elif "연회비" in key: fee=clean(dd.get_text())
            elif "발급" in key:
                a=dd.find("a",href=True); url=a["href"] if a else ""
        tel=""; tm=re.search(r"(1[5-9]\d{2}-\d{3,4}|0\d{1,2}-\d{3,4}-\d{4})", li.get_text(" "))
        if tm: tel=tm.group(1)
        tiers=[]
        if det:
            for br in det.find_all("br"): br.replace_with("\n")
            cur=None
            for ln in [clean(x) for x in det.get_text().split("\n") if clean(x)]:
                m=re.search(r"(\d+)\s*만원\s*이상\s*시\s*([\d,]+)\s*원", ln)
                if m:
                    if cur: tiers.append(cur)
                    cur={"spend":int(m.group(1)),"total":int(m.group(2).replace(",","")),"base":None,"promo":None}; continue
                b=re.search(r"기본\s*([\d,]+)\s*원\s*\+\s*프로모션\s*([\d,]+)\s*원", ln)
                if b and cur:
                    cur["base"]=int(b.group(1).replace(",","")); cur["promo"]=int(b.group(2).replace(",",""))
            if cur: tiers.append(cur)
        # 공통 스키마(기본/프로모션 행)로 변환
        rows=[]
        for t in tiers:
            rows.append({"spend":t["spend"],"type":"기본","discount":t["base"] if t["base"] is not None else t["total"]})
            if t["base"] is not None:  # 프로모션 분리 존재 → 프로모션 적용 시 총액
                rows.append({"spend":t["spend"],"type":"프로모션","discount":t["total"]})
        if rows: out.append({"card_name":name,"tel":tel,"apply_url":url,"fee":fee,"tiers":rows})
    return out

def restore(text):
    """크롬 'view-source 저장본'이면 원본 HTML 복원, 아니면 그대로(라이브 fetch는 그대로)."""
    if 'class="line-content"' in text:
        s=BeautifulSoup(text,"lxml"); return "\n".join(td.get_text() for td in s.select("td.line-content"))
    return text

def fetch(url):
    r=requests.get(url,headers=UA,timeout=20); r.encoding=r.apparent_encoding or "utf-8"
    return restore(r.text)

def grid(tiers,kind):
    pts=sorted([(t["spend"],t["discount"]) for t in tiers if t["type"]==kind and t["spend"]])
    def at(g):
        v=None
        for s,d in pts:
            if g>=s: v=d
        return v
    return {g:at(g) for g in GRID}

def main():
    today=datetime.date.today().isoformat()
    longs=[]; grids=[]; errs=[]
    jobs=[("A",b,u,parse_a) for b,u in WATCHLIST_A.items()] \
        +[("B",b,u,parse_b) for b,u in WATCHLIST_B.items()] \
        +[("C",b,u,fn) for b,u,fn in ONEOFFS]
    if True:
        for fam,brand,url,parser in jobs:
            try:
                cards=parser(fetch(url))
                print(f"[OK] {fam} {brand}: {len(cards)}장")
                for c in cards:
                    for t in c["tiers"]:
                        longs.append([today,fam,brand,c["card_name"],c["tel"],c["fee"],
                                      t["spend"],t["type"],t["discount"],c["apply_url"]])
                    bs,pr=grid(c["tiers"],"기본"),grid(c["tiers"],"프로모션")
                    grids.append([today,fam,brand,c["card_name"],c["fee"]]+[bs[g] for g in GRID]+[pr[g] for g in GRID])
            except Exception as e:
                print(f"[FAIL] {fam} {brand}: {e}"); errs.append(brand)
    with open(f"card_long_{today}.csv","w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["date","family","brand","card_name","tel","fee","spend_tier","type","discount","apply_url"]); w.writerows(longs)
    with open(f"card_grid_{today}.csv","w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["date","family","brand","card_name","fee"]+[f"기본_{g}만" for g in GRID]+[f"프로모_{g}만" for g in GRID]); w.writerows(grids)
    print(f"\n저장: card_long_{today}.csv ({len(longs)}행), card_grid_{today}.csv ({len(grids)}장)")
    if errs: print("실패:",errs)
    su,sk=os.environ.get("SUPABASE_URL"),os.environ.get("SUPABASE_KEY")
    if su and sk and longs:
        pl=[dict(zip(["date","family","brand","card_name","tel","fee","spend_tier","type","discount","apply_url"],r)) for r in longs]
        resp=requests.post(f"{su}/rest/v1/card_benefit",
            headers={"apikey":sk,"Authorization":f"Bearer {sk}","Content-Type":"application/json","Prefer":"return=minimal"},
            data=json.dumps(pl,ensure_ascii=False).encode("utf-8"),timeout=30)
        print("Supabase:",resp.status_code, "OK" if resp.status_code<300 else resp.text[:200])
    elif not(su and sk): print("Supabase 미설정 → CSV만")

if __name__=="__main__": main()

# -*- coding: utf-8 -*-
"""
통신/렌탈 제휴카드 실적별 할인 수집기 (패밀리 A + B + 통신 + 아정당 자사)
- 패밀리 A: partner.*/user/sub5014 (card_Wrap 표) — 8개
- 패밀리 B: /shop/card.php 등 (tbl_CardInfo 문장형) — 5개
- 통신: SKB / LG헬로비전 / HCN / 딜라이브 / 유모바일 / SKT / 스카이라이프 / LGU+ / KT
- 아정당: 자사 PLCC(우리/하나) — 홈페이지 이벤트 파싱, 실패 시 폴백
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
            sm=re.search(r"(\d+)\s*만원\s*이상\s*시?", ln)
            if not sm: continue
            spend=int(sm.group(1))
            pb=re.search(r"\(\s*([\d,]+)\s*원\s*\+\s*([\d,]+)\s*원\s*\)\s*([\d,]+)\s*원", ln)
            if pb:  # (기본+프로모션)총액
                tiers.append({"spend":spend,"type":"기본","discount":int(pb.group(1).replace(",",""))})
                tiers.append({"spend":spend,"type":"프로모션","discount":int(pb.group(3).replace(",",""))})
            else:
                dm=re.search(r"([\d,]+)\s*원", ln.split("시",1)[-1])
                if dm: tiers.append({"spend":spend,"type":"기본","discount":int(dm.group(1).replace(",",""))})
        if tiers: out.append({"card_name":name,"tel":"","apply_url":"","fee":fee,"tiers":tiers})
    return out

def parse_smartrental(html):
    soup=BeautifulSoup(html,"lxml"); out=[]
    for box in soup.select("div.card_cont"):
        for br in box.find_all("br"): br.replace_with("\n")
        cur=None
        for el in box.find_all(["h3","p"]):
            if el.name=="h3":
                if cur and cur["tiers"]: out.append(cur)
                cur={"card_name":clean(el.get_text())[:40],"tel":"","apply_url":"","fee":"","tiers":[],"_seen":set()}
                continue
            if not cur: continue
            for m in re.finditer(r"(\d+)\s*만원\s*이상\s*사용\s*시[,\s]*매월\s*([\d.,]+)\s*원", clean(el.get_text(" "))):
                k=(int(m.group(1)),int(re.sub(r"[^\d]","",m.group(2))))
                if k in cur["_seen"]: continue
                cur["_seen"].add(k); cur["tiers"].append({"spend":k[0],"type":"기본","discount":k[1]})
        if cur and cur["tiers"]: out.append(cur)
    for c in out: c.pop("_seen",None)
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
                    sm=re.search(r"(\d+)\s*만원",k); dm=re.search(r"([\d.,]+)\s*원",v)
                    tiers.append({"spend":int(sm.group(1)) if sm else None,
                                  "type":"프로모션" if "프로모션" in k else "기본",
                                  "discount":int(re.sub(r"[^\d]","",dm.group(1))) if dm else None})
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
        rows=[]
        for t in tiers:
            rows.append({"spend":t["spend"],"type":"기본","discount":t["base"] if t["base"] is not None else t["total"]})
            if t["base"] is not None:
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


def tclean(s): return re.sub(r"\s+"," ",(s or "")).strip()

# ── 카드사 추론 ───────────────────────────────────────────────
_ISSUER = [
    ("바로카드","BC바로"),("paybooc","BC바로"),("bc 바로","BC바로"),("bc바로","BC바로"),
    ("파인애플","신한"),("알뜰more","신한"),("알뜰모아","신한"),("신한","신한"),
    ("loca","롯데"),("tello","롯데"),("티다","롯데"),("롯데","롯데"),
    ("삼성","삼성"),("kb","KB국민"),("국민","KB국민"),
    ("하나","하나"),("우리","우리"),("현대","현대"),
    ("nh","NH농협"),("농협","NH농협"),("ibk","기업"),
]
def guess_issuer(name):
    n=(name or "").lower()
    for kw,iss in _ISSUER:
        if kw in n: return iss
    return ""

# ── 할인유형 추론 ─────────────────────────────────────────────
def guess_dtype(text):
    t=text or ""
    if "결제대금" in t or "결제일 할인" in t: return "결제대금차감"
    if "캐시백" in t: return "캐시백"
    if "아이폰" in t: return "아이폰전용"
    return "청구할인"

# ── 금액/구간 정규식 ──────────────────────────────────────────
def won(s):
    m=re.search(r"([\d,]+)\s*원",s or "")
    return int(m.group(1).replace(",","")) if m else None

def kwon(s):
    """한글 금액. '1만 5천 원'→15000, '7천 원'→7000, '2만 원'→20000, '20,000원'→20000"""
    if not s: return None
    man=re.search(r"(\d+)\s*만", s); chon=re.search(r"(\d+)\s*천", s)
    v=0
    if man: v+=int(man.group(1))*10000
    if chon: v+=int(chon.group(1))*1000
    if not man and not chon:
        m=re.search(r"([\d,]+)\s*원", s)
        if m: v=int(m.group(1).replace(",",""))
    return v or None

# ════════════════════════════════════════════════════════════
#  SKB (B world) — 제휴카드 할인 섹션, 실적별 한글금액
# ════════════════════════════════════════════════════════════
def parse_skb(html):
    soup=BeautifulSoup(html,"lxml")
    lines=[tclean(x) for x in soup.get_text("\n").split("\n") if tclean(x)]
    try:
        start=next(i for i,l in enumerate(lines) if l=="제휴카드 할인")
    except StopIteration:
        start=0
    lines=lines[start+1:]

    def is_name(l):
        return l.endswith("카드") and not any(k in l for k in ("할인","실적","연회비","더보기"))

    blocks=[]; cur=None
    for l in lines:
        if is_name(l):
            if cur: blocks.append(cur)
            cur={"name":l,"lines":[]}
        elif cur:
            cur["lines"].append(l)
    if cur: blocks.append(cur)

    pat=re.compile(r"월\s*([0-9만천, ]+?원)(?:\s*~\s*([0-9만천, ]+?원))?\s*(?:결제일\s*)?할인\s*\(전월[^)]*?(\d+)\s*만\s*원\s*이상")
    out=[]
    for b in blocks:
        text=" ".join(b["lines"])
        tiers=[]
        for m in pat.finditer(text):
            low=kwon(m.group(1)); high=kwon(m.group(2)); spend=int(m.group(3))
            if low: tiers.append({"spend":spend,"type":"기본","discount":low,"note":""})
            if high and high!=low:
                tiers.append({"spend":spend,"type":"프로모션","discount":high,"note":""})
        if not tiers: continue
        fm=re.search(r"연회비\s*(.+?)(?:카드 혜택|$)", text)
        fee=tclean(fm.group(1))[:60] if fm else ""
        out.append({"card_name":b["name"],"issuer":guess_issuer(b["name"]),"carrier":"SKB",
                    "disc_type":guess_dtype(text),"category":"통신","fee":fee,
                    "apply_url":"","tiers":tiers,"note":""})
    return out

# ════════════════════════════════════════════════════════════
#  LG헬로비전(홈) — div.benefit_card_area.type02
# ════════════════════════════════════════════════════════════
def parse_lghello_home(html):
    soup=BeautifulSoup(html,"lxml"); out=[]
    for area in soup.select("div.benefit_card_area.type02"):
        nm=area.select_one("p.card_name")
        name=tclean(nm.get_text()) if nm else ""
        if not name: continue
        blob=area.select_one("div.card_infoCon") or area
        for br in blob.find_all("br"): br.replace_with("\n")
        tiers=[]
        for ln in [tclean(x) for x in blob.get_text("\n").split("\n") if tclean(x)]:
            sm=re.search(r"(\d+)\s*만원\s*이상",ln)
            if not sm: continue
            sp=int(sm.group(1))
            pb=re.search(r"기본\s*([\d,]+)\s*원\s*\+\s*프로모션\s*([\d,]+)\s*원",ln)
            tot=won(ln)
            if pb:
                tiers.append({"spend":sp,"type":"기본","discount":int(pb.group(1).replace(",",""))})
                if tot: tiers.append({"spend":sp,"type":"프로모션","discount":tot})
            elif tot:
                tiers.append({"spend":sp,"type":"기본","discount":tot})
        fee=""
        fm=re.search(r"연회비[^\d]*([\d,]+)\s*원",tclean(area.get_text()))
        if fm: fee=fm.group(1)+"원"
        a=area.select_one("dd.bottom a[href], dt a[href]")
        out.append({"card_name":name,"issuer":guess_issuer(name),"carrier":"LG헬로비전",
                    "disc_type":guess_dtype(area.get_text()),"fee":fee,
                    "apply_url":a["href"] if a else "","tiers":tiers,"note":"" if tiers else "구간없음"})
    return out

# ════════════════════════════════════════════════════════════
#  HCN — div.dafault_list.card > ul > li (carrier 혼재: memo2 분기)
# ════════════════════════════════════════════════════════════
def parse_hcn(html):
    soup=BeautifulSoup(html,"lxml"); out=[]
    for box in soup.select("div.dafault_list.card"):
        for li in box.select("ul > li"):
            t=li.select_one("p.tit")
            name=tclean(t.get_text()) if t else ""
            if not name: continue
            memo=li.select_one("p.memo2")
            memo_t=tclean(memo.get_text()) if memo else ""
            carrier="스카이라이프" if "skylife" in memo_t.lower() else "HCN"
            for br in li.find_all("br"): br.replace_with("\n")
            tiers=[]; cardtype=""
            for ln in [tclean(x) for x in li.get_text("\n").split("\n") if tclean(x)]:
                if "해외겸용" in ln: cardtype="해외겸용"
                elif "국내전용" in ln: cardtype="국내전용"
                sm=re.search(r"(\d+)\s*만원\s*이상",ln)
                if not sm: continue
                sp=int(sm.group(1))
                addm=re.search(r"월?\s*([\d,]+)\s*원\s*\+\s*추가\s*([\d,]+)\s*원",ln)
                if addm:
                    base=int(addm.group(1).replace(",",""))
                    add=int(addm.group(2).replace(",",""))
                    typ="기본"+(f"_{cardtype}" if cardtype else "")
                    tiers.append({"spend":sp,"type":typ,"discount":base})
                    tiers.append({"spend":sp,"type":"프로모션"+(f"_{cardtype}" if cardtype else ""),"discount":base+add})
                else:
                    d=won(ln)
                    if d: tiers.append({"spend":sp,"type":"기본"+(f"_{cardtype}" if cardtype else ""),"discount":d})
            fee=""
            fm=re.search(r"연회비[^\d]*([\d,]+)\s*원", tclean(li.get_text()))
            if fm: fee=fm.group(1)+"원"
            a=li.select_one("a.btnS1[href]")
            out.append({"card_name":name,"issuer":guess_issuer(name),"carrier":carrier,
                        "disc_type":guess_dtype(li.get_text()),"fee":fee,
                        "apply_url":a["href"] if a else "","tiers":tiers,"note":"" if tiers else "구간없음"})
    return out

# ════════════════════════════════════════════════════════════
#  딜라이브 — ul.finish_event_list > li (에디터 자유텍스트, 2p)
# ════════════════════════════════════════════════════════════
def parse_dlive(html):
    soup=BeautifulSoup(html,"lxml"); out=[]
    for li in soup.select("ul.finish_event_list > li"):
        dt=li.select_one("dt a") or li.select_one("dt")
        name=tclean(dt.get_text()) if dt else ""
        if not name: continue
        txt=li.select_one("dd.text")
        blob=txt if txt else li
        for br in blob.find_all("br"): br.replace_with("\n")
        body=blob.get_text(" ")
        tiers=[]
        for m in re.finditer(r"(\d+)\s*만원\s*이상[^0-9]*?([\d,]+)\s*원",body):
            tiers.append({"spend":int(m.group(1)),"type":"기본","discount":int(m.group(2).replace(",",""))})
        fee=""
        fm=re.search(r"연회비[^\d]*([\d,]+)\s*원",body)
        if fm: fee=fm.group(1)+"원"
        a=li.select_one("dd.bottom a[href]") or li.select_one("dt a[href]")
        out.append({"card_name":name,"issuer":guess_issuer(name),"carrier":"딜라이브",
                    "disc_type":guess_dtype(body),"fee":fee,
                    "apply_url":a["href"] if a else "","tiers":tiers,"note":"" if tiers else "구간없음"})
    return out

# ════════════════════════════════════════════════════════════
#  유모바일 — card-list(목록) + 팝업테이블(구간) join
# ════════════════════════════════════════════════════════════
def parse_umobile(html):
    soup=BeautifulSoup(html,"lxml")
    listed={}
    for li in soup.select("ul.card-list > li"):
        st=li.select_one("strong"); a=li.select_one("a[href]")
        name=tclean(st.get_text()) if st else ""
        if not name: continue
        bang=li.select_one("p.bang-notice")
        gubun=""
        if a and "gubun=" in a.get("href",""):
            gubun=a["href"].split("gubun=")[-1]
        listed[name]={"range":tclean(bang.get_text()) if bang else "","gubun":gubun}
    tables={}
    for li in soup.select("ul.card-benefit-list > li"):
        st=li.select_one("div.card-desc strong")
        name=tclean(st.get_text()) if st else ""
        if not name: continue
        tiers=[]
        for tr in li.select("table.table-type-04 tbody tr"):
            tds=tr.find_all("td")
            if len(tds)<2: continue
            sm=re.search(r"(\d+)\s*만원",tclean(tds[0].get_text()))
            amt=clean_amount_umobile(tds[1].get_text())
            if sm and amt: tiers+= [{"spend":int(sm.group(1)),**a} for a in amt]
        tables[name]=tiers
    out=[]
    for name,meta in listed.items():
        tiers=tables.get(name,[])
        note="" if tiers else "구간미상(상세필요)"
        out.append({"card_name":name,"issuer":guess_issuer(name),"carrier":"유모바일(LGU+알뜰폰)",
                    "disc_type":"청구할인","fee":"","apply_url":meta["gubun"],
                    "tiers":tiers,"note":note,"range":meta["range"]})
    return out

def clean_amount_umobile(s):
    s=tclean(s); res=[]
    tot=won(s)
    pm=re.search(r"프로모션[^\d]*([\d,]+)\s*원",s)
    addm=re.search(r"([\d,]+)\s*원\s*\+\s*프로모션\s*([\d,]+)\s*원",s)
    if addm:
        base=int(addm.group(1).replace(",","")); promo=int(addm.group(2).replace(",",""))
        res.append({"type":"기본","discount":base})
        res.append({"type":"프로모션","discount":base+promo})
    elif pm and tot:
        promo=int(pm.group(1).replace(",",""))
        res.append({"type":"기본","discount":tot-promo})
        res.append({"type":"프로모션","discount":tot})
    elif tot:
        res.append({"type":"기본","discount":tot})
    return res

# ════════════════════════════════════════════════════════════
#  SKT (T world) — 요금할인형 섹션 alliance_card. 범위(low~high)→기본 2행.
# ════════════════════════════════════════════════════════════
_SKT_DTYPE_OK = ("통신비 할인", "청구 할인")
def parse_skt(html):
    soup=BeautifulSoup(html,"lxml"); out=[]; in_fee=False
    for el in soup.find_all(["em","div"]):
        cls=el.get("class") or []
        if el.name=="em" and "topTitle" in cls:
            in_fee=("요금할인형" in tclean(el.get_text())); continue
        if el.name=="div" and "alliance_card" in cls:
            if not in_fee: continue
            tit=el.select_one("strong.card_tit")
            name=tclean(tit.get_text()) if tit else ""
            if not name: continue
            le=el.select_one("span.tit"); label=tclean(le.get_text()) if le else ""
            if label not in _SKT_DTYPE_OK: continue
            pe=el.select_one("span.price"); price=tclean(pe.get_text()) if pe else ""
            nums=[int(x.replace(",","")) for x in re.findall(r"([\d,]+)",price)]
            if not nums: continue
            low=min(nums); high=max(nums)
            fee=""
            for li in el.select("div.discount_list_info li"):
                t=tclean(li.get_text())
                if "연회비" in t:
                    fee=tclean(re.sub(r"^연회비\s*[:：]?\s*","",t))[:60]; break
            a=el.select_one("div.btn_wrap a[href]")
            tiers=[{"spend":None,"type":"기본","discount":low,"note":"범위"}]
            if high!=low: tiers.append({"spend":None,"type":"기본","discount":high,"note":"범위"})
            out.append({"card_name":name,"issuer":guess_issuer(name),"carrier":"SKT",
                        "disc_type":"청구할인","category":"통신","fee":fee,
                        "apply_url":a["href"] if a else "","tiers":tiers,
                        "note":"범위(T world 요금할인형)"})
    return out

# ════════════════════════════════════════════════════════════
#  LGU+ 본체 — JSON API
# ════════════════════════════════════════════════════════════
def parse_lgu_table(html):
    if not html or len(tclean(html))<15: return []
    soup=BeautifulSoup(html,"lxml"); tiers=[]
    for tbl in soup.select("table.b-table"):
        cap=tclean(tbl.find("caption").get_text()) if tbl.find("caption") else ""
        if "전월실적" not in cap: continue
        head=[tclean(th.get_text()) for th in tbl.select("thead th")]
        spends=[int(m.group(1)) for h in head for m in [re.search(r"(\d+)\s*만원",h)] if m]
        for tr in tbl.select("tbody tr"):
            th=tr.find("th"); rowlab=tclean(th.get_text()) if th else ""
            tds=tr.find_all("td")
            vals=[won(td.get_text()) for td in tds]
            typ="기본"
            if "미이용" in rowlab: typ="할부미이용"
            elif "이용" in rowlab and "할부" in rowlab: typ="할부이용"
            elif "25개월" in rowlab: typ="25개월후"
            if len(tds)==1 and tds[0].get("colspan"):
                for sp in spends:
                    if vals[0] is not None: tiers.append({"spend":sp,"type":typ,"discount":vals[0]})
            else:
                for i,v in enumerate(vals):
                    if v is None: continue
                    sp=spends[i] if i<len(spends) else (spends[-1] if spends else None)
                    tiers.append({"spend":sp,"type":typ,"discount":v})
    return tiers

def parse_lgu(jsontext):
    data=json.loads(jsontext); out=[]
    for it in data:
        name=tclean(it.get("urcBnftNm","")).replace("⁺","+")
        if not name: continue
        rng=tclean(it.get("cprtCardDcntAmtCntn",""))
        pchtml=it.get("pcBnftHtmlCntn","")
        desc=tclean(BeautifulSoup(it.get("bnftMajrDscr",""),"lxml").get_text(" "))
        url=it.get("cardRqstUrl","") or it.get("cardRqstMblUrl","")
        tiers=parse_lgu_table(pchtml)
        dtype=guess_dtype((pchtml or "")+" "+desc)
        cat="통신-할부형" if ("할부" in desc and "스마트" in name) else "통신"
        if not tiers:
            tiers=[{"spend":None,"type":"범위","discount":None,"note":rng}]
            note="범위만(구간HTML없음)"
        else: note=""
        out.append({"card_name":name,"issuer":guess_issuer(name),"carrier":"LGU+",
                    "disc_type":dtype,"category":cat,"fee":"","apply_url":url,
                    "tiers":tiers,"note":note,"range":rng})
    return out

# ════════════════════════════════════════════════════════════
#  KT — savedream 허브 상세 API (card-detail?prodId={uuid})
# ════════════════════════════════════════════════════════════
KT_PRODIDS = [
    "82b3fe07-44ea-4aef-aed9-0d49b54168f7",  # KT Plus 우리카드
    "004cc44c-9ca5-478e-87d1-7c24cb39e9eb",  # KT 36 Plus 우리카드
    "074b0e83-5f28-4167-b895-fea12fdef0a2",  # KT 가족만족 DC 신한카드
    "ed7ee762-199c-4ee6-adc9-ba259a64ee98",  # KT 으랏차차 신한카드
    "c04ea319-cf93-421f-b8fa-20b9f4857c1e",  # KT 삼성카드
    "056b253d-354e-4f10-bbdd-9472ffc5c190",  # KT 현대카드M Edition3(통신할인형 2.0)
    "08851ac2-d5a5-4d2e-8cca-22ba18867f75",  # KT 현대카드M Edition3(청구할인형)
    "8562a613-5694-4fe6-b0d3-caaae416a6b2",  # KT 현대카드M Edition3(청구할인형 2.0)
]
KT_DETAIL_API = "https://savedream.co.kr/api/v1/card-detail?prodId="

_ISSUER_DOMAIN=[("wooricard","우리"),("shinhancard","신한"),("samsungcard","삼성"),
    ("kbcard","KB국민"),("hyundaicard","현대"),("hanacard","하나"),
    ("nonghyup","NH농협"),("paybooc","BC바로"),("lottecard","롯데")]
def _issuer_from_url(url):
    u=(url or "").lower()
    for kw,iss in _ISSUER_DOMAIN:
        if kw in u: return iss
    return ""
def _won_all(s): return [int(x.replace(",","")) for x in re.findall(r"([\d,]+)\s*원", s or "")]

def parse_kt_detail(jsontext):
    obj=json.loads(jsontext)
    if obj.get("responseCode")!="S": return None
    d=obj.get("data") or {}
    name=tclean(d.get("prodNm","")).replace("⁺","+")
    if not name: return None
    url=d.get("prodRedirectUrl","") or d.get("prodOptRedirectUrl","") or ""
    issuer=_issuer_from_url(url)
    soup=BeautifulSoup(d.get("benefitDesc",""),"lxml")
    fee=""
    fseg=soup.get_text()
    if "연회비" in fseg:
        seg=fseg.split("연회비",1)[-1][:60]
        famt=kwon(seg)
        if famt: fee=f"{famt:,}원"
    base={"card_name":name,"issuer":issuer,"carrier":"KT","disc_type":"청구할인",
          "category":"통신","fee":fee,"apply_url":url}
    tbls=soup.select("table")
    if not tbls:
        return {**base,"tiers":[],"note":"표없음(범위만)"}
    tbl=tbls[0]; rows=tbl.select("tr")
    if not rows: return {**base,"tiers":[],"note":"표없음"}
    header=[tclean(c.get_text()) for c in rows[0].find_all(["td","th"])]
    ncol=len(header)
    col={"base":None,"total":None}
    has_period=any(("할인" in h and "기간" in h) for h in header)
    for i,h in enumerate(header):
        if h.strip().startswith("기본"): col["base"]=i
        if "합계" in h or h.strip().startswith("총"): col["total"]=i
    if ncol>=5 or has_period or col["base"] is None:
        reason="복합표(수기확인)" if (ncol>=5 or has_period) else "표인식실패(수기확인)"
        return {**base,"tiers":[],"note":f"{reason} 열{ncol}"}
    tiers=[]; has_range=False
    for tr in rows[1:]:
        cells=[tclean(c.get_text()) for c in tr.find_all(["td","th"])]
        if len(cells)<2: continue
        sm=re.search(r"(\d+)\s*만\s*원?",cells[0])
        if not sm: continue
        sp=int(sm.group(1)); joined=" ".join(cells)
        if "~" in joined: has_range=True
        def cw(idx):
            if idx is None or idx>=len(cells): return None
            w=_won_all(cells[idx]); return w[0] if w else None
        b=cw(col["base"]); t=cw(col["total"])
        if b: tiers.append({"spend":sp,"type":"기본","discount":b})
        if t: tiers.append({"spend":sp,"type":"프로모션","discount":t})
    note="금액범위포함(확인권장)" if has_range else ("" if tiers else "구간없음")
    return {**base,"tiers":tiers,"note":note}

def collect_kt():
    import time
    out=[]
    for pid in KT_PRODIDS:
        try:
            raw=fetch_json(KT_DETAIL_API+pid)
            print(f"  [KT-DEBUG] {pid[:8]} len={len(raw)} head={raw[:80]!r}")
            c=parse_kt_detail(raw)
            if c: out.append(c)
        except Exception as e:
            print(f"  [KT] {pid[:8]} 실패: {e}")
        time.sleep(0.3)
    return out

# ════════════════════════════════════════════════════════════
#  스카이라이프 — SPA(__NEXT_DATA__). 자동수집 리스크 커서 하드코딩.
# ════════════════════════════════════════════════════════════
SKYLIFE_CARDS = [
    ("스카이라이프 신한카드",       "신한",   [(30, 15000, None), (70, 16000, None), (120, 20000, None)]),
    ("KT스카이라이프 KB카드",       "KB국민", [(30, 15000, None), (70, 17000, None)]),
    ("LOCA x special SE",         "롯데",   [(30, 15000, None), (70, 17000, None), (150, 25000, None)]),
    ("스카이라이프 하나카드",       "하나",   [(30, 13000, None)]),
    ("KT 마이알뜰폰 BC 바로카드",   "BC바로", [(30, 12000, None), (70, 17000, None)]),
]

def parse_skylife(html=None):
    out=[]
    for name,issuer,tiers in SKYLIFE_CARDS:
        rows=[]
        for spend,base,promo in tiers:
            rows.append({"spend":spend,"type":"기본","discount":base,"note":""})
            if promo:
                rows.append({"spend":spend,"type":"프로모션","discount":promo,"note":""})
        out.append({"card_name":name,"issuer":issuer,"carrier":"스카이라이프",
                    "disc_type":"청구할인","category":"통신","fee":"","apply_url":"",
                    "tiers":rows,"note":"수기확인(2026-06-29)"})
    return out

# ════════════════════════════════════════════════════════════
#  아정당 자사 PLCC(우리/하나) — 홈페이지 이벤트 파싱, 실패 시 폴백
#  리스트(/card/event/list)에서 "아정당 OO카드" → detail sn 찾고
#  detail 표에서 (전월실적, 혜택합계) 파싱. discount=혜택 합계(기본+프로모션).
#  실패/미게시/이상값이면 AJD_FALLBACK 사용 → 자사카드 절대 누락 안 됨.
#  main에서 category "통신"+"렌탈" 2벌 적재(carrier="아정당" 통일).
# ════════════════════════════════════════════════════════════
AJD_LIST_URL   = "https://www.ajd.co.kr/card/event/list"
AJD_DETAIL_URL = "https://www.ajd.co.kr/card/event/detail/"

# 폴백(2026-07-01 계약 확정본). 하나카드는 당분간 이벤트 미게시 → 상시 이 값.
AJD_FALLBACK = {
    "우리카드": {"fee":"23,000원","apply_url":AJD_LIST_URL,
               "tiers":[{"spend":30,"discount":18000},
                        {"spend":70,"discount":21000},
                        {"spend":160,"discount":26000}]},
    "하나카드": {"fee":"29,000원","apply_url":AJD_LIST_URL,
               "tiers":[{"spend":30,"discount":15000},
                        {"spend":120,"discount":20000}]},
}
AJD_ISSUER = {"우리카드":"우리","하나카드":"하나"}

def _ajd_find_sn(list_html, cardword):
    soup=BeautifulSoup(list_html,"lxml")
    for a in soup.select("a[href*='/card/event/detail/']"):
        txt=tclean(a.get_text())
        if "아정당" in txt and cardword in txt:
            m=re.search(r"/detail/(\d+)", a.get("href",""))
            if m: return m.group(1)
    return None

def _ajd_parse_detail(detail_html):
    soup=BeautifulSoup(detail_html,"lxml")
    tbl=soup.find("table")
    if not tbl: return None
    tds=[tclean(c.get_text()) for c in tbl.select("td")]
    tiers=[]
    for i,c in enumerate(tds):
        sm=re.search(r"(\d+)\s*만원\s*이상", c)
        if not sm: continue
        row_vals=[won(tds[j]) for j in range(i, min(i+4, len(tds)))]
        row_vals=[v for v in row_vals if v]
        if row_vals:
            tiers.append({"spend":int(sm.group(1)), "discount":row_vals[-1]})
    fee=""
    m=re.search(r"연회비[^\d]{0,40}?([\d,]+)\s*원", soup.get_text(), re.S)
    if m: fee=m.group(1)+"원"
    if tiers and all(t["discount"] and t["discount"]>0 for t in tiers):
        return {"fee":fee, "tiers":tiers}
    return None

def collect_ajd():
    results={}
    list_html=""
    try:
        list_html=fetch(AJD_LIST_URL)
    except Exception as e:
        print(f"  [아정당] 리스트 fetch 실패 → 전체 폴백: {e}")

    for card in ("우리카드","하나카드"):
        parsed=None
        if list_html:
            try:
                sn=_ajd_find_sn(list_html, card)
                if sn:
                    dhtml=fetch(AJD_DETAIL_URL+sn)
                    parsed=_ajd_parse_detail(dhtml)
                    if parsed: parsed["apply_url"]=AJD_DETAIL_URL+sn
            except Exception as e:
                print(f"  [아정당] {card} 상세 파싱 실패 → 폴백: {e}")
        if parsed:
            results[card]={**parsed,"_src":"파싱"}
        else:
            fb=AJD_FALLBACK[card]
            results[card]={"fee":fb["fee"],"apply_url":fb["apply_url"],
                           "tiers":[dict(t) for t in fb["tiers"]],"_src":"폴백"}

    out=[]
    for card,info in results.items():
        rows=[{"spend":t["spend"],"type":"기본","discount":t["discount"]} for t in info["tiers"]]
        note = "자사(파싱)" if info["_src"]=="파싱" else "자사(고정값)"
        out.append({"card_name":f"아정당 {card}","issuer":AJD_ISSUER[card],
                    "carrier":"아정당","disc_type":"청구할인","fee":info["fee"],
                    "apply_url":info["apply_url"],"tiers":rows,"note":note})
    return out

# ════════════════════════════════════════════════════════════
#  통신 job 목록 (carrier, url, parser, mode)
# ════════════════════════════════════════════════════════════
TEL_JOBS = [
    ("SKT",          "https://www.tworld.co.kr/poc/html/product/TS3.3.3T.html", parse_skt,           "html"),
    ("SKB",          "https://www.bworld.co.kr/event/page.do?menu_id=B06000000", parse_skb,           "html"),
    ("스카이라이프",   "https://www.skylife.co.kr/benefit/card?tab=shinhan",       parse_skylife,       "html"),
    ("LG헬로비전",    "https://www.lghellovision.net/benefits/card/cardDiscountList.do", parse_lghello_home, "html"),
    ("HCN",          "https://www.hcn.co.kr/www/event/event3.jsp",               parse_hcn,           "html"),
    ("딜라이브",      "https://www.dlive.kr/front/join/join/DiscountAction.do?method=view", parse_dlive, "html"),
    ("유모바일",      "https://www.uplusumobile.com/product/guide/benefitCopCard", parse_umobile,       "html"),
    ("LGU+",         "https://m.lguplus.com/uhdc/fo/prdv/dcntbnft/v1/cprt-card-dcnt-list?billDcntYn=&bnftDcntYn=", parse_lgu, "json"),
    # KT savedream 허브는 main에서 collect_kt()로 별도 처리
    # 아정당 자사는 main에서 collect_ajd()로 별도 처리
]

def fetch_json(url):
    if "savedream.co.kr" in url:
        ref={"Referer":"https://product.kt.com/","Origin":"https://product.kt.com"}
    elif "lguplus.com" in url:
        ref={"Referer":"https://m.lguplus.com/"}
    else:
        ref={}
    r=requests.get(url,headers={**UA,"Accept":"application/json, text/plain, */*",**ref},timeout=20)
    r.encoding=r.apparent_encoding or "utf-8"
    return r.text

def dlive_page2(url):
    try:
        r=requests.post(url,headers=UA,data={"currentPage":"2","linesPerPage":"5"},timeout=20)
        r.encoding=r.apparent_encoding or "utf-8"
        return restore(r.text)
    except Exception:
        return ""

def main():
    today=datetime.date.today().isoformat()
    longs=[]; grids=[]; errs=[]; report=[]

    # ── 1) 렌탈 (기존) ──────────────────────────────────────
    rental_jobs=[("A",b,u,parse_a) for b,u in WATCHLIST_A.items()] \
        +[("B",b,u,parse_b) for b,u in WATCHLIST_B.items()] \
        +[("C",b,u,fn) for b,u,fn in ONEOFFS]
    for fam,brand,url,parser in rental_jobs:
        try:
            cards=parser(fetch(url))
            report.append(("렌탈",brand,len(cards),"OK"))
            for c in cards:
                iss=guess_issuer(c["card_name"])
                for t in c["tiers"]:
                    longs.append([today,"렌탈",brand,"",iss,c["card_name"],c.get("tel",""),c.get("fee",""),
                                  t["spend"],t["type"],t["discount"],"청구할인",c.get("apply_url",""),t.get("note","")])
                bs,pr=grid(c["tiers"],"기본"),grid(c["tiers"],"프로모션")
                grids.append([today,"렌탈",brand,c["card_name"],c.get("fee","")]+[bs[g] for g in GRID]+[pr[g] for g in GRID])
        except Exception as e:
            report.append(("렌탈",brand,0,f"FAIL: {e}")); errs.append(("렌탈",brand))

    # ── 2) 통신 ─────────────────────────────────────────────
    for carrier,url,parser,mode in TEL_JOBS:
        try:
            raw=fetch_json(url) if mode=="json" else fetch(url)
            cards=parser(raw)
            if carrier=="딜라이브":
                p2=dlive_page2(url)
                if p2:
                    try: cards += parser(p2)
                    except Exception: pass
            report.append(("통신",carrier,len(cards),"OK" if cards else "0건(selector확인)"))
            for c in cards:
                cat=c.get("category","통신")
                for t in c["tiers"]:
                    longs.append([today,cat,carrier,carrier,c.get("issuer",""),c["card_name"],"",c.get("fee",""),
                                  t.get("spend"),t["type"],t.get("discount"),c.get("disc_type","청구할인"),
                                  c.get("apply_url",""),t.get("note","") or c.get("note","")])
                if any(t.get("spend") for t in c["tiers"]):
                    bs,pr=grid(c["tiers"],"기본"),grid(c["tiers"],"프로모션")
                    grids.append([today,cat,carrier+"/"+c["card_name"],c["card_name"],c.get("fee","")]
                                 +[bs[g] for g in GRID]+[pr[g] for g in GRID])
        except Exception as e:
            report.append(("통신",carrier,0,f"FAIL: {e}")); errs.append(("통신",carrier))

    # ── 2-b) KT (savedream 허브 다회 호출) ───────────────────
    try:
        kt_cards=collect_kt()
        n_auto=sum(1 for c in kt_cards if c["tiers"])
        report.append(("통신","KT",len(kt_cards),f"OK (구간자동 {n_auto}/{len(kt_cards)}, 나머지 수기플래그)"))
        for c in kt_cards:
            for t in c["tiers"]:
                longs.append([today,"통신","KT","KT",c.get("issuer",""),c["card_name"],"",c.get("fee",""),
                              t.get("spend"),t["type"],t.get("discount"),c.get("disc_type","청구할인"),
                              c.get("apply_url",""),c.get("note","")])
            if not c["tiers"]:
                longs.append([today,"통신","KT","KT",c.get("issuer",""),c["card_name"],"",c.get("fee",""),
                              None,"수기확인",None,c.get("disc_type","청구할인"),
                              c.get("apply_url",""),c.get("note","")])
            if any(t.get("spend") for t in c["tiers"]):
                bs,pr=grid(c["tiers"],"기본"),grid(c["tiers"],"프로모션")
                grids.append([today,"통신","KT/"+c["card_name"],c["card_name"],c.get("fee","")]
                             +[bs[g] for g in GRID]+[pr[g] for g in GRID])
    except Exception as e:
        report.append(("통신","KT",0,f"FAIL: {e}")); errs.append(("통신","KT"))

    # ── 2-c) 아정당 자사(우리/하나) — 통신+렌탈 2벌 적재 ──────
    try:
        ajd_cards=collect_ajd()
        n_parse=sum(1 for c in ajd_cards if "파싱" in c.get("note",""))
        report.append(("자사","아정당",len(ajd_cards),f"OK (파싱 {n_parse}/{len(ajd_cards)}, 나머지 고정값)"))
        for c in ajd_cards:
            for cat in ("통신","렌탈"):   # C안: 양쪽 탭에 동일 카드 적재
                for t in c["tiers"]:
                    longs.append([today,cat,"아정당","아정당",c.get("issuer",""),c["card_name"],"",c.get("fee",""),
                                  t.get("spend"),t["type"],t.get("discount"),c.get("disc_type","청구할인"),
                                  c.get("apply_url",""),c.get("note","")])
                if any(t.get("spend") for t in c["tiers"]):
                    bs,pr=grid(c["tiers"],"기본"),grid(c["tiers"],"프로모션")
                    grids.append([today,cat,"아정당/"+c["card_name"],c["card_name"],c.get("fee","")]
                                 +[bs[g] for g in GRID]+[pr[g] for g in GRID])
    except Exception as e:
        report.append(("자사","아정당",0,f"FAIL: {e}")); errs.append(("자사","아정당"))

    # ── 3) CSV 저장 (확장 컬럼) ─────────────────────────────
    LONG_HEAD=["date","category","carrier","carrier2","issuer","card_name","tel","fee",
               "spend_tier","type","discount","disc_type","apply_url","note"]
    with open(f"card_long_{today}.csv","w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(LONG_HEAD); w.writerows(longs)
    with open(f"card_grid_{today}.csv","w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["date","category","key","card_name","fee"]+[f"기본_{g}만" for g in GRID]+[f"프로모_{g}만" for g in GRID]); w.writerows(grids)

    # ── 4) 리포트 출력 ──────────────────────────────────────
    print("\n"+"="*56)
    print(f"  수집 리포트 ({today})")
    print("="*56)
    for kind,name,n,status in report:
        flag="[OK]" if status.startswith("OK") else ("[!] " if "0건" in status else "[X]")
        print(f"  {flag} [{kind}] {name:14s} {n:3d}장  {status}")
    print("="*56)
    print(f"  long {len(longs)}행 / grid {len(grids)}장 -> card_long_{today}.csv")
    if errs: print(f"  실패: {errs}")

    # ── 5) Supabase 적재 (전체 삭제 → 오늘치만 재적재: 누적/1000행컷 원천 차단) ──
    #   ※ 과거 '오늘 것만 삭제'는 어제·그제 행이 계속 남아 3일이면 1000행 초과 →
    #      PostgREST 기본 1000행 응답컷에 렌탈이 잘림. 그래서 매 실행마다 전체 비우고
    #      오늘 하루치(~350행)만 남긴다. 이력 보관이 필요하면 아래 신중히 변경.
    su,sk=os.environ.get("SUPABASE_URL"),os.environ.get("SUPABASE_KEY")
    if su and sk and longs:
        hdr={"apikey":sk,"Authorization":f"Bearer {sk}","Content-Type":"application/json"}
        # (a) 전체 삭제. date>=0 등 항상참 조건이 있어야 PostgREST가 전체 DELETE 허용.
        #     (조건 없는 DELETE는 안전장치로 막혀 있어 400 반환됨)
        try:
            dresp=requests.delete(f"{su}/rest/v1/card_benefit2?date=gte.2000-01-01",
                headers={**hdr,"Prefer":"return=minimal"},timeout=30)
            print("  Supabase DELETE(all):",dresp.status_code,"OK" if dresp.status_code<300 else dresp.text[:200])
        except Exception as e:
            print("  Supabase DELETE 실패:",e)
        # (b) 오늘치 재적재
        pl=[dict(zip(LONG_HEAD,r)) for r in longs]
        resp=requests.post(f"{su}/rest/v1/card_benefit2",
            headers={**hdr,"Prefer":"return=minimal"},
            data=json.dumps(pl,ensure_ascii=False).encode("utf-8"),timeout=30)
        print("  Supabase INSERT:",resp.status_code,"OK" if resp.status_code<300 else resp.text[:200])
        # (c) 적재 후 행수 검증 — 1000 근처면 경고
        try:
            cnt=requests.get(f"{su}/rest/v1/card_benefit2?select=count",
                headers={**hdr,"Prefer":"count=exact"},timeout=30)
            total=cnt.headers.get("Content-Range","").split("/")[-1]
            print(f"  Supabase 현재 총행수: {total}")
            if total.isdigit() and int(total)>900:
                print("  [경고] 900행 초과 — 1000행 컷 위험. 삭제가 안 됐을 수 있음(키 권한 확인).")
        except Exception as e:
            print("  행수 확인 실패:",e)
    elif not(su and sk):
        print("  Supabase 미설정 → CSV만 생성")

if __name__=="__main__": main()

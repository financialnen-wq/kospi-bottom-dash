import os,sys,json
from dotenv import load_dotenv; load_dotenv('/Users/soobinkim/Downloads/tg-digest/.env')
from pykrx.website.comm.auth import get_auth_session
s=get_auth_session()
sess=getattr(s,'session',s)
URL='https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd'
H={'User-Agent':'Mozilla/5.0','Referer':'https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC0201060101'}
def get(bld,**kw):
    d=dict(bld=bld,locale='ko_KR',share='1',money='1',csvxls_isNo='false',**kw)
    r=sess.post(URL,data=d,headers=H,timeout=120); return r.json()
if __name__=='__main__':
    j=get('dbms/MDC/STAT/standard/MDCSTAT13102',inqTpCd='2',prtType='AMT',prtCheck='SUN',isuCd='KR___OPK2I',isuCd2='',prodId='KR___OPK2I',isuOpt='P',aggBasTpCd='',strtDd=sys.argv[1],endDd=sys.argv[2])
    print(json.dumps(j,ensure_ascii=False)[:1500])

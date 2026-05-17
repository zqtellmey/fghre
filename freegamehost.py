import time
import os
import json
import re
import random
import requests

# 智能环境配置：仅在未设置时才应用默认值
# 这样兼容 GitHub Actions 的 xvfb-run (会自动设置 DISPLAY) 和 Docker 环境
if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":1"
    
if "XAUTHORITY" not in os.environ:
    # 仅当路径存在时才设置，避免在 GitHub Runner (home/runner) 中报错
    if os.path.exists("/home/headless/.Xauthority"):
        os.environ["XAUTHORITY"] = "/home/headless/.Xauthority"

print(f"[DEBUG] Env DISPLAY: {os.environ.get('DISPLAY')}")
print(f"[DEBUG] Env XAUTHORITY: {os.environ.get('XAUTHORITY')}")

from seleniumbase import SB

# ================= 配置区域 =================
PROXY_URL = os.getenv("PROXY", "")  # 代理
TG_TOKEN = os.getenv("TG_TOKEN")  # tg通知token
TG_CHAT_ID = os.getenv("TG_CHAT_ID")  # tg通知chat_id
COOKIE = os.getenv("COOKIE")  # cookies
SERVERNUM = os.getenv("NUM")  # 服务器编号

# 目标 URL
URL_APP_PANEL = f"https://panel.freegamehost.xyz/server/{SERVERNUM}"
# ===========================================

class FreegameHostRenewal:
    def __init__(self):
        self.BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        self.screenshot_dir = os.path.join(self.BASE_DIR, "artifacts")
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)

    def log(self, msg):
        timestamp = time.strftime('%H:%M:%S')
        print(f"[{timestamp}] [INFO] {msg}", flush=True)

    def human_wait(self, min_s=6, max_s=10):
        """随机模拟人类等待时间"""
        time.sleep(random.uniform(min_s, max_s))

    def move_mouse_human(self, sb):
        """模拟人类鼠标晃动预热"""
        try:
            # 在页面不同位置“晃悠”一下鼠标，打破机器人直线模式
            for _ in range(3):
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                sb.slow_click(f"body", force=True) # 借用 slow_click 的移动特性，或者直接用 move_to
                time.sleep(random.uniform(0.5, 1.2))
        except: pass

    def send_telegram_notify(self, message, photo_path=None):
        """发送 Telegram 通知 (带图片)"""
        if not TG_TOKEN or not TG_CHAT_ID:
            self.log("⚠️ 未配置 TG_TOKEN 或 TG_CHAT_ID，跳过推送。")
            return
        
        try:
            if photo_path and os.path.exists(photo_path):
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
                with open(photo_path, 'rb') as f:
                    # caption 参数用于发送带文字的图片
                    requests.post(url, data={'chat_id': TG_CHAT_ID, 'caption': message}, files={'photo': f})
            else:
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                requests.post(url, data={'chat_id': TG_CHAT_ID, 'text': message})
            
            self.log("✅ TG 推送已发送")
        except Exception as e:
            self.log(f"❌ TG 推送失败: {e}")

    def _handle_cookie_consent(self, sb):
        """处理隐私/Cookie 同意弹窗 (从本地 zampto.py 1:1 复制)"""
        direct_selectors = [
            "#onetrust-accept-btn-handler",
            "button#didomi-notice-agree-button",
            "button[aria-label*='Accept']",
            "button[aria-label*='同意']",
        ]
        for sel in direct_selectors:
            try:
                if sb.is_element_visible(sel):
                    sb.click(sel)
                    self.log(f"✅ 已点击 Cookie 同意选择器: {sel}")
                    time.sleep(1)
                    return
            except Exception:
                pass

        try:
            clicked = bool(
                sb.execute_script(r"""
                (function() {
                    var buttons = document.querySelectorAll('button');
                    for (var i = 0; i < buttons.length; i++) {
                        var text = (buttons[i].textContent || '').trim().toLowerCase().replace(/\s+/g, '');
                        if (
                          text === 'consent' ||
                          text === 'accept' ||
                          text === 'agree' ||
                          text === 'acceptall' ||
                          text === '同意' ||
                          text === '我同意'
                        ) {
                            buttons[i].click();
                            return true;
                        }
                    }
                    var all = document.querySelectorAll('button,[role="button"],a');
                    for (var j = 0; j < all.length; j++) {
                        var item = all[j];
                        var title = (item.getAttribute('aria-label') || item.getAttribute('title') || '').toLowerCase();
                        var txt = (item.textContent || '').toLowerCase().replace(/\s+/g, '');
                        if (
                          title.includes('accept') || title.includes('agree') ||
                          txt.includes('accept') || txt.includes('agree') ||
                          txt.includes('同意') || txt.includes('全部同意')
                        ) {
                            item.click();
                            return true;
                        }
                    }
                    return false;
                })()
                """)
            )
            if clicked:
                self.log("✅ 已点击 Cookie 同意")
                time.sleep(1)
        except Exception:
            pass

        # 中文专项兜底
        try:
            zh_clicked = bool(
                sb.execute_script(r"""
                (function() {
                    var cands = Array.from(document.querySelectorAll('button,[role="button"],a'));
                    function visible(el) {
                        if (!el) return false;
                        var r = el.getBoundingClientRect();
                        var s = window.getComputedStyle(el);
                        return r.width > 30 && r.height > 18 && s.visibility !== 'hidden' && s.display !== 'none';
                    }
                    for (var i = 0; i < cands.length; i++) {
                        var t = (cands[i].textContent || '').trim();
                        if (!visible(cands[i])) continue;
                        if (t === '同意' || t.indexOf('同意') >= 0 || t.indexOf('接受') >= 0) {
                            cands[i].click();
                            return true;
                        }
                    }
                    return false;
                })()
                """)
            )
            if zh_clicked:
                self.log("✅ 已点击中文同意按钮")
                time.sleep(1)
        except Exception:
            pass

    def run(self):
        self.log("=" * 40)
        self.log("🚀 FreegameHost - 拟人化续期流程")
        self.log("=" * 40)
        self.log("🎯 正在启动 Chrome 浏览器...")
        
        # 使用 headed=True 强制有头模式渲染到 VNC
        with SB(
            uc=True,            # 启用反检测模式
            test=True, 
            headed=True,        # 关键：强制有头模式
            headless=False,     # 明确禁用 headless
            xvfb=False,         # 禁用内部虚拟显示器，使用系统 DISPLAY
            chromium_arg="--no-sandbox,--disable-dev-shm-usage,--disable-gpu,--window-position=0,0,--start-maximized",
            proxy=PROXY_URL if PROXY_URL else None
        ) as sb:
            try:
                self.log("✅ 浏览器已启动！")
                
                # ... (省略中间步骤，保持原有逻辑不变) ...
                
                # 1. IP 检测
                self.log("🌍 正在检测出口 IP...")
                try:
                    sb.open("https://api.ipify.org?format=json")
                    ip_val = json.loads(re.search(r'\{.*\}', sb.get_text("body")).group(0)).get('ip', 'Unknown')
                    parts = ip_val.split('.')
                    self.log(f"✅ 当前出口 IP: {parts[0]}.{parts[1]}.***.{parts[-1]}")
                except:
                    self.log("⚠️ IP 检测跳过...")

                # 2. 访问主页并注入 Cookie
                self.log("🔗 正在访问入口页面...")
                sb.uc_open_with_reconnect("https://panel.freegamehost.xyz/auth/login", reconnect_time=5)
                self.log("⏳ 等待页面 JS 渲染...")
                time.sleep(10)
                
                sb.add_cookie({
                    "name": "remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d",
                    "value": f"{COOKIE}",
                    "domain": "panel.freegamehost.xyz",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "Lax",
                    "expires": int(time.time()) + 3600 * 24 * 365
                })
                self.log("✅ Cookie 注入成功！")

                # 3. 进入管理面板
                self.log(f"📂 正在进入面板...")
                sb.uc_open_with_reconnect(URL_APP_PANEL, reconnect_time=5)
                self.human_wait(6, 10)

                if "login" in sb.get_current_url().lower():
                    self.log(f"❌ 权限失效。当前 URL: {sb.get_current_url()}")
                    # ... 省略登录失败处理 ...
                    sb.save_screenshot(f"{self.screenshot_dir}/login_fail.png")
                    self.log(f"📸 失败截图已保存至: {self.screenshot_dir}/login_fail.png")
                    return

                self._handle_cookie_consent(sb)
                time.sleep(3)
          
                # 4. 点击续期
                self.log("🖱️ 正在点击 '+8 HOURS'...")
                self.move_mouse_human(sb)
                xpath = '//button[contains(., "8")]'
                sb.wait_for_element_present(xpath, timeout=20)
                sb.scroll_to(xpath)
                sb.sleep(random.uniform(1, 2))
                sb.hover(xpath)
                sb.sleep(random.uniform(0.5, 1.2))
                sb.slow_click(xpath) 
                self.human_wait(6, 10)
   
                # 5. 验证码处理循环 (已优化)
                max_retry_rounds = 3
                for round_idx in range(max_retry_rounds):
                    self.log(f"🔄 执行第 {round_idx + 1}/{max_retry_rounds} 轮验证...")
                    
                    for attempt in range(4):
                        if sb.is_text_visible("Connection lost"):
                            # ... 连接丢失处理 ...
                            try: sb.click("//button[contains(., '연장하기')]")
                            except: sb.refresh()
                            time.sleep(15)
                            continue

                        text_all = sb.get_text("body").lower()
                        has_cf = ("verify you are human" in text_all or 
                                  "challenges.cloudflare" in text_all or
                                  sb.is_element_present('iframe[src*="cloudflare"]') or
                                  sb.is_element_present('iframe[src*="turnstile"]'))
                        has_err = "complete the captcha" in text_all

                        sb.uc_gui_click_captcha()
                        sb.uc_gui_handle_captcha()

                        if has_cf or has_err:
                            self.log(f"🛡️ 发现验证挑战 (尝试 {attempt+1})...")
                            sb.save_screenshot(f"{self.screenshot_dir}/captcha_found.png")
                            
                            self.log("⏳ 等待验证码完全加载...")
                            time.sleep(15)
                            
                            try:
                                self.log("🖱️ 正在尝试点击验证码 (uc_gui_click_captcha)...")
                                sb.uc_gui_click_captcha()
                                sb.uc_gui_handle_captcha()
                                self.log("✅ 点击动作已执行")

                            except Exception as e_cap:
                                self.log(f"⚠️ 验证码点击失败: {e_cap}")
                                sb.save_screenshot(f"{self.screenshot_dir}/click_fail.png")

                            self.log("⏳ GUI 点击完成，等待生效 (8秒)...")
                            time.sleep(8)
                            
                            self.log("✅ 动作已执行，准备尝试提交...")
                            break
                        else:
                            self.log("✅ 未发现活跃验证码，准备提交。")
                            break
            
                # 保存最终截图
                final_screenshot = f"{self.screenshot_dir}/final_success.png"
                sb.save_screenshot(final_screenshot)

                # 6. 再次进入管理面板
                self.log(f"📂 再次进入面板...")
                sb.uc_open_with_reconnect(URL_APP_PANEL, reconnect_time=5)
                self.human_wait(6, 10)
                timestamp = sb.get_text('[class*="RenewBox__TimerDigits"]')

                if final_screenshot:
                    # 发送 TG 通知
                    msg = f"✅ FreegameHost 续期成功\n\n🕒 到期时间为: {timestamp}\n"
                    self.send_telegram_notify(msg, final_screenshot)
                else:
                    msg = f"❌ FreegameHost 续期失败\n\n"
                    self.send_telegram_notify(msg, final_screenshot)

            except Exception as e:
                self.log(f"❌ 运行异常: {e}")
                import traceback
                traceback.print_exc()
                sb.save_screenshot(f"{self.screenshot_dir}/error.png")


if __name__ == "__main__":
    FreegameHostRenewal().run()

import os
import time
import sys
import threading
import random
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

RED = '\033[91m'
GREEN = '\033[92m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

results_lock = threading.Lock()
stats_lock = threading.Lock()

stats = {
    'available': 0,
    'taken': 0,
    'total_checked': 0
}

active_drivers = []
drivers_lock = threading.Lock()

def load_config():
    """Load configuration from config.json file"""
    if not os.path.exists("config.json"):
        print(f"{RED}❌ No config.json file found{RESET}")
        return None
    
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"{RED}❌ Error loading config.json: {str(e)}{RESET}")
        return None

def create_usernames_folder(config):
    """Create usernames folder if it doesn't exist"""
    folder_path = config.get("paths", {}).get("usernames_folder", "usernames")
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

def load_usernames(config):
    """Load usernames from the configured file"""
    folder = config.get("paths", {}).get("usernames_folder", "usernames")
    filename = config.get("paths", {}).get("usernames_file", "usernames.txt")
    filepath = os.path.join(folder, filename)
    
    if not os.path.exists(filepath):
        print(f"{RED}❌ No usernames file found at {filepath}{RESET}")
        return None
    
    try:
        with open(filepath, "r") as f:
            usernames = [line.strip() for line in f if line.strip()]
        return usernames if usernames else None
    except Exception as e:
        print(f"{RED}❌ Error loading usernames: {str(e)}{RESET}")
        return None

def save_available_username(username, config):
    """Save available username and remove from input file"""
    with results_lock:
        folder = config.get("paths", {}).get("usernames_folder", "usernames")
        available_file = config.get("paths", {}).get("available_file", "available_usernames.txt")
        available_path = os.path.join(folder, available_file)
        
        with open(available_path, "a") as f:
            f.write(f"{username}\n")
        
        folder = config.get("paths", {}).get("usernames_folder", "usernames")
        filename = config.get("paths", {}).get("usernames_file", "usernames.txt")
        filepath = os.path.join(folder, filename)
        
        with open(filepath, "r") as f:
            lines = f.readlines()
        with open(filepath, "w") as f:
            for line in lines:
                if line.strip() != username:
                    f.write(line)
        
        with stats_lock:
            stats['available'] += 1
            stats['total_checked'] += 1

def save_taken_username(username, config):
    """Save taken username and remove from input file"""
    with results_lock:
        folder = config.get("paths", {}).get("usernames_folder", "usernames")
        taken_file = config.get("paths", {}).get("taken_file", "taken_usernames.txt")
        taken_path = os.path.join(folder, taken_file)
        
        with open(taken_path, "a") as f:
            f.write(f"{username}\n")
        
        folder = config.get("paths", {}).get("usernames_folder", "usernames")
        filename = config.get("paths", {}).get("usernames_file", "usernames.txt")
        filepath = os.path.join(folder, filename)
        
        with open(filepath, "r") as f:
            lines = f.readlines()
        with open(filepath, "w") as f:
            for line in lines:
                if line.strip() != username:
                    f.write(line)
        
        with stats_lock:
            stats['taken'] += 1
            stats['total_checked'] += 1

def setup_chrome_driver(token_index, config):
    """Setup Chrome driver with options from config"""
    chrome_options = Options()
    
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--quiet")
    
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    if config.get("browser", {}).get("headless", False):
        chrome_options.add_argument("--headless")
    
    tokens = config.get("tokens", [])
    if len(tokens) > 1:
        debug_port_start = config.get("browser", {}).get("debug_port_start", 9222)
        chrome_options.add_argument(f"--remote-debugging-port={debug_port_start + token_index}")
        chrome_options.add_argument(f"--user-data-dir=/tmp/chrome_profile_{token_index}")
    
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        with drivers_lock:
            active_drivers.append(driver)
        
        return driver
    except Exception as e:
        print(f"{RED}❌ Chrome setup failed: {str(e)}{RESET}")
        return None

def login_with_token(driver, token, token_index):
    """Login to Discord using token"""
    try:
        driver.get("https://discord.com")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
        
        script = f"""
        let token = "{token}";
        function login(token) {{
            setInterval(() => {{
              document.body.appendChild(document.createElement('iframe')).contentWindow.localStorage.token = `"${{token}}"`;
            }}, 50);
            setTimeout(() => {{
              location.reload();
            }}, 2500);
          }}
        login(token);
        """
        
        driver.execute_script(script)
        time.sleep(5)
        
        try:
            open_discord_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Open Discord')]")
            open_discord_btn.click()
            time.sleep(3)
            
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='app-']")))
            
            time.sleep(2)
            if "channels" not in driver.current_url:
                driver.get("https://discord.com/channels/@me")
                time.sleep(3)
            
            return True
        except:
            if "discord.com" in driver.current_url and "login" not in driver.current_url:
                time.sleep(2)
                if "channels" not in driver.current_url:
                    driver.get("https://discord.com/channels/@me")
                    time.sleep(3)
                
                return True
            return False
    except Exception as e:
        return False

def navigate_to_username_edit(driver, token_index, config):
    """Navigate to username edit page"""
    page_load_wait = config.get("timing", {}).get("page_load_wait", 3)
    
    try:
        driver.get("https://discord.com/channels/@me")
        time.sleep(page_load_wait)
        
        try:
            settings_btn = driver.execute_script("""
                var buttons = document.querySelectorAll('button[aria-label="User Settings"], div[aria-label="User Settings"], button[aria-label="Settings"], div[aria-label="Settings"]');
                for (var i = 0; i < buttons.length; i++) {
                    if (buttons[i].offsetParent !== null) {
                        buttons[i].click();
                        return true;
                    }
                }
                return false;
            """)
            
            if settings_btn:
                time.sleep(page_load_wait + 1)
                
                username_edit_found = driver.execute_script("""
                    var buttons = document.querySelectorAll('button[aria-label="Edit username"]');
                    for (var i = 0; i < buttons.length; i++) {
                        if (buttons[i].offsetParent !== null) {
                            buttons[i].click();
                            return true;
                        }
                    }
                    
                    var usernameElements = document.querySelectorAll('*');
                    for (var i = 0; i < usernameElements.length; i++) {
                        if (usernameElements[i].textContent && usernameElements[i].textContent.includes('Username')) {
                            var parent = usernameElements[i].closest('div');
                            if (parent) {
                                var editButtons = parent.querySelectorAll('button');
                                for (var j = 0; j < editButtons.length; j++) {
                                    if (edit_buttons[j].textContent && edit_buttons[j].textContent.includes('Edit')) {
                                        edit_buttons[j].click();
                                        return true;
                                    }
                                }
                            }
                        }
                    }
                    return false;
                """)
                
                if username_edit_found:
                    time.sleep(2)
                    return True
            
        except Exception as js_error:
            pass
                
    except Exception as e:
        pass
    
    return False

def type_username_manually(driver, username, token_index):
    """Type username into the input field"""
    try:
        username_input = driver.find_element(By.CSS_SELECTOR, "input[name='username']")
        
        username_input.click()
        username_input.send_keys(Keys.CONTROL + "a")
        time.sleep(0.5)
        username_input.send_keys(Keys.DELETE)
        time.sleep(1)
        
        for char in username:
            username_input.send_keys(char)
            time.sleep(random.uniform(0.1, 0.3))
        
        return True
    except Exception as e:
        return False

def check_username_availability(driver):
    """Check if username is available"""
    try:
        time.sleep(2)
        
        messages = driver.find_elements(By.CSS_SELECTOR, ".text-xs\\/normal_cf4812")
        
        for msg in messages:
            msg_text = msg.text.lower()
            
            if "username is unavailable" in msg_text or "try adding numbers" in msg_text:
                return False
            elif "username is available" in msg_text or "nice!" in msg_text:
                return True
            
            style = msg.get_attribute("style")
            if style:
                if "text-feedback-critical" in style:
                    return False
                elif "text-feedback-positive" in style:
                    return True
        
        return None
    except:
        return None

def clear_username_field(driver):
    """Clear the username input field"""
    try:
        username_input = driver.find_element(By.CSS_SELECTOR, "input[name='username']")
        username_input.click()
        username_input.send_keys(Keys.CONTROL + "a")
        time.sleep(0.5)
        username_input.send_keys(Keys.DELETE)
        time.sleep(1)
        return True
    except:
        return False

def process_token(token, token_index, usernames, failed_tokens, config):
    """Process a single token to check usernames"""
    driver = None
    try:
        driver = setup_chrome_driver(token_index, config)
        if not driver:
            return token_index
        
        wait_time = config.get("timing", {}).get("wait_between_checks", 30)
        
        if login_with_token(driver, token, token_index):
            if navigate_to_username_edit(driver, token_index, config):
                for username in usernames:
                    if token_index in failed_tokens:
                        break
                    
                    if type_username_manually(driver, username, token_index):
                        is_available = check_username_availability(driver)
                        
                        if is_available is True:
                            print(f"✅ {GREEN}\"{username}\"{RESET}")
                            save_available_username(username, config)
                        elif is_available is False:
                            print(f"❌ {RED}\"{username}\"{RESET}")
                            save_taken_username(username, config)
                        else:
                            print(f"[❓] {RED}\"{username}\" status unknown{RESET}")
                        
                        clear_username_field(driver)
                        
                        print(f"{BOLD}⏳ Waiting: {wait_time}s{RESET}")
                        time.sleep(wait_time)
                    else:
                        print(f"{RED}❌ Failed to type username{RESET}")
            else:
                print(f"{RED}❌ Failed to navigate to username edit{RESET}")
                return token_index
        else:
            print(f"{RED}❌ Login failed{RESET}")
            return token_index
    except Exception as e:
        print(f"{RED}❌ Token failed: {str(e)}{RESET}")
        return token_index
    
    return None

def assign_usernames_to_tokens(tokens, usernames):
    """Assign usernames to tokens in round-robin fashion"""
    assignments = {i: [] for i in range(len(tokens))}
    
    for i, username in enumerate(usernames):
        token_index = i % len(tokens)
        assignments[token_index].append(username)
    
    return assignments

def print_stats():
    """Print final statistics"""
    with stats_lock:
        print(f"\n{BOLD}📊 STATS: Available Names: {GREEN}{stats['available']}{RESET} {BOLD}Taken Names: {RED}{stats['taken']}{RESET} {BOLD}Total Checked: {BLUE}{stats['total_checked']}{RESET}")

def close_all_drivers():
    """Close all active drivers"""
    with drivers_lock:
        for driver in active_drivers:
            try:
                driver.quit()
            except:
                try:
                    driver.close()
                except:
                    pass
        active_drivers.clear()

def main():
    config = load_config()
    if not config:
        return
    
    create_usernames_folder(config)
    
    tokens = config.get("tokens", [])
    if not tokens:
        print(f"{RED}❌ No tokens found in config.json{RESET}")
        return
    
    usernames = load_usernames(config)
    if not usernames:
        return
    
    print(f"Found {GREEN}{len(tokens)}{RESET} token(s) and {GREEN}{len(usernames)}{RESET} username(s)")
    print(f"{BOLD}CTRL + C to close browsers{RESET}")
    
    with stats_lock:
        stats['available'] = 0
        stats['taken'] = 0
        stats['total_checked'] = 0
    
    assignments = assign_usernames_to_tokens(tokens, usernames)
    failed_tokens = set()
    threads = []
    
    for i, token in enumerate(tokens):
        thread = threading.Thread(target=process_token, args=(token, i, assignments[i], failed_tokens, config))
        thread.start()
        threads.append(thread)
        
        if i < len(tokens) - 1:
            time.sleep(2)
    
    for thread in threads:
        thread.join()
    
    if failed_tokens:
        print(f"{RED}❌ Failed tokens detected. Reassigning usernames...{RESET}")
        
        remaining_usernames = []
        for token_index in failed_tokens:
            remaining_usernames.extend(assignments[token_index])
        
        if remaining_usernames and len(failed_tokens) < len(tokens):
            working_tokens = [i for i in range(len(tokens)) if i not in failed_tokens]
            
            if working_tokens:
                print(f"{GREEN}✅ Reassigning {len(remaining_usernames)} usernames to {len(working_tokens)} working tokens{RESET}")
                
                new_assignments = {i: [] for i in working_tokens}
                for i, username in enumerate(remaining_usernames):
                    token_index = working_tokens[i % len(working_tokens)]
                    new_assignments[token_index].append(username)
                
                new_threads = []
                for token_index in working_tokens:
                    token = tokens[token_index]
                    thread = threading.Thread(target=process_token, args=(token, token_index, new_assignments[token_index], failed_tokens, config))
                    thread.start()
                    new_threads.append(thread)
                
                for thread in new_threads:
                    thread.join()
    
    print_stats()
    
    close_all_drivers()
    print(f"{GREEN}✅ All browser profiles closed{RESET}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Stopped by user")
        close_all_drivers()
    except Exception as e:
        print(f"{RED}❌ Unexpected error: {str(e)}{RESET}")
        close_all_drivers()
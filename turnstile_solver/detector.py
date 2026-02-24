"""
Internal module to detect the presence and type of Cloudflare Turnstile on a page.

This uses Chrome DevTools Protocol (CDP) to inspect the DOM and determine whether
an embedded widget or full challenge page is present.
"""

from typing import Optional
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

class TurnstileDetector:
    """
    Detects whether a Turnstile widget is present on the page,
    and identifies its type: 'embedded' or 'challenge'.
    
    :param driver: Selenium WebDriver instance.
    """

    def __init__(self, driver, debug: bool = True):
        self.driver = driver
        self.debug = debug
        self.node_id: Optional[int] = None
        self.type: Optional[str] = None
    
    def _log(self, msg: str):
        if self.debug:
            print(f"[Detector] {msg}", flush=True)

    def detect(self) -> Optional[dict]:
        """
        Detect and classify the Turnstile widget using CDP.

        :return: True/False if found/not found.
        """
        try:
            # 1. Standard CDP detection for .cf-turnstile
            # Note: keeping original logic to support standard non-shadow widgets
            try:
                root = self.driver.execute_cdp_cmd("DOM.getDocument", {"depth": 2})
                self.node_id = root["root"]["nodeId"]

                if self._has_embedded_widget():
                    self.type = "embedded"
                    self._log("Found standard embedded widget (.cf-turnstile)")
                    return True

                if self._has_challenge_page():
                    self.type = "challenge"
                    self._log("Found challenge page")
                    return True
            except Exception as e:
                # self._log(f"CDP detection failed: {e}")
                pass

            # 2. Fallback: Iframe-based detection (Selenium)
            # This handles cases where .cf-turnstile wrapper is missing or different
            if self._has_iframe_widget():
                self.type = "embedded" # Threat frame as embedded
                self._log("Found widget via iframe search")
                return True

            self._log("No widget detected in this pass")
            return None

        # This is an expected error if the DOM changes (e.g., page reload or dynamic updates)
        # causing the previously obtained nodeId to become invalid.
        # Common CDP error: "No node with given id found"
        except WebDriverException as e:
            self._log(f"WebDriverException during detection: {e}")
            return None

    def _has_embedded_widget(self) -> bool:
        """
        Check if an embedded Turnstile widget exists via #cf-turnstile[data-sitekey].
        If found, scroll it into view (centered).
        
        :return: True if embedded widget found, else False.
        """
        try:
            result = self.driver.execute_cdp_cmd("DOM.querySelector", {
                "nodeId": self.node_id,
                "selector": ".cf-turnstile[data-sitekey]"
            })
            node_id = result.get("nodeId")
            if node_id:
                # Scroll into center of viewport for image
                self.driver.execute_cdp_cmd("DOM.scrollIntoViewIfNeeded", {
                    "nodeId": node_id,
                    "center": True
                })
                return True
        except:
            pass
        return False

    def _has_challenge_page(self) -> bool:
        """
        Check if the page is a Cloudflare challenge page via .footer-inner content.
        If found, scroll it into view (centered).

        :return: True if challenge page detected, else False.
        """
        try:
            footer = self.driver.execute_cdp_cmd("DOM.querySelector", {
                "nodeId": self.node_id,
                "selector": ".footer-inner"
            })

            footer_id = footer.get("nodeId")
            if not footer_id:
                return False

            # Get HTML content of the footer
            html = self.driver.execute_cdp_cmd("DOM.getOuterHTML", {
                "nodeId": footer_id
            }).get("outerHTML", "")

            return all(kw in html for kw in ["Ray ID", "Performance &", "security by", "Cloudflare"])
        except:
            pass
        return False

    def _has_iframe_widget(self) -> bool:
        """
        Check for iframes containing cloudflare/turnstile in src, including inside Shadow DOM.
        """
        try:
            # Method 1: Standard Selenium find_elements (Top level only)
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                src = iframe.get_attribute("src") or ""
                if "cloudflare" in src and "cdn-cgi" in src:
                    self._log(f"Found Cloudflare iframe (Top Level): {src[:60]}...")
                    return True
            
            # Method 2: Deep Search via JS (Traverse Shadow DOM)
            found = self.driver.execute_script("""
                function findTurnstileIframe(root, depth=0) {
                    if (!root || depth > 10) return false;
                    
                    // Check if current node is the target iframe
                    if (root.tagName === 'IFRAME') {
                        const src = root.src || '';
                        if (src.includes('cloudflare') && src.includes('cdn-cgi')) {
                            return true;
                        }
                    }
                    
                    // Check Shadow Root (including our hacked one from test script)
                    const shadow = root.shadowRoot || root.__closedShadowRoot;
                    if (shadow) {
                        if (findTurnstileIframe(shadow, depth + 1)) return true;
                    }
                    
                    // Check children
                    if (root.children) {
                        for (let child of Array.from(root.children)) {
                            if (findTurnstileIframe(child, depth)) return true;
                        }
                    }
                    return false;
                }
                
                try {
                    return findTurnstileIframe(document.body);
                } catch(e) {
                    return false;
                }
            """)
            
            if found:
                self._log("Found Cloudflare iframe inside Shadow DOM via JS")
                return True
                
            return False
        except Exception as e:
            self._log(f"Iframe check error: {e}")
            return False

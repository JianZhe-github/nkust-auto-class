"""
matcher.py

Locates Cloudflare Turnstile captchas using DOM traversal and Shadow DOM analysis.
Replaces image matching with precise element location.
"""

from typing import Literal
from selenium.webdriver.common.by import By
import traceback

class TurnstileMatcher:
    """
    Locates the Turnstile widget and its checkbox by traversing iframes
    and nested shadow roots.
    """

    def __init__(
        self,
        driver,
        theme: Literal["light", "dark", "auto"] = "auto",
        grayscale: bool = False,
        thresh: float = 0.8,
        debug: bool = True
    ):
        self.driver = driver
        # Parameters kept for compatibility but not used in DOM matching
        self.theme = theme
        self.grayscale = grayscale
        self.thresh = thresh
        self.debug = debug

    def _log(self, msg: str):
        if self.debug:
            print(f"[Matcher] {msg}", flush=True)

    def match(self) -> tuple[int, int] | None:
        """
        Find the Turnstile checkbox coordinates using DOM traversal.
        
        Returns:
            (x, y) coordinates adjusted so that solver's offset click hits the checkbox center.
            The solver typically adds (30, 25) to the returned coordinates.
        """
        try:
            # 1. Find iframes that look like Cloudflare Turnstile (including inside Shadow DOM)
            # Standard find_elements only checks top-level DOM. We need a deep search.
            candidates = self.driver.execute_script("""
                function findAllTurnstileIframes(root, depth=0, results=[]) {
                    if (!root || depth > 20) return results;

                    // Check if current node is target iframe
                    if (root.tagName === 'IFRAME') {
                         const src = root.src || '';
                         if (src.includes('cloudflare') && src.includes('cdn-cgi')) {
                             results.push(root);
                         }
                    }

                    // Shadow Root (Deep Search)
                    // Support standard shadowRoot and our anti-closed-shadow hack
                    const shadow = root.shadowRoot || root.__closedShadowRoot;
                    if (shadow) {
                        findAllTurnstileIframes(shadow, depth + 1, results);
                    }

                    // Children
                    if (root.children) {
                        for (let child of Array.from(root.children)) {
                            findAllTurnstileIframes(child, depth, results);
                        }
                    }
                    return results;
                }
                
                try {
                    return findAllTurnstileIframes(document.body);
                } catch (e) {
                    return [];
                }
            """)
            
            # User requested logs
            self._log(f"Found {len(candidates)} candidate iframes via Deep Search")
            
            if not candidates:
                 self._log("No Cloudflare iframes found")

            for i, iframe in enumerate(candidates):
                try:
                    # Get iframe absolute position using JS getBoundingClientRect to ensure Viewport Coordinates
                    # (Selenium's element.rect might return document-relative coordinates)
                    rect = self.driver.execute_script("return arguments[0].getBoundingClientRect();", iframe)
                    iframe_x = rect['x']
                    iframe_y = rect['y']
                    iframe_w = rect['width']
                    iframe_h = rect['height']
                    self._log(f"Checking candidate {i} at viewport pos: ({iframe_x}, {iframe_y}) size: {iframe_w}x{iframe_h}")

                    # 2. Switch to iframe context
                    self.driver.switch_to.frame(iframe)

                    # 3. Use JS to traverse Shadow DOM (handling potential nested layers)
                    # Returns {x, y, width, height} relative to iframe or null
                    checkbox_rect = self.driver.execute_script("""
                        function findCheckbox(root, depth=0, log=[]) {
                            if (!root || depth > 10) return null;
                            
                            // Log current node (simplified)
                            // log.push("D" + depth + ": " + root.tagName);

                            // Check for checkbox input - RELAXED CONDITION
                            if (root.tagName === 'INPUT') { // && root.type === 'checkbox') {
                                // Sometimes it's not strictly type=checkbox or it's hidden
                                // Return it if it looks like a checkbox
                                const rect = root.getBoundingClientRect();
                                return {x: rect.x, y: rect.y, width: rect.width, height: rect.height, found: true, type: root.type};
                            }
                            
                            // 1. Search in Shadow Root
                            // Check both standard shadowRoot (open) and our hacked __closedShadowRoot (closed)
                            const shadow = root.shadowRoot || root.__closedShadowRoot;
                            if (shadow) {
                                // log.push("-> Entering ShadowRoot");
                                const res = findCheckbox(shadow, depth + 1, log);
                                if (res) return res;
                            }
                            
                            // 2. Search in children
                            // Use Array.from to handle HTMLCollections safely
                            if (root.children) {
                                for (let child of Array.from(root.children)) {
                                    const res = findCheckbox(child, depth, log);
                                    if (res) return res;
                                }
                            }
                            return null;
                        }
                        
                        // Start search from body
                        try {
                            const logs = [];
                            
                            // Debug Info
                            const info = {
                                url: window.location.href,
                                readyState: document.readyState,
                                bodyChildren: document.body ? document.body.children.length : -1,
                                htmlLen: document.body ? document.body.innerHTML.length : -1
                            };
                            logs.push("Context Info: " + JSON.stringify(info));

                            if (!document || !document.body) {
                                return {found: false, reason: "No document or body", logs: logs};
                            }
                            
                            if (document.body.children.length === 0 && document.body.innerHTML.trim().length === 0) {
                                return {found: false, reason: "Body is empty (loading?)", logs: logs};
                            }

                            // Helper to log structure
                            function getStructure(node, d=0) {
                                if (!node || d > 5) return "";
                                let s = "\\n" + "  ".repeat(d) + (node.tagName || node.nodeName);
                                if (node.id) s += "#" + node.id;
                                if (node.className) s += "." + node.className;
                                
                                const shadow = node.shadowRoot || node.__closedShadowRoot;
                                if (shadow) {
                                    s += " [SHADOW]";
                                    for (let child of Array.from(shadow.children || [])) {
                                        s += getStructure(child, d+1);
                                    }
                                }
                                if (node.children) {
                                    for (let child of Array.from(node.children)) {
                                        s += getStructure(child, d+1);
                                    }
                                }
                                return s;
                            }

                            const result = findCheckbox(document.body, 0, logs);
                            if (!result) {
                                // If not found, return debug info with structure
                                return {
                                    found: false, 
                                    html_preview: document.body ? document.body.innerHTML.substring(0, 100) : "NO BODY",
                                    structure: document.body ? getStructure(document.body) : "NO BODY",
                                    logs: logs
                                };
                            }
                            return result;
                        } catch (e) {
                            return {error: e.toString()};
                        }
                    """)

                    # Switch back immediately
                    self.driver.switch_to.default_content()

                    if isinstance(checkbox_rect, dict) and 'error' in checkbox_rect:
                        self._log(f"JS Error in candidate {i}: {checkbox_rect['error']}")
                        continue
                        
                    if isinstance(checkbox_rect, dict) and checkbox_rect.get('found') is False:
                         if checkbox_rect.get('reason') == "Body is empty (loading?)":
                             # FAILSAFE: If body is empty, assume Cloudflare blockage and click center blindly!
                             self._log(f"Candidate {i} body is empty. ATTEMPTING BLIND CLICK.")
                             checkbox_rect = {
                                 'x': max(0, iframe_w/2 - 15),
                                 'y': max(0, iframe_h/2 - 15),
                                 'width': 30,
                                 'height': 30,
                                 'found': True
                             }
                             # Do NOT continue, let it fall through to 'if checkbox_rect:' block
                         else:
                             self._log(f"Checkbox NOT found. Reason: {checkbox_rect.get('reason') or 'Unknown'}")
                             self._log(f"Logs: {checkbox_rect.get('logs')}")
                             self._log(f"Structure: {checkbox_rect.get('structure')}")
                             continue

                    if checkbox_rect:
                        self._log(f"Checkbox found in candidate {i}: {checkbox_rect}")
                        # Parse results
                        x = iframe_x + checkbox_rect['x']
                        y = iframe_y + checkbox_rect['y']
                        w = checkbox_rect['width']
                        h = checkbox_rect['height']

                        # Coordinate Adjustment for Solver.py
                        # Solver.py logic: click(x + 30, y + 25)
                        # We want to click center: (x + w/2, y + h/2)
                        # Equation: return_x + 30 = x + w/2  => return_x = x + w/2 - 30
                        #           return_y + 25 = y + h/2  => return_y = y + h/2 - 25
                        
                        target_x = x + (w / 2) - 30
                        target_y = y + (h / 2) - 25
                        
                        self._log(f"Target coords: ({target_x}, {target_y}) (Original: {x}, {y}, Size: {w}x{h})")

                        return int(target_x), int(target_y)
                    else:
                        self._log(f"Checkbox NOT found in candidate {i} (JS returned null)")

                except Exception as e:
                    self._log(f"Exception processing candidate {i}: {e}")
                    traceback.print_exc()
                    # Ensure we switch back if something breaks in the loop
                    try:
                        self.driver.switch_to.default_content()
                    except:
                        pass
                    continue
            
            # If no candidates processed successfully
            # self._log("No matching checkbox found in any candidate")
            return None

        except Exception as e:
            self._log(f"Top-level match exception: {e}")
            traceback.print_exc()
            return None

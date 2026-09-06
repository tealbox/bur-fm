"""
FortiManager API Client Class
This module provides a Python class for interacting with FortiManager JSON RPC API.
"""

import requests
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class CFortiManager:
    """
    FortiManager API Client Class
    
    Provides methods to interact with FortiManager JSON RPC API including:
    - Authentication with API key
    - GET, POST, SET, EXEC operations
    - Device management (list, authorize, manage ADOM assignments)
    - Centralized logging
    """
    
    def __init__(self, fmg_ip: str, api_key: str, adom: str = "root", verify_ssl: bool = False):
        """
        Initialize FortiManager API Client
        
        Args:
            fmg_ip: FortiManager IP address or FQDN
            api_key: API key for authentication (Bearer token)
            adom: Administrative Domain (default: "root")
            verify_ssl: Whether to verify SSL certificates (default: False)
        """
        self.fmg_ip = fmg_ip
        self.api_key = api_key
        self.adom = adom
        self.verify_ssl = verify_ssl
        self.base_url = f"https://{fmg_ip}/jsonrpc"
        self.session_id = None
        self.request_id = 1
        
        # Setup logging
        self.logger = self._setup_logger()
        self.logger.info(f"Initialized CFortiManager for {fmg_ip}")
    
    def _setup_logger(self) -> logging.Logger:
        """Setup centralized logging to file and console"""
        log_filename = f"fortimanager_api_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        
        # File handler
        file_handler = logging.FileHandler(log_filename)
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Remove existing handlers to avoid duplicates
        logger.handlers.clear()
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def _get_next_request_id(self) -> int:
        """Get next request ID for API calls"""
        current_id = self.request_id
        self.request_id += 1
        return current_id
    
    def _make_request(self, method: str, url: str, data: Optional[Dict] = None, 
                     fields: Optional[List] = None) -> Dict[str, Any]:
        """
        Make a JSON RPC request to FortiManager API
        
        Args:
            method: HTTP method (exec, get, set, post, etc.)
            url: API endpoint URL
            data: Data payload for POST/SET operations
            fields: Fields to return (for GET operations)
        
        Returns:
            API response as dictionary
        """
        params = {"url": url}
        
        if data:
            params["data"] = data
        if fields:
            params["fields"] = fields
        
        payload = {
            "id": self._get_next_request_id(),
            "method": method,
            "params": [params]
        }
        
        if self.session_id:
            payload["session"] = self.session_id
        
        self.logger.debug(f"Request: {json.dumps(payload, indent=2)}")
        
        try:
            response = requests.post(
                self.base_url,
                json=payload,
                verify=self.verify_ssl,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            self.logger.debug(f"Response: {json.dumps(result, indent=2)}")
            
            return result
        
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {str(e)}")
            raise
    
    def login(self, username: str, password: str) -> bool:
        """
        Authenticate using username and password
        
        Args:
            username: FortiManager username
            password: FortiManager password
        
        Returns:
            True if authentication successful, False otherwise
        """
        self.logger.info(f"Attempting login with user: {username}")
        
        data = {
            "user": username,
            "passwd": password
        }
        
        try:
            response = self._make_request("exec", "/sys/login/user", data=data)
            
            if response.get("session"):
                self.session_id = response["session"]
                self.logger.info(f"Login successful. Session ID: {self.session_id[:20]}...")
                return True
            else:
                self.logger.error("Login failed: No session ID returned")
                return False
        
        except Exception as e:
            self.logger.error(f"Login error: {str(e)}")
            return False
    
    def login_with_api_key(self, api_token: str) -> bool:
        """
        Authenticate using API key (Bearer token)
        
        Args:
            api_token: API Bearer token
        
        Returns:
            True if authentication successful, False otherwise
        """
        self.logger.info("Attempting login with API key")
        self.api_key = api_token
        
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        try:
            payload = {
                "id": self._get_next_request_id(),
                "method": "exec",
                "params": [{"url": "/sys/login/user"}]
            }
            
            self.logger.debug(f"API Key Request: {json.dumps(payload, indent=2)}")
            
            response = requests.post(
                self.base_url,
                json=payload,
                headers=headers,
                verify=self.verify_ssl,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            self.logger.debug(f"API Key Response: {json.dumps(result, indent=2)}")
            
            if result.get("session"):
                self.session_id = result["session"]
                self.logger.info(f"API Key login successful. Session ID: {self.session_id[:20]}...")
                return True
            else:
                self.logger.error("API Key login failed: No session ID returned")
                return False
        
        except Exception as e:
            self.logger.error(f"API Key login error: {str(e)}")
            return False
    
    def logout(self) -> bool:
        """
        Logout from FortiManager
        
        Returns:
            True if logout successful, False otherwise
        """
        self.logger.info("Attempting logout")
        
        try:
            response = self._make_request("exec", "/sys/logout")
            
            if response.get("result"):
                status = response["result"][0].get("status", {})
                if status.get("code") == 0:
                    self.logger.info("Logout successful")
                    self.session_id = None
                    return True
            
            self.logger.error("Logout failed")
            return False
        
        except Exception as e:
            self.logger.error(f"Logout error: {str(e)}")
            return False
    
    def get(self, url: str, fields: Optional[List[str]] = None) -> Optional[List[Dict]]:
        """
        GET method - Retrieve configuration objects
        
        Args:
            url: API endpoint URL
            fields: Optional list of fields to return
        
        Returns:
            List of objects or None if failed
        """
        self.logger.info(f"GET: {url}")
        
        try:
            response = self._make_request("get", url, fields=fields)
            
            if response.get("result"):
                data = response["result"][0].get("data", [])
                self.logger.info(f"GET successful: Retrieved {len(data) if data else 0} objects")
                return data
            
            self.logger.warning("GET: No data returned")
            return None
        
        except Exception as e:
            self.logger.error(f"GET error: {str(e)}")
            return None
    
    def set(self, url: str, data: Dict) -> bool:
        """
        SET method - Update configuration objects
        
        Args:
            url: API endpoint URL
            data: Object data to update
        
        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"SET: {url}")
        
        try:
            response = self._make_request("set", url, data=data)
            
            if response.get("result"):
                status = response["result"][0].get("status", {})
                if status.get("code") == 0:
                    self.logger.info("SET successful")
                    return True
            
            self.logger.error("SET failed")
            return False
        
        except Exception as e:
            self.logger.error(f"SET error: {str(e)}")
            return False
    
    def post(self, url: str, data: Dict) -> bool:
        """
        POST method - Create new configuration objects
        
        Args:
            url: API endpoint URL
            data: Object data to create
        
        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"POST: {url}")
        
        try:
            response = self._make_request("post", url, data=data)
            
            if response.get("result"):
                status = response["result"][0].get("status", {})
                if status.get("code") == 0:
                    self.logger.info("POST successful")
                    return True
            
            self.logger.error("POST failed")
            return False
        
        except Exception as e:
            self.logger.error(f"POST error: {str(e)}")
            return False
    
    def delete(self, url: str) -> bool:
        """
        DELETE method - Delete configuration objects
        
        Args:
            url: API endpoint URL
        
        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"DELETE: {url}")
        
        try:
            response = self._make_request("delete", url)
            
            if response.get("result"):
                status = response["result"][0].get("status", {})
                if status.get("code") == 0:
                    self.logger.info("DELETE successful")
                    return True
            
            self.logger.error("DELETE failed")
            return False
        
        except Exception as e:
            self.logger.error(f"DELETE error: {str(e)}")
            return False
    
    def exec(self, url: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """
        EXEC method - Execute commands or operations
        
        Args:
            url: API endpoint URL
            data: Optional data payload
        
        Returns:
            Response data or None if failed
        """
        self.logger.info(f"EXEC: {url}")
        
        try:
            response = self._make_request("exec", url, data=data)
            
            if response.get("result"):
                self.logger.info("EXEC successful")
                return response["result"][0]
            
            self.logger.error("EXEC failed")
            return None
        
        except Exception as e:
            self.logger.error(f"EXEC error: {str(e)}")
            return None
    
    def list_unauthorized_devices(self) -> Optional[List[Dict]]:
        """
        List all unauthorized devices in FortiManager
        
        Returns:
            List of unauthorized devices or None if failed
        """
        self.logger.info("Listing unauthorized devices")
        
        try:
            # Get all devices
            url = f"/dvm/cmd/discover/device"
            devices = self.get(url)
            
            if not devices:
                self.logger.warning("No devices found or API call failed")
                return None
            
            # Filter unauthorized devices
            unauthorized = [d for d in devices if d.get("adm_pass") is False]
            
            self.logger.info(f"Found {len(unauthorized)} unauthorized devices")
            return unauthorized
        
        except Exception as e:
            self.logger.error(f"Error listing unauthorized devices: {str(e)}")
            return None
    
    def get_device_model(self, device: Dict) -> Optional[str]:
        """
        Extract device model from device object
        
        Args:
            device: Device object
        
        Returns:
            Device model string or None
        """
        try:
            # Try different possible model fields
            model = device.get("model") or device.get("device_model") or device.get("prod_name")
            return model
        except Exception as e:
            self.logger.error(f"Error extracting device model: {str(e)}")
            return None
    
    def determine_adom_by_model(self, model: str) -> str:
        """
        Determine ADOM assignment based on device model
        
        Args:
            model: Device model string
        
        Returns:
            ADOM name
        """
        if not model:
            return self.adom  # Default to root ADOM
        
        model = model.lower()
        
        # Model-based ADOM assignment logic
        if "60" in model or "60f" in model:
            return "ADOM_FortiGate_60"
        elif "70" in model or "70d" in model:
            return "ADOM_FortiGate_70"
        elif "80" in model:
            return "ADOM_FortiGate_80"
        elif "90" in model:
            return "ADOM_FortiGate_90"
        elif "100" in model:
            return "ADOM_FortiGate_100"
        else:
            return self.adom  # Default ADOM
    
    def authorize_device(self, device_serial: str, device_name: str, 
                        adom: Optional[str] = None) -> bool:
        """
        Authorize a device and assign to ADOM
        
        Args:
            device_serial: Device serial number
            device_name: Device name
            adom: Optional ADOM name (if not provided, will determine from model)
        
        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"Authorizing device: {device_name} (SN: {device_serial})")
        
        try:
            # Get device details first
            url = f"/dvm/cmd/discover/device"
            devices = self.get(url)
            
            target_device = None
            if devices:
                for dev in devices:
                    if dev.get("sn") == device_serial or dev.get("name") == device_name:
                        target_device = dev
                        break
            
            if not target_device:
                self.logger.error(f"Device not found: {device_name}")
                return False
            
            # Determine ADOM if not provided
            if not adom:
                model = self.get_device_model(target_device)
                adom = self.determine_adom_by_model(model)
            
            self.logger.info(f"Assigning device to ADOM: {adom}")
            
            # Authorize device
            url = f"/dvm/cmd/add/device"
            data = {
                "name": device_name,
                "sn": device_serial,
                "adom": adom,
                "username": "admin"
            }
            
            success = self.post(url, data)
            
            if success:
                self.logger.info(f"Device authorized successfully: {device_name} -> {adom}")
            else:
                self.logger.error(f"Failed to authorize device: {device_name}")
            
            return success
        
        except Exception as e:
            self.logger.error(f"Error authorizing device: {str(e)}")
            return False
    
    def get_firewall_addresses(self, adom: Optional[str] = None, 
                              fields: Optional[List[str]] = None) -> Optional[List[Dict]]:
        """
        Get all firewall address objects from specified ADOM
        
        Args:
            adom: ADOM name (default: self.adom)
            fields: Optional list of fields to return
        
        Returns:
            List of firewall addresses or None if failed
        """
        if not adom:
            adom = self.adom
        
        url = f"/pm/config/adom/{adom}/obj/firewall/address"
        self.logger.info(f"Retrieving firewall addresses from ADOM: {adom}")
        
        return self.get(url, fields=fields)
    
    def get_firewall_services(self, adom: Optional[str] = None) -> Optional[List[Dict]]:
        """
        Get all firewall service objects from specified ADOM
        
        Args:
            adom: ADOM name (default: self.adom)
        
        Returns:
            List of firewall services or None if failed
        """
        if not adom:
            adom = self.adom
        
        url = f"/pm/config/adom/{adom}/obj/firewall/service/custom"
        self.logger.info(f"Retrieving firewall services from ADOM: {adom}")
        
        return self.get(url)
    
    def get_firewall_policies(self, adom: Optional[str] = None) -> Optional[List[Dict]]:
        """
        Get all firewall policies from specified ADOM
        
        Args:
            adom: ADOM name (default: self.adom)
        
        Returns:
            List of firewall policies or None if failed
        """
        if not adom:
            adom = self.adom
        
        url = f"/pm/config/adom/{adom}/pkg/default/firewall/policy"
        self.logger.info(f"Retrieving firewall policies from ADOM: {adom}")
        
        return self.get(url)
    
    def create_firewall_address(self, adom: str, name: str, subnet: str, 
                               color: int = 0, comment: str = "") -> bool:
        """
        Create a new firewall address object
        
        Args:
            adom: ADOM name
            name: Address object name
            subnet: Subnet in CIDR or space-separated format
            color: Color code (0-31)
            comment: Comment
        
        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"Creating firewall address: {name} in ADOM: {adom}")
        
        # Parse subnet
        if "/" in subnet:
            # Convert CIDR to netmask format
            from ipaddress import ip_network
            network = ip_network(subnet, strict=False)
            subnet_data = [str(network.network_address), str(network.netmask)]
        else:
            subnet_data = subnet.split()
        
        url = f"/pm/config/adom/{adom}/obj/firewall/address"
        data = {
            "name": name,
            "subnet": subnet_data,
            "color": color,
            "comment": comment,
            "type": 0
        }
        
        return self.post(url, data)
    
    def __del__(self):
        """Cleanup - logout when object is destroyed"""
        try:
            if self.session_id:
                self.logout()
        except:
            pass


class CFortiManagerTask(CFortiManager):
    """
    Extended FortiManager API Client with Task Management capabilities
    
    Inherits from CFortiManager and adds task-specific operations
    """
    
    def __init__(self, fmg_ip: str, api_key: str, adom: str = "root", verify_ssl: bool = False):
        """Initialize FortiManagerTask"""
        super().__init__(fmg_ip, api_key, adom, verify_ssl)
        self.logger.info("Initialized CFortiManagerTask")
    
    def get_tasks(self) -> Optional[List[Dict]]:
        """
        Get all tasks from FortiManager
        
        Returns:
            List of tasks or None if failed
        """
        self.logger.info("Retrieving tasks")
        
        url = "/task/task"
        return self.get(url)
    
    def get_task_status(self, task_id: int) -> Optional[Dict]:
        """
        Get status of a specific task
        
        Args:
            task_id: Task ID
        
        Returns:
            Task status object or None if failed
        """
        self.logger.info(f"Retrieving task status for task ID: {task_id}")
        
        url = f"/task/task/{task_id}"
        result = self.get(url)
        
        return result[0] if result else None
    
    def execute_task(self, task_name: str, parameters: Optional[Dict] = None) -> Optional[int]:
        """
        Execute a task on FortiManager
        
        Args:
            task_name: Name of the task to execute
            parameters: Optional task parameters
        
        Returns:
            Task ID or None if failed
        """
        self.logger.info(f"Executing task: {task_name}")
        
        url = "/task/task"
        data = {
            "name": task_name,
            "parameters": parameters or {}
        }
        
        result = self.exec(url, data=data)
        
        if result:
            task_id = result.get("task_id")
            self.logger.info(f"Task executed with ID: {task_id}")
            return task_id
        
        return None


# Example usage
if __name__ == "__main__":
    # Example initialization and usage
    
    # Initialize with API key
    fm = CFortiManager(
        fmg_ip="192.168.1.1",
        api_key="your_api_key_here"
    )
    
    # Login with API key
    if fm.login_with_api_key("your_api_key_here"):
        
        # List unauthorized devices
        unauthorized_devices = fm.list_unauthorized_devices()
        if unauthorized_devices:
            print(f"Found {len(unauthorized_devices)} unauthorized devices:")
            for device in unauthorized_devices:
                print(f"  - {device.get('name')} (SN: {device.get('sn')})")
        
        # Get firewall addresses
        addresses = fm.get_firewall_addresses(fields=["name", "subnet"])
        if addresses:
            print(f"\nFound {len(addresses)} firewall addresses")
        
        # Create a new address
        fm.create_firewall_address(
            adom="root",
            name="Test-Network",
            subnet="192.168.1.0/24",
            comment="Test network"
        )
        
        # Logout
        fm.logout()
    else:
        print("Login failed")

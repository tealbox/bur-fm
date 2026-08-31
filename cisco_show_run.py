#!/usr/bin/env python3
"""
Script to login to Cisco device and run 'show run' command
Handles '--more--' prompts automatically
"""

from netmiko import ConnectHandler
import time

def login_and_run_show_run(device_info):
    """
    Login to Cisco device and execute 'show run' command,
    handling '--more--' prompts automatically.
    
    Args:
        device_info (dict): Dictionary containing:
            - device_type: 'cisco_ios', 'cisco_nxos', etc.
            - host: IP address or hostname
            - username: Login username
            - password: Login password
            - secret: Enable password (optional)
    """
    try:
        # Connect to the device
        net_connect = ConnectHandler(**device_info)
        
        # Enter enable mode if secret is provided
        if 'secret' in device_info:
            net_connect.enable()
        
        # Execute show run command using send_command with max_loops to handle --more--
        output = net_connect.send_command(
            "show run",
            expect_string=r"#",
            delay_factor=1,
            max_loops=1000  # Handles multiple '--more--' prompts
        )
        
        # Disconnect from device
        net_connect.disconnect()
        
        return output
        
    except Exception as e:
        print(f"Error connecting to device: {e}")
        return None


def main():
    """Main function with device connection parameters"""
    
    # Device connection details - MODIFY THESE FOR YOUR DEVICE
    device = {
        'device_type': 'cisco_ios',
        'host': '192.168.1.1',      # Change to your device IP
        'username': 'admin',         # Change to your username
        'password': 'password',      # Change to your password
        'secret': 'enable_password', # Change to your enable password
        'port': 22,
    }
    
    print("Connecting to Cisco device...")
    output = login_and_run_show_run(device)
    
    if output:
        print("\n" + "="*80)
        print("SHOW RUN OUTPUT:")
        print("="*80)
        print(output)
        
        # Optionally save to file
        with open('show_run_output.txt', 'w') as f:
            f.write(output)
        print("\nOutput saved to 'show_run_output.txt'")
    else:
        print("Failed to retrieve output")


if __name__ == "__main__":
    main()

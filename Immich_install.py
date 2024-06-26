# Ram
# 25 jun, 2024
# immich installer
# ver 5.2


import os
import subprocess
import sys
import getpass

def run_command(command):
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    if result.returncode != 0:
        print(f"Command failed: {command}\n{result.stderr}")
        sys.exit(result.returncode)
    print(f"Command succeeded: {command}\n{result.stdout}")
    return result.stdout

def prompt_password(prompt_message):
    return getpass.getpass(prompt_message)

def update_db_password():
    # Run 'pwd' to display the current working directory
    current_directory = subprocess.run(['pwd'], capture_output=True, text=True).stdout.strip()
    print(f"Current directory: {current_directory}")

    # Prompt for the path to the .env file
    env_dir_path = input("Enter the path to the directory containing the .env file (e.g., /immich-app): ")

    # Construct the full path to the .env file
    env_file_path = os.path.join(env_dir_path, ".env")

    # Check if the file exists
    if not os.path.isfile(env_file_path):
        print(f"File not found: {env_file_path}")
        exit(1)

    # Prompt for new password and confirmation
    new_password = prompt_password("Enter the new DB password: ")
    confirm_password = prompt_password("Confirm the new DB password: ")

    # Check if passwords match
    if new_password != confirm_password:
        print("Passwords do not match. Please try again.")
        exit(1)

    # Read the .env file
    with open(env_file_path, 'r') as file:
        lines = file.readlines()

    # Update the .env file with the new password
    updated = False
    with open(env_file_path, 'w') as file:
        for line in lines:
            if line.startswith("DB_PASSWORD="):
                file.write(f"DB_PASSWORD={new_password}\n")
                updated = True
            else:
                file.write(line)

    if updated:
        print("DB password updated successfully.")
    else:
        print("DB_PASSWORD entry not found in the .env file.")
        exit(1)

def add_nginx_config_line():
    # Define the path to the nginx.conf file
    nginx_conf_path = "/etc/nginx/nginx.conf"

    # Check if the file exists
    if not os.path.isfile(nginx_conf_path):
        print(f"File not found: {nginx_conf_path}")
        exit(1)

    # Read the nginx.conf file
    with open(nginx_conf_path, 'r') as file:
        lines = file.readlines()

    # Flag to check if the line was added
    line_added = False

    # Prepare the new line to be added
    new_line = "\tclient_max_body_size 500M;\n"

    # Open the nginx.conf file for writing
    with open(nginx_conf_path, 'w') as file:
        for line in lines:
            file.write(line)
            # Add the new line after the line containing "types_hash_max_size:"
            if "types_hash_max_size" in line and not line_added:
                indentation = line[:len(line) - len(line.lstrip())]  # Capture the indentation of the current line
                file.write(f"{indentation}client_max_body_size 500M;\n")
                line_added = True

    if line_added:
        print("Configuration line added successfully.")
    else:
        print("The specified line was not found in the configuration file.")
        exit(1)

def main():
    # Prompt for the domain name
    DOMAIN_NAME = input("Enter your domain name (e.g., me.mooo.com): ")

    # Install the basics
    run_command("sudo apt update -y")
    run_command("sudo apt upgrade -y")
    run_command("sudo apt install vim fail2ban curl openssh-server nginx certbot python3-certbot-nginx -y")

    # Install packages to allow apt to use a repository over HTTPS
    run_command("sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common")

    # Add Docker’s official GPG key
    run_command("curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -")

    # Set up the stable repository
    run_command('''sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"''')

    # Update the apt package index again
    run_command("sudo apt-get update")

    # Install the latest version of Docker Engine and containerd
    run_command("sudo apt-get install -y docker-ce docker-ce-cli containerd.io")

    # Verify that Docker Engine is installed correctly
    run_command("sudo docker run hello-world")

    # Check the Docker version
    print(run_command("docker --version"))

    os.makedirs("./immich-app", exist_ok=True)
    os.chdir("./immich-app")

    run_command("wget -O docker-compose.yml https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml")
    run_command("wget -O .env https://github.com/immich-app/immich/releases/latest/download/example.env")
    run_command("wget -O hwaccel.transcoding.yml https://github.com/immich-app/immich/releases/latest/download/hwaccel.transcoding.yml")
    run_command("wget -O hwaccel.ml.yml https://github.com/immich-app/immich/releases/latest/download/hwaccel.ml.yml")

    # Execute Pass_FileSize_Update.py script functionality here
    update_db_password()
    add_nginx_config_line()

    # Start and enable Nginx
    run_command("sudo systemctl start nginx")
    run_command("sudo systemctl enable nginx")

    # Check Nginx status
    print(run_command("sudo systemctl status nginx"))

    # Create the necessary directories
    run_command(f"sudo mkdir -p /var/www/{DOMAIN_NAME}/html")

    # Set permissions
    run_command(f"sudo chown -R $USER:$USER /var/www/{DOMAIN_NAME}/html")
    run_command("sudo chmod -R 755 /var/www")

    # Create necessary directories for Nginx configuration
    run_command("sudo mkdir -p /etc/nginx/sites-available")
    run_command("sudo mkdir -p /etc/nginx/sites-enabled")

    # Define the file path
    FILE_PATH = f"/etc/nginx/sites-available/{DOMAIN_NAME}"

    # Server block configuration content to be added
    SERVER_BLOCK = f"""
    server {{
        listen 80;
        listen [::]:80;

        # replace with your domain or subdomain
        server_name {DOMAIN_NAME};

        # https://github.com/immich-app/immich/blob/main/nginx/templates/default.conf.template#L28
        client_max_body_size 50000M;

        location / {{
            proxy_pass http://localhost:2283;
            proxy_set_header Host              $http_host;
            proxy_set_header X-Real-IP         $remote_addr;
            proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # http://nginx.org/en/docs/http/websocket.html
            proxy_http_version 1.1;
            proxy_set_header   Upgrade    $http_upgrade;
            proxy_set_header   Connection "upgrade";
            proxy_redirect off;
        }}
    }}
    """

    # Create or overwrite the file with the server block configuration
    with open("/tmp/server_block.conf", "w") as file:
        file.write(SERVER_BLOCK)
    
    run_command(f"sudo mv /tmp/server_block.conf {FILE_PATH}")

    # Create a symbolic link to enable the site
    run_command(f"sudo ln -s /etc/nginx/sites-available/{DOMAIN_NAME} /etc/nginx/sites-enabled/")

    # Allow traffic on ports 80 and 443
    run_command("sudo ufw allow 80")
    run_command("sudo ufw allow 443")

    # Reload Nginx to apply the changes
    run_command("sudo systemctl reload nginx")
    
    # Obtain an SSL certificate
    run_command(f"sudo certbot --nginx -d {DOMAIN_NAME}")

    print("Setup completed successfully!")

if __name__ == "__main__":
    main()

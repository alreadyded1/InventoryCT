# Inventory Manager

A lightweight, web-based inventory management system with a clean front-end interface. Perfect for running in a Proxmox container.

## Features

- **Item Management**: Add, view, edit, and delete inventory items
- **Multiple Image Support**: Upload and manage multiple images per item
- **Comprehensive Fields**: Track item name, brand, cost, quantity, and description
- **Image Gallery**: View items with an interactive image carousel
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Lightweight**: Built with Flask and SQLite - no external database required
- **Container Ready**: Optimized for deployment in Proxmox containers

## Quick Start

### Using Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd InventoryCT
   ```

2. **Build and run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

3. **Access the application**
   Open your browser to `http://localhost:5000`

### Manual Installation

1. **Install Python 3.11+**
   ```bash
   python3 --version  # Verify Python is installed
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Access the application**
   Open your browser to `http://localhost:5000`

## Deployment to Proxmox

### Option 1: Docker Container in Proxmox

1. **Create a Proxmox LXC container** with Docker support
   - Template: Ubuntu 22.04 or Debian 12
   - Enable nesting and keyctl features

2. **Install Docker in the container**
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   ```

3. **Clone and deploy**
   ```bash
   git clone <repository-url>
   cd InventoryCT
   docker-compose up -d
   ```

### Option 2: Direct Python Installation in LXC

1. **Create a Proxmox LXC container**
   - Template: Ubuntu 22.04 or Debian 12
   - Allocate: 1-2 CPU cores, 512MB-1GB RAM, 8GB disk

2. **Install Python and dependencies**
   ```bash
   apt update && apt install -y python3 python3-pip python3-venv git
   ```

3. **Deploy the application**
   ```bash
   git clone https://github.com/alreadyded1/InventoryCT.git
   cd InventoryCT
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Create systemd service** (optional, for auto-start)
   ```bash
   sudo nano /etc/systemd/system/inventory-manager.service
   ```

   Add:
   ```ini
   [Unit]
   Description=Inventory Manager
   After=network.target

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/root/InventoryCT
   Environment="PATH=/root/InventoryCT/venv/bin"
   ExecStart=/root/InventoryCT/venv/bin/python app.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable inventory-manager
   sudo systemctl start inventory-manager
   ```

## Updating

### Updating Docker Installation

To update a Docker-based installation:

```bash
cd InventoryCT
git pull origin main
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Updating Direct Python Installation

To update a direct Python installation:

1. **Stop the application** (if running as a service)
   ```bash
   sudo systemctl stop inventory-manager
   ```

   Or if running manually, press `Ctrl+C` in the terminal.

2. **Backup your data** (recommended before updating)
   ```bash
   cp inventory.db inventory.db.backup
   cp -r uploads/ uploads.backup/
   ```

3. **Pull the latest changes**
   ```bash
   cd InventoryCT
   git pull origin main
   ```

4. **Update Python dependencies**
   ```bash
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install --upgrade -r requirements.txt
   ```

5. **Restart the application**

   If using systemd service:
   ```bash
   sudo systemctl start inventory-manager
   sudo systemctl status inventory-manager
   ```

   If running manually:
   ```bash
   python app.py
   ```

### Checking Current Version

```bash
cd InventoryCT
git log -1 --oneline  # Show latest commit
git status           # Check for uncommitted changes
```

### Rollback (if needed)

If an update causes issues:

```bash
# Restore database backup
cp inventory.db.backup inventory.db
cp -r uploads.backup/ uploads/

# Revert to previous version
git log --oneline    # Find the commit hash you want to revert to
git checkout <commit-hash>

# Restart the application
sudo systemctl restart inventory-manager
```

## Configuration

### Environment Variables

- `SECRET_KEY`: Flask secret key (change in production)
- Default port: `5000` (can be modified in `app.py` or docker-compose.yml)

### Data Persistence

- **Database**: `inventory.db` (SQLite)
- **Uploads**: `uploads/` directory
- Both are automatically created on first run
- For Docker deployments, volumes are configured in `docker-compose.yml`

## Usage

### Adding Items

1. Click "Add New Item" button
2. Fill in item details:
   - Name (required)
   - Brand
   - Cost
   - Quantity
   - Description
   - Upload one or more images
3. Click "Add Item"

### Editing Items

1. Click on an item card or "View" button
2. Click "Edit" button
3. Modify any fields
4. Add new images or delete existing ones
5. Set a primary image (displayed in the inventory list)
6. Click "Save Changes"

### Viewing Items

- **Inventory List**: Browse all items with their primary images
- **Item Details**: Click "View" to see full details and image gallery
- **Image Carousel**: Navigate through multiple images

## Technical Details

### Stack

- **Backend**: Python Flask 3.0
- **Database**: SQLite3
- **Frontend**: HTML5, Bootstrap 5, JavaScript
- **Container**: Docker

### Database Schema

**Items Table**
- id (Primary Key)
- name
- brand
- cost
- quantity
- description
- created_at
- updated_at

**Images Table**
- id (Primary Key)
- item_id (Foreign Key)
- filename
- is_primary

### File Structure

```
InventoryCT/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── Dockerfile             # Docker image definition
├── docker-compose.yml     # Docker Compose configuration
├── templates/             # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── add_item.html
│   ├── edit_item.html
│   └── view_item.html
├── static/               # Static assets
│   └── css/
│       └── style.css
├── uploads/              # Uploaded images
└── inventory.db          # SQLite database (created on first run)
```

## Security Notes

- Change the `SECRET_KEY` in production
- This application is designed for internal/private network use
- For internet-facing deployments, consider adding:
  - Authentication/login system
  - HTTPS/SSL certificates
  - Rate limiting
  - Input validation enhancements

## Backup

To backup your inventory:

1. **Database**: Copy `inventory.db`
2. **Images**: Copy `uploads/` directory

```bash
# Backup script example
tar -czf inventory-backup-$(date +%Y%m%d).tar.gz inventory.db uploads/
```

## Troubleshooting

### Port Already in Use
```bash
# Change port in docker-compose.yml or app.py
# docker-compose.yml: "8080:5000"
# app.py: app.run(host='0.0.0.0', port=8080)
```

### Permission Issues
```bash
# Ensure proper ownership
chown -R $USER:$USER .
```

### Database Locked
```bash
# Stop all instances of the app
# Check for multiple running processes
ps aux | grep app.py
```

## License

This project is open source and available under the MIT License.

## Support

For issues, questions, or contributions, please open an issue in the repository.

#!/usr/bin/env python3
"""
Inventory Manager Application
A simple web-based inventory management system
"""
import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import uuid

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database setup
DATABASE = 'inventory.db'


def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database"""
    conn = get_db()
    cursor = conn.cursor()

    # Create categories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            brand TEXT,
            cost REAL,
            quantity INTEGER,
            description TEXT,
            listed_on TEXT,
            category_id INTEGER,
            sold BOOLEAN DEFAULT 0,
            sold_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        )
    ''')

    # Create images table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            is_primary BOOLEAN DEFAULT 0,
            FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
        )
    ''')

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Migrations: Add columns if they don't exist
    cursor.execute("PRAGMA table_info(items)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'listed_on' not in columns:
        cursor.execute('ALTER TABLE items ADD COLUMN listed_on TEXT')
    if 'sold' not in columns:
        cursor.execute('ALTER TABLE items ADD COLUMN sold BOOLEAN DEFAULT 0')
    if 'sold_date' not in columns:
        cursor.execute('ALTER TABLE items ADD COLUMN sold_date TIMESTAMP')
    if 'category_id' not in columns:
        cursor.execute('ALTER TABLE items ADD COLUMN category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL')

    conn.commit()
    conn.close()


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
@login_required
def index():
    """Display all inventory items (excluding sold items)"""
    conn = get_db()
    cursor = conn.cursor()

    # Get all items with their primary image and category (excluding sold items)
    cursor.execute('''
        SELECT i.*, img.filename as primary_image, c.name as category_name
        FROM items i
        LEFT JOIN images img ON i.id = img.item_id AND img.is_primary = 1
        LEFT JOIN categories c ON i.category_id = c.id
        WHERE i.sold = 0 OR i.sold IS NULL
        ORDER BY i.updated_at DESC
    ''')

    items = cursor.fetchall()
    conn.close()

    return render_template('index.html', items=items)


@app.route('/sold')
@login_required
def sold_items():
    """Display all sold items"""
    conn = get_db()
    cursor = conn.cursor()

    # Get all sold items with their primary image and category
    cursor.execute('''
        SELECT i.*, img.filename as primary_image, c.name as category_name
        FROM items i
        LEFT JOIN images img ON i.id = img.item_id AND img.is_primary = 1
        LEFT JOIN categories c ON i.category_id = c.id
        WHERE i.sold = 1
        ORDER BY i.sold_date DESC
    ''')

    items = cursor.fetchall()
    conn.close()

    return render_template('sold_items.html', items=items)


@app.route('/item/<int:item_id>')
@login_required
def view_item(item_id):
    """View single item details"""
    conn = get_db()
    cursor = conn.cursor()

    # Get item details with category
    cursor.execute('''
        SELECT i.*, c.name as category_name
        FROM items i
        LEFT JOIN categories c ON i.category_id = c.id
        WHERE i.id = ?
    ''', (item_id,))
    item = cursor.fetchone()

    if not item:
        flash('Item not found', 'error')
        return redirect(url_for('index'))

    # Get all images for this item
    cursor.execute('SELECT * FROM images WHERE item_id = ? ORDER BY is_primary DESC', (item_id,))
    images = cursor.fetchall()

    conn.close()

    return render_template('view_item.html', item=item, images=images)


@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_item():
    """Add new item"""
    if request.method == 'POST':
        name = request.form.get('name')
        brand = request.form.get('brand')
        cost = request.form.get('cost')
        quantity = request.form.get('quantity')
        description = request.form.get('description')
        listed_on = request.form.get('listed_on')
        category_id = request.form.get('category_id')

        if not name:
            flash('Item name is required', 'error')
            return redirect(url_for('add_item'))

        conn = get_db()
        cursor = conn.cursor()

        # Insert item
        cursor.execute('''
            INSERT INTO items (name, brand, cost, quantity, description, listed_on, category_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, brand, float(cost) if cost else None,
              int(quantity) if quantity else 0, description, listed_on,
              int(category_id) if category_id else None))

        item_id = cursor.lastrowid

        # Handle image uploads
        files = request.files.getlist('images')
        for idx, file in enumerate(files):
            if file and file.filename and allowed_file(file.filename):
                # Generate unique filename
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4()}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                # Save to database (first image is primary)
                is_primary = 1 if idx == 0 else 0
                cursor.execute('''
                    INSERT INTO images (item_id, filename, is_primary)
                    VALUES (?, ?, ?)
                ''', (item_id, filename, is_primary))

        conn.commit()
        conn.close()

        flash('Item added successfully!', 'success')
        return redirect(url_for('view_item', item_id=item_id))

    # GET request - fetch categories
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categories ORDER BY name')
    categories = cursor.fetchall()
    conn.close()

    return render_template('add_item.html', categories=categories)


@app.route('/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    """Edit existing item"""
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form.get('name')
        brand = request.form.get('brand')
        cost = request.form.get('cost')
        quantity = request.form.get('quantity')
        description = request.form.get('description')
        listed_on = request.form.get('listed_on')
        category_id = request.form.get('category_id')

        if not name:
            flash('Item name is required', 'error')
            return redirect(url_for('edit_item', item_id=item_id))

        # Update item
        cursor.execute('''
            UPDATE items
            SET name = ?, brand = ?, cost = ?, quantity = ?, description = ?, listed_on = ?, category_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (name, brand, float(cost) if cost else None,
              int(quantity) if quantity else 0, description, listed_on,
              int(category_id) if category_id else None, item_id))

        # Handle new image uploads
        files = request.files.getlist('images')
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                # Generate unique filename
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4()}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)

                # Check if this is the first image for this item
                cursor.execute('SELECT COUNT(*) as count FROM images WHERE item_id = ?', (item_id,))
                count = cursor.fetchone()['count']
                is_primary = 1 if count == 0 else 0

                cursor.execute('''
                    INSERT INTO images (item_id, filename, is_primary)
                    VALUES (?, ?, ?)
                ''', (item_id, filename, is_primary))

        # Handle image deletions
        delete_images = request.form.getlist('delete_images')
        for image_id in delete_images:
            # Get filename before deleting from DB
            cursor.execute('SELECT filename FROM images WHERE id = ?', (image_id,))
            img = cursor.fetchone()
            if img:
                # Delete file
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], img['filename'])
                if os.path.exists(filepath):
                    os.remove(filepath)
                # Delete from database
                cursor.execute('DELETE FROM images WHERE id = ?', (image_id,))

        # Handle primary image selection
        primary_image_id = request.form.get('primary_image')
        if primary_image_id:
            # Unset all primary flags for this item
            cursor.execute('UPDATE images SET is_primary = 0 WHERE item_id = ?', (item_id,))
            # Set new primary
            cursor.execute('UPDATE images SET is_primary = 1 WHERE id = ?', (primary_image_id,))

        conn.commit()
        conn.close()

        flash('Item updated successfully!', 'success')
        return redirect(url_for('view_item', item_id=item_id))

    # GET request - display form
    cursor.execute('SELECT * FROM items WHERE id = ?', (item_id,))
    item = cursor.fetchone()

    if not item:
        flash('Item not found', 'error')
        return redirect(url_for('index'))

    cursor.execute('SELECT * FROM images WHERE item_id = ? ORDER BY is_primary DESC', (item_id,))
    images = cursor.fetchall()

    cursor.execute('SELECT * FROM categories ORDER BY name')
    categories = cursor.fetchall()

    conn.close()

    return render_template('edit_item.html', item=item, images=images, categories=categories)


@app.route('/delete/<int:item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    """Delete an item"""
    conn = get_db()
    cursor = conn.cursor()

    # Get all images for this item
    cursor.execute('SELECT filename FROM images WHERE item_id = ?', (item_id,))
    images = cursor.fetchall()

    # Delete image files
    for img in images:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], img['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)

    # Delete from database (cascade will handle images table)
    cursor.execute('DELETE FROM images WHERE item_id = ?', (item_id,))
    cursor.execute('DELETE FROM items WHERE id = ?', (item_id,))

    conn.commit()
    conn.close()

    flash('Item deleted successfully!', 'success')
    return redirect(url_for('index'))


@app.route('/mark-sold/<int:item_id>', methods=['POST'])
@login_required
def mark_as_sold(item_id):
    """Mark an item as sold"""
    conn = get_db()
    cursor = conn.cursor()

    # Check if item exists
    cursor.execute('SELECT name FROM items WHERE id = ?', (item_id,))
    item = cursor.fetchone()

    if not item:
        flash('Item not found', 'error')
        return redirect(url_for('index'))

    # Mark as sold with current timestamp
    cursor.execute('''
        UPDATE items
        SET sold = 1, sold_date = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (item_id,))

    conn.commit()
    conn.close()

    flash(f'{item["name"]} marked as sold!', 'success')
    return redirect(url_for('index'))


@app.route('/unmark-sold/<int:item_id>', methods=['POST'])
@login_required
def unmark_sold(item_id):
    """Unmark an item as sold (return to inventory)"""
    conn = get_db()
    cursor = conn.cursor()

    # Check if item exists
    cursor.execute('SELECT name FROM items WHERE id = ?', (item_id,))
    item = cursor.fetchone()

    if not item:
        flash('Item not found', 'error')
        return redirect(url_for('sold_items'))

    # Unmark as sold
    cursor.execute('''
        UPDATE items
        SET sold = 0, sold_date = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (item_id,))

    conn.commit()
    conn.close()

    flash(f'{item["name"]} returned to inventory!', 'success')
    return redirect(url_for('sold_items'))


@app.route('/categories')
@login_required
def manage_categories():
    """Display and manage categories"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categories ORDER BY name')
    categories = cursor.fetchall()
    conn.close()
    return render_template('categories.html', categories=categories)


@app.route('/categories/add', methods=['POST'])
@login_required
def add_category():
    """Add a new category"""
    name = request.form.get('name')
    if not name:
        flash('Category name is required', 'error')
        return redirect(url_for('manage_categories'))

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO categories (name) VALUES (?)', (name,))
        conn.commit()
        flash(f'Category "{name}" added successfully!', 'success')
    except sqlite3.IntegrityError:
        flash(f'Category "{name}" already exists', 'error')
    finally:
        conn.close()

    return redirect(url_for('manage_categories'))


@app.route('/categories/delete/<int:category_id>', methods=['POST'])
@login_required
def delete_category(category_id):
    """Delete a category"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM categories WHERE id = ?', (category_id,))
    category = cursor.fetchone()

    if category:
        cursor.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        conn.commit()
        flash(f'Category "{category["name"]}" deleted successfully!', 'success')
    else:
        flash('Category not found', 'error')

    conn.close()
    return redirect(url_for('manage_categories'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        email = request.form.get('email')

        if not username or not password:
            flash('Username and password are required', 'error')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))

        conn = get_db()
        cursor = conn.cursor()

        try:
            password_hash = generate_password_hash(password)
            cursor.execute('INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)',
                         (username, password_hash, email))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists', 'error')
        finally:
            conn.close()

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Username and password are required', 'error')
            return redirect(url_for('login'))

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash(f'Welcome back, {username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('index'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """User logout"""
    username = session.get('username', 'User')
    session.clear()
    flash(f'Goodbye, {username}!', 'success')
    return redirect(url_for('login'))


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
